"""Painel local: servidor web simples em http://127.0.0.1:8765 (só no seu PC)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import cambio, coleta, curriculo, db, golpes, janela
from .caminhos import avaliar
from .config import carregar_fontes, carregar_perfil, salvar_fontes, salvar_perfil
from .ocupacoes import CATEGORIAS
from .util import PASTA_WEB, VERSAO, agora_iso

STATUS_VALIDOS = ["", "interesse", "aplicado", "entrevista", "oferta", "recusado", "descartado"]


def _vagas(con, q: dict) -> list[dict]:
    sql = ["SELECT v.*, c.status AS status, c.notas AS notas, c.lembrete AS lembrete, c.aplicado_em AS aplicado_em "
           "FROM vagas v LEFT JOIN candidaturas c ON c.vaga_id=v.id WHERE (v.ativo=1 OR COALESCE(c.status,'')<>'')"]
    args: list = []
    if q.get("desde"):
        sql.append("AND v.primeira_vez>?"); args.append(q["desde"])
    if q.get("pais"):
        sql.append("AND v.pais=?"); args.append(q["pais"])
    if q.get("fonte"):
        sql.append("AND v.fonte=?"); args.append(q["fonte"])
    if q.get("cat"):
        sql.append("AND v.categoria=?"); args.append(q["cat"])
    if q.get("min"):
        sql.append("AND COALESCE(v.score,0)>=?"); args.append(int(q["min"]))
    if q.get("so_estrangeiro") == "1":
        sql.append("AND v.aceita_estrangeiro=1")
    elif q.get("so_estrangeiro") == "2":
        sql.append("AND COALESCE(v.aceita_estrangeiro,-1)<>0")
    if q.get("status") == "_com":
        sql.append("AND COALESCE(c.status,'')<>''")
    elif q.get("status"):
        sql.append("AND c.status=?"); args.append(q["status"])
    else:
        sql.append("AND COALESCE(c.status,'')<>'descartado'")
    if q.get("q"):
        sql.append("AND (v.titulo LIKE ? OR v.empresa LIKE ? OR v.cidade LIKE ? OR v.estado LIKE ? OR v.descricao LIKE ?)")
        args += [f"%{q['q']}%"] * 5
    ordem = {"score": "v.score DESC, v.data_publicacao DESC", "data": "v.data_publicacao DESC",
             "salario": "COALESCE(v.salario_hora,0) DESC"}.get(q.get("ordem", "score"), "v.score DESC")
    sql.append(f"ORDER BY {ordem} LIMIT ? OFFSET ?")
    args.append(min(int(q.get("limite") or 300), 2000))
    args.append(max(0, int(q.get("offset") or 0)))
    cot = db.kv_ler(con, "cambio", {}) or {}
    saida = []
    for r in con.execute(" ".join(sql), args).fetchall():
        v = db.linha_para_dict(r)
        v["salario_mes_brl"] = cambio.salario_mensal_brl(v.get("salario_hora"), v.get("moeda"), cot)
        saida.append(v)
    return saida


def _estatisticas(con) -> dict:
    hoje = agora_iso()[:10]
    um = lambda s, a=(): con.execute(s, a).fetchone()[0]  # noqa: E731
    pares = lambda s, a=(): [list(r) for r in con.execute(s, a).fetchall()]  # noqa: E731
    base = "FROM vagas WHERE ativo=1 AND aceita_estrangeiro=1"
    return {
        "por_pais": pares(f"SELECT pais, COUNT(*) {base} GROUP BY pais"),
        "por_area": pares(f"SELECT COALESCE(categoria,'outra'), COUNT(*) {base} GROUP BY 1 ORDER BY 2 DESC"),
        "por_estado": pares(f"SELECT pais || ' · ' || estado, COUNT(*) {base} AND estado<>'' GROUP BY 1 ORDER BY 2 DESC LIMIT 8"),
        "faixa_nota": pares(f"SELECT CASE WHEN score>=70 THEN '70+' WHEN score>=55 THEN '55–69' WHEN score>=40 THEN '40–54' ELSE '<40' END, COUNT(*) {base} GROUP BY 1"),
        "salario_medio": pares(f"SELECT pais, ROUND(AVG(salario_hora),2) {base} AND salario_hora>0 GROUP BY pais"),
        "pipeline": pares("SELECT status, COUNT(*) FROM candidaturas WHERE COALESCE(status,'')<>'' GROUP BY status"),
        "lembretes": [db.linha_para_dict(r) for r in con.execute(
            "SELECT v.id, v.titulo, v.empresa, v.pais, c.status, c.lembrete FROM candidaturas c JOIN vagas v ON v.id=c.vaga_id "
            "WHERE COALESCE(c.lembrete,'')<>'' AND c.lembrete<=? AND c.status NOT IN ('recusado','descartado') "
            "ORDER BY c.lembrete", (hoje,))],
        "empresas_por_regiao": pares("SELECT regiao, COUNT(DISTINCT empresa) FROM empregadores GROUP BY regiao ORDER BY 2 DESC LIMIT 10"),
        "ultima_busca": db.kv_ler(con, "ultima_busca"),
        "cambio": db.kv_ler(con, "cambio", {}),
        "total_ativas": um("SELECT COUNT(*) FROM vagas WHERE ativo=1"),
    }


class Painel(BaseHTTPRequestHandler):
    server_version = "RotaNorte/" + VERSAO

    def log_message(self, fmt, *args):  # silencioso
        pass

    # ----------------------------------------------------------- respostas
    def _enviar(self, codigo: int, corpo: bytes, tipo: str, extra: dict | None = None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, dados, codigo=200):
        self._enviar(codigo, json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8"),
                     "application/json; charset=utf-8")

    def _html(self, texto: str):
        self._enviar(200, texto.encode("utf-8"), "text/html; charset=utf-8")

    def _corpo(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def _origem_ok(self) -> bool:
        """Bloqueia pedidos vindos de outros sites (proteção básica)."""
        origem = self.headers.get("Origin") or self.headers.get("Referer") or ""
        return not origem or origem.startswith(("http://127.0.0.1", "http://localhost"))

    # ----------------------------------------------------------------- GET
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        rota = url.path
        try:
            if rota in ("/", "/index.html"):
                return self._html((PASTA_WEB / "index.html").read_text(encoding="utf-8"))
            if rota == "/api/ping":
                ULTIMO_SINAL["t"] = time.time()
                return self._json({"app": "RotaNorte", "versao": VERSAO})
            if rota == "/favicon.ico":
                return self._enviar(204, b"", "image/x-icon")
            con = db.conectar()
            if rota == "/api/resumo":
                c = lambda s, a=(): con.execute(s, a).fetchone()[0]  # noqa: E731
                execucoes = [dict(r) for r in con.execute(
                    "SELECT fonte, fim, ok, mensagem, novos, total FROM execucoes ORDER BY id DESC LIMIT 12")]
                return self._json({
                    "versao": VERSAO,
                    "vagas": c("SELECT COUNT(*) FROM vagas WHERE ativo=1"),
                    "vagas_estrangeiro": c("SELECT COUNT(*) FROM vagas WHERE ativo=1 AND aceita_estrangeiro=1"),
                    "vagas_boas": c("SELECT COUNT(*) FROM vagas WHERE ativo=1 AND aceita_estrangeiro=1 AND score>=?",
                                    (carregar_perfil()["preferencias"].get("score_minimo", 40),)),
                    "novas_hoje": c("SELECT COUNT(*) FROM vagas WHERE substr(primeira_vez,1,10)=?", (agora_iso()[:10],)),
                    "empregadores": c("SELECT COUNT(*) FROM empregadores"),
                    "candidaturas": {r[0]: r[1] for r in con.execute(
                        "SELECT status, COUNT(*) FROM candidaturas WHERE status<>'' GROUP BY status")},
                    "execucoes": execucoes,
                    "coleta": {k: coleta.ESTADO[k] for k in ("rodando", "inicio", "fim")},
                    "fontes": [r[0] for r in con.execute("SELECT DISTINCT fonte FROM vagas ORDER BY fonte")],
                    "categorias": {k: v["nome"] for k, v in CATEGORIAS.items()},
                    "ultima_busca": db.kv_ler(con, "ultima_busca"),
                })
            if rota == "/api/vagas":
                return self._json(_vagas(con, q))
            if rota == "/api/estatisticas":
                return self._json(_estatisticas(con))
            if rota == "/api/email":
                r = con.execute("SELECT * FROM vagas WHERE id=?", (q.get("id"),)).fetchone()
                if not r:
                    return self._json({"erro": "vaga não encontrada"}, 404)
                vaga = db.linha_para_dict(r)
                assunto, corpo = curriculo.texto_carta(carregar_perfil(), vaga)
                import re as _re
                emails = _re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", vaga.get("como_aplicar") or "")
                return self._json({"para": emails[0] if emails else "", "assunto": assunto, "corpo": corpo})
            if rota == "/api/vaga":
                r = con.execute("SELECT v.*, c.status, c.notas, c.lembrete, c.aplicado_em FROM vagas v "
                                "LEFT JOIN candidaturas c ON c.vaga_id=v.id WHERE v.id=?", (q.get("id"),)).fetchone()
                if not r:
                    return self._json({"erro": "vaga não encontrada"}, 404)
                v = db.linha_para_dict(r)
                v["salario_mes_brl"] = cambio.salario_mensal_brl(v.get("salario_hora"), v.get("moeda"),
                                                                 db.kv_ler(con, "cambio", {}) or {})
                return self._json(v)
            if rota == "/api/empregadores":
                sql = ["SELECT * FROM empregadores WHERE 1=1"]
                args = []
                if q.get("q"):
                    sql.append("AND (empresa LIKE ? OR endereco LIKE ? OR ocupacao LIKE ?)")
                    args += [f"%{q['q']}%"] * 3
                if q.get("regiao"):
                    sql.append("AND regiao=?"); args.append(q["regiao"])
                if q.get("cat"):
                    sql.append("AND categoria=?"); args.append(q["cat"])
                sql.append("ORDER BY periodo DESC, COALESCE(posicoes,0) DESC LIMIT 1000")
                linhas = [dict(r) for r in con.execute(" ".join(sql), args)]
                regioes = [r[0] for r in con.execute("SELECT DISTINCT regiao FROM empregadores WHERE regiao<>'' ORDER BY regiao")]
                return self._json({"itens": linhas, "regioes": regioes})
            if rota == "/api/perm":
                sql, args = ["SELECT * FROM perm_empregadores WHERE 1=1"], []
                if q.get("q"):
                    sql.append("AND (empresa LIKE ? OR cargo LIKE ? OR locais LIKE ? OR soc_titulo LIKE ?)")
                    args += [f"%{q['q']}%"] * 4
                if q.get("estado"):
                    sql.append("AND (estado=? OR locais LIKE ?)"); args += [q["estado"], f"%, {q['estado']}%"]
                if q.get("cat"):
                    sql.append("AND categoria=?"); args.append(q["cat"])
                sql.append("ORDER BY casos DESC, ultima_decisao DESC LIMIT 1000")
                itens = [dict(r) for r in con.execute(" ".join(sql), args)]
                info = con.execute("SELECT periodo, COUNT(*), SUM(casos) FROM perm_empregadores").fetchone()
                estados = [r[0] for r in con.execute("SELECT DISTINCT estado FROM perm_empregadores WHERE estado<>'' ORDER BY 1")]
                return self._json({"itens": itens, "periodo": info[0], "empresas": info[1], "casos": info[2] or 0,
                                   "estados": estados})
            if rota == "/api/aip":
                from .fontes import aip as _aip
                sql, args = ["SELECT * FROM aip_empregadores WHERE 1=1"], []
                if q.get("q"):
                    sql.append("AND (empresa LIKE ? OR local LIKE ? OR noc LIKE ?)"); args += [f"%{q['q']}%"] * 3
                if q.get("prov"):
                    sql.append("AND provincia=?"); args.append(q["prov"])
                if q.get("oficios") == "1":
                    sql.append("AND (noc LIKE '%72%' OR noc LIKE '%73%' OR noc LIKE '%75110%' OR noc LIKE '%94%' OR noc LIKE '%95%')")
                sql.append("ORDER BY provincia, empresa LIMIT 1500")
                itens = [dict(r) for r in con.execute(" ".join(sql), args)]
                contagem = dict(con.execute("SELECT provincia, COUNT(*) FROM aip_empregadores GROUP BY 1").fetchall())
                cruz = con.execute("SELECT COUNT(*) FROM vagas WHERE ativo=1 AND extras LIKE '%\"aip\": \"%'").fetchone()[0]
                return self._json({"itens": itens, "contagem": contagem, "links": _aip.LINKS_OFICIAIS,
                                   "vagas_cruzadas": cruz, "atualizado": db.kv_ler(con, "aip_atualizado")})
            if rota == "/api/caminhos":
                return self._json(avaliar(carregar_perfil()))
            if rota == "/api/perfil":
                return self._json(carregar_perfil())
            if rota == "/api/fontes":
                return self._json(carregar_fontes())
            if rota == "/api/coleta/estado":
                return self._json(coleta.ESTADO)
            if rota in ("/doc/curriculo", "/doc/carta"):
                vaga = None
                if q.get("id"):
                    r = con.execute("SELECT * FROM vagas WHERE id=?", (q["id"],)).fetchone()
                    vaga = db.linha_para_dict(r) if r else None
                perfil = carregar_perfil()
                if rota == "/doc/curriculo":
                    return self._html(curriculo.gerar_curriculo(perfil, vaga))
                return self._html(curriculo.gerar_carta(perfil, vaga or {}))
            if rota == "/api/exportar.csv":
                vagas = _vagas(con, {**q, "limite": 2000})
                buf = io.StringIO()
                campos = ["score", "pais", "programa", "titulo", "empresa", "cidade", "estado", "salario_txt",
                          "aceita_estrangeiro", "lmia", "data_publicacao", "data_inicio", "url", "status", "fonte"]
                w = csv.writer(buf, delimiter=";")
                w.writerow(campos)
                for v in vagas:
                    w.writerow([v.get(k) if v.get(k) is not None else "" for k in campos])
                return self._enviar(200, ("﻿" + buf.getvalue()).encode("utf-8"), "text/csv; charset=utf-8",
                                    {"Content-Disposition": "attachment; filename=vagas_rotanorte.csv"})
            return self._json({"erro": "rota não encontrada"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"erro": f"{type(e).__name__}: {e}"}, 500)

    # ---------------------------------------------------------------- POST
    def do_POST(self):
        if not self._origem_ok():
            return self._json({"erro": "origem não permitida"}, 403)
        rota = urllib.parse.urlparse(self.path).path
        try:
            dados = self._corpo()
            if rota == "/api/coletar":
                ok = coleta.executar_em_segundo_plano(dados.get("fontes"))
                return self._json({"ok": ok, "mensagem": "Busca iniciada." if ok else "Já existe uma busca rodando."})
            if rota == "/api/perfil":
                p = salvar_perfil(dados)
                n = coleta.repontuar_tudo()
                return self._json({"ok": True, "perfil": p, "repontuadas": n})
            if rota == "/api/fontes":
                return self._json({"ok": True, "fontes": salvar_fontes(dados)})
            if rota == "/api/pdf":
                from . import pdf as _pdf
                con = db.conectar()
                r = con.execute("SELECT * FROM vagas WHERE id=?", (dados.get("id"),)).fetchone()
                vaga = db.linha_para_dict(r) if r else {}
                perfil = carregar_perfil()
                nome = _pdf.nome_arquivo("Curriculo", perfil.get("nome") or "", vaga.get("empresa") or "")
                destino = _pdf.pasta_documentos() / f"{nome}.pdf"
                porta = self.server.server_address[1]
                url = f"http://127.0.0.1:{porta}/doc/curriculo" + (f"?id={urllib.parse.quote(vaga['id'])}" if vaga else "")
                arq = _pdf.gerar_pdf(url, destino)
                return self._json({"ok": True, "arquivo": str(arq), "nome": arq.name})
            if rota == "/api/abrir_pasta":
                import os
                import subprocess
                import sys as _sys
                from .util import PASTA_DOCS
                arq = os.path.abspath(str(dados.get("arquivo") or PASTA_DOCS))
                if not arq.startswith(os.path.abspath(str(PASTA_DOCS.parent))):
                    return self._json({"erro": "pasta não permitida"}, 400)
                if _sys.platform.startswith("win"):
                    if os.path.isfile(arq):
                        subprocess.Popen(["explorer", "/select,", arq])
                    else:
                        os.startfile(arq)  # noqa: S606
                else:
                    import webbrowser
                    webbrowser.open("file://" + os.path.dirname(arq))
                return self._json({"ok": True})
            if rota == "/api/telegram/chat":
                from . import avisos
                return self._json(avisos.descobrir_chat(dados.get("token", "")))
            if rota == "/api/telegram/teste":
                from . import avisos
                avisos.enviar(dados.get("token", ""), dados.get("chat_id", ""),
                              "🧭 <b>RotaNorte conectado!</b>\nVocê vai receber aqui as vagas novas com nota alta "
                              "e os lembretes de candidaturas.")
                return self._json({"ok": True})
            if rota == "/api/abrir":
                url = str(dados.get("url", ""))
                if not url.startswith(("https://", "http://", "mailto:")):
                    return self._json({"erro": "endereço não permitido"}, 400)
                import webbrowser
                webbrowser.open(url)  # abre no navegador normal do PC (onde você já está logado)
                return self._json({"ok": True})
            if rota == "/api/golpe":
                return self._json(golpes.analisar(dados.get("texto", "")))
            if rota == "/api/candidatura":
                status = dados.get("status", "")
                if status not in STATUS_VALIDOS:
                    return self._json({"erro": "status inválido"}, 400)
                con = db.conectar()
                antiga = con.execute("SELECT * FROM candidaturas WHERE vaga_id=?", (dados["vaga_id"],)).fetchone()
                antiga = dict(antiga) if antiga else {}
                notas = dados.get("notas", antiga.get("notas") or "")
                lembrete = dados.get("lembrete", antiga.get("lembrete") or "")
                aplicado = antiga.get("aplicado_em") or ""
                if status in ("aplicado", "entrevista", "oferta") and not aplicado:
                    aplicado = agora_iso()[:10]
                    if "lembrete" not in dados and not lembrete:
                        import datetime as _dt
                        lembrete = (_dt.date.today() + _dt.timedelta(days=7)).isoformat()  # cobrar resposta
                con.execute("INSERT OR REPLACE INTO candidaturas (vaga_id,status,notas,atualizado,lembrete,aplicado_em) "
                            "VALUES (?,?,?,?,?,?)",
                            (dados["vaga_id"], status, notas, agora_iso(), lembrete, aplicado))
                con.commit()
                return self._json({"ok": True, "lembrete": lembrete, "aplicado_em": aplicado})
            if rota == "/api/vaga_manual":
                texto = dados.get("texto", "")
                ident = hashlib.sha1((dados.get("url") or texto or agora_iso()).encode()).hexdigest()[:12]
                vaga = {"id": f"manual:{ident}", "fonte": "Adicionada por você", "pais": dados.get("pais", "CA"),
                        "programa": dados.get("programa", "A confirmar"), "titulo": dados.get("titulo", "Vaga"),
                        "empresa": dados.get("empresa", ""), "cidade": dados.get("cidade", ""), "estado": "",
                        "url": dados.get("url", ""), "como_aplicar": dados.get("como_aplicar", ""),
                        "aceita_estrangeiro": 1 if dados.get("aceita_estrangeiro") else None,
                        "descricao": texto[:4000], "data_publicacao": agora_iso()[:10]}
                con = db.conectar()
                db.salvar_vaga(con, coleta._preparar(vaga, carregar_perfil()))
                con.commit()
                return self._json({"ok": True, "id": vaga["id"], "risco_golpe": vaga["risco_golpe"],
                                   "alertas": vaga["alertas_golpe"]})
            return self._json({"erro": "rota não encontrada"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"erro": f"{type(e).__name__}: {e}"}, 500)


class Servidor(ThreadingHTTPServer):
    """Servidor que NÃO divide a porta com outro programa.

    No Windows, a opção padrão do Python (SO_REUSEADDR) deixa dois programas
    ocuparem a mesma porta e o navegador cai no programa errado. Aqui usamos
    porta exclusiva."""
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


ULTIMO_SINAL = {"t": time.time()}


def _vigiar(srv, processo, sem_console: bool):
    """Encerra o servidor quando a janela do app é fechada."""
    inicio = time.time()
    if processo is not None:
        processo.wait()
        if time.time() - inicio > 8:  # a janela ficou aberta e foi fechada
            print("Janela fechada – encerrando o RotaNorte.", flush=True)
            time.sleep(1.5)
            srv.shutdown()
            return
    if not sem_console:
        return  # com a janela preta aberta, o usuário encerra fechando-a
    # sem console: encerra se o painel ficar 3 minutos sem dar sinal de vida
    while True:
        time.sleep(20)
        if time.time() - ULTIMO_SINAL["t"] > 180 and not coleta.ESTADO["rodando"]:
            print("Painel fechado há 3 min – encerrando.", flush=True)
            srv.shutdown()
            return


def iniciar(porta: int = janela.PORTA_PADRAO, abrir_navegador: bool = True, sem_console: bool = False) -> None:
    srv = None
    for p in janela.candidatos(porta):
        if janela.porta_em_uso(p):
            if janela.rotanorte_na_porta(p):
                url = f"http://127.0.0.1:{p}/"
                print(f"  O RotaNorte já está aberto em {url} – abrindo a janela.", flush=True)
                if abrir_navegador:
                    janela.abrir_como_app(url)
                return
            print(f"  Porta {p} ocupada por outro programa – tentando a próxima…", flush=True)
            continue
        try:
            srv = Servidor(("127.0.0.1", p), Painel)
            porta = p
            break
        except OSError:
            print(f"  Porta {p} ocupada – tentando a próxima…", flush=True)
    if srv is None:
        print("  Não encontrei porta livre. Feche outros programas e tente de novo.", flush=True)
        return
    janela.salvar_porta(porta)
    url = f"http://127.0.0.1:{porta}/"
    print(f"\n  RotaNorte rodando em {url}\n  Feche a janela do RotaNorte para encerrar.\n", flush=True)
    processo = None
    if abrir_navegador:
        processo = janela.abrir_como_app(url)
    threading.Thread(target=_vigiar, args=(srv, processo, sem_console), daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
