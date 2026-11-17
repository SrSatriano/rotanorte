"""Roda todas as fontes, pontua as vagas e grava no banco."""
from __future__ import annotations

import threading
import traceback

from . import avisos, cambio, db, golpes
from .config import carregar_fontes, carregar_perfil
from .fontes import adzuna, aip, dol_h2b, jobbank, lmia, perm
from .ocupacoes import classificar
from .pontuacao import pontuar
from .util import agora_iso

ESTADO = {"rodando": False, "log": [], "inicio": None, "fim": None}
_trava = threading.Lock()


def _log(msg: str) -> None:
    linha = f"[{agora_iso()[11:19]}] {msg}"
    print(linha, flush=True)
    ESTADO["log"].append(linha)
    ESTADO["log"] = ESTADO["log"][-300:]


def _preparar(vaga: dict, perfil: dict) -> dict:
    vaga["categoria"] = classificar(vaga.get("titulo", ""), vaga.get("codigo_ocupacao", ""),
                                    vaga.get("descricao", ""))
    vaga["score"], vaga["motivos"] = pontuar(vaga, perfil)
    analise = golpes.analisar(" ".join(str(vaga.get(k) or "") for k in
                                       ("titulo", "descricao", "como_aplicar", "empresa")))
    vaga["risco_golpe"] = analise["risco"]
    vaga["alertas_golpe"] = [a["motivo"] for a in analise["alertas"]]
    return vaga


def repontuar_tudo() -> int:
    """Recalcula a nota de todas as vagas (ex.: depois de editar o perfil)."""
    perfil = carregar_perfil()
    con = db.conectar()
    n = 0
    for r in con.execute("SELECT * FROM vagas").fetchall():
        v = db.linha_para_dict(r)
        v["score"], v["motivos"] = pontuar(v, perfil)
        con.execute("UPDATE vagas SET score=?, motivos=?, categoria=? WHERE id=?",
                    (v["score"], __import__("json").dumps(v["motivos"], ensure_ascii=False),
                     v.get("categoria"), v["id"]))
        n += 1
    con.commit()
    return n


def cruzar_aip(con, perfil) -> int:
    """Marca vagas e empresas canadenses cujo empregador é designado no AIP."""
    import json as _json
    designados: dict[str, str] = {}
    for nome_norm, prov in con.execute("SELECT nome_norm, provincia FROM aip_empregadores"):
        for parte in (nome_norm or "").split("|"):
            if len(parte) >= 4:
                designados[parte] = prov
    if not designados:
        return 0
    n = 0
    for r in con.execute("SELECT * FROM vagas WHERE pais='CA'").fetchall():
        v = db.linha_para_dict(r)
        partes = aip.normalizar(v.get("empresa") or "").split("|")
        prov = next((designados[p] for p in partes if p in designados), None)
        ex = v.get("extras") if isinstance(v.get("extras"), dict) else {}
        if (ex.get("aip") or None) == prov:
            continue
        ex["aip"] = prov
        v["extras"] = ex
        v["score"], v["motivos"] = pontuar(v, perfil)
        con.execute("UPDATE vagas SET extras=?, score=?, motivos=? WHERE id=?",
                    (_json.dumps(ex, ensure_ascii=False), v["score"], _json.dumps(v["motivos"], ensure_ascii=False), v["id"]))
        n += 1
    for eid, empresa in con.execute("SELECT id, empresa FROM empregadores").fetchall():
        partes = aip.normalizar(empresa).split("|")
        prov = next((designados[p] for p in partes if p in designados), None)
        con.execute("UPDATE empregadores SET aip=? WHERE id=?", (prov, eid))
        n += 1 if prov else 0
    con.commit()
    return n


def arquivar_antigas(con) -> int:
    """Esconde vagas que já passaram ou sumiram das fontes (as acompanhadas ficam)."""
    import datetime as dt
    hoje = dt.date.today()
    limite_visto = (hoje - dt.timedelta(days=30)).isoformat()
    limite_inicio = (hoje - dt.timedelta(days=15)).isoformat()
    acompanhadas = "id NOT IN (SELECT vaga_id FROM candidaturas WHERE COALESCE(status,'') NOT IN ('','descartado'))"
    cur = con.execute(
        f"""UPDATE vagas SET ativo=0 WHERE ativo=1 AND {acompanhadas} AND fonte NOT LIKE 'Adicionada%' AND (
              substr(ultima_vez,1,10) < ? OR (data_inicio <> '' AND data_inicio IS NOT NULL AND data_inicio < ?))""",
        (limite_visto, limite_inicio))
    con.commit()
    return cur.rowcount


def executar(fontes_escolhidas: list[str] | None = None) -> dict:
    with _trava:
        if ESTADO["rodando"]:
            return {"ok": False, "mensagem": "Já existe uma busca em andamento."}
        ESTADO.update(rodando=True, log=[], inicio=agora_iso(), fim=None)
    resumo = {}
    try:
        perfil = carregar_perfil()
        cfg = carregar_fontes()
        con = db.conectar()
        escolha = set(fontes_escolhidas or ["dol_h2b", "jobbank", "lmia", "adzuna", "perm", "aip"])
        forcar = "forcar" in escolha

        def rodar(chave, nome, func):
            if chave not in escolha or not cfg.get(chave, {}).get("ativo"):
                return
            inicio = agora_iso()
            _log(f"== {nome} ==")
            try:
                novos, total = func()
                db.registrar_execucao(con, nome, inicio, True, "ok", novos, total)
                resumo[nome] = {"ok": True, "novos": novos, "total": total}
                _log(f"{nome}: {total} itens, {novos} novos.")
            except Exception as e:  # noqa: BLE001 – queremos seguir com as outras fontes
                msg = f"{type(e).__name__}: {e}"
                db.registrar_execucao(con, nome, inicio, False, msg)
                resumo[nome] = {"ok": False, "erro": msg}
                _log(f"ERRO em {nome}: {msg}")
                traceback.print_exc()

        def salvar_lista(vagas):
            novos = 0
            for v in vagas:
                novos += db.salvar_vaga(con, _preparar(v, perfil))
            con.commit()
            return novos, len(vagas)

        try:
            cambio.atualizar(con, _log)
        except Exception as e:  # noqa: BLE001
            _log(f"Cotação indisponível: {e}")

        rodar("dol_h2b", dol_h2b.NOME, lambda: salvar_lista(dol_h2b.coletar(cfg["dol_h2b"], _log)))

        def job_bank():
            ja = {r[0] for r in con.execute("SELECT id FROM vistos_jobbank")}
            vagas = jobbank.coletar(cfg["jobbank"], _log, ja)
            for v in vagas:
                jid = v["id"].split(":", 1)[1]
                if v.pop("_verificado", False) and jid not in ja:
                    con.execute("INSERT OR IGNORE INTO vistos_jobbank (id, verificado) VALUES (?,?)",
                                (jid, agora_iso()))
                antiga = con.execute("SELECT aceita_estrangeiro, lmia, codigo_ocupacao, descricao FROM vagas WHERE id=?",
                                     (v["id"],)).fetchone()
                if antiga and jid in ja:  # mantém o que já foi conferido no anúncio
                    v["aceita_estrangeiro"] = antiga["aceita_estrangeiro"]
                    v["lmia"] = antiga["lmia"]
                    v["codigo_ocupacao"] = antiga["codigo_ocupacao"] or v["codigo_ocupacao"]
                    v["descricao"] = antiga["descricao"] or v["descricao"]
            return salvar_lista(vagas)

        rodar("jobbank", jobbank.NOME, job_bank)

        def lista_lmia():
            cats = set(cfg["lmia"].get("categorias") or [])
            itens = lmia.coletar(cfg["lmia"], _log, cats)
            antes = con.execute("SELECT COUNT(*) FROM empregadores").fetchone()[0]
            for e in itens:
                db.salvar_empregador(con, e)
            con.commit()
            depois = con.execute("SELECT COUNT(*) FROM empregadores").fetchone()[0]
            return depois - antes, len(itens)

        rodar("lmia", lmia.NOME, lista_lmia)
        rodar("adzuna", adzuna.NOME, lambda: salvar_lista(adzuna.coletar(cfg["adzuna"], _log)))

        def green_card():
            cats = set(cfg["perm"].get("categorias") or [])
            itens, url = perm.coletar(cfg["perm"], _log, cats, db.kv_ler(con, "perm_url"), forcar)
            if not itens:
                return 0, con.execute("SELECT COUNT(*) FROM perm_empregadores").fetchone()[0]
            with db._trava:
                con.execute("DELETE FROM perm_empregadores")
                cols = ["id", "empresa", "cidade", "estado", "soc", "soc_titulo", "categoria", "cargo", "casos",
                        "salario_min", "salario_max", "locais", "ultima_decisao", "telefone", "funcionarios",
                        "periodo", "fonte_url"]
                con.executemany(f"INSERT OR REPLACE INTO perm_empregadores ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                                [[i.get(c) for c in cols] for i in itens])
                con.commit()
            db.kv_salvar(con, "perm_url", url)
            return len(itens), len(itens)

        rodar("perm", perm.NOME, green_card)

        def atlantico():
            import datetime as dt
            ultima = db.kv_ler(con, "aip_atualizado")
            dias = int(cfg["aip"].get("dias_entre_atualizacoes", 7))
            if ultima and not forcar and ultima > (dt.datetime.now() - dt.timedelta(days=dias)).isoformat():
                _log("AIP: lista atualizada recentemente – pulando.")
                return 0, con.execute("SELECT COUNT(*) FROM aip_empregadores").fetchone()[0]
            itens = aip.coletar(cfg["aip"], _log)
            provs = {i["provincia"] for i in itens}
            with db._trava:
                for pv in provs:
                    con.execute("DELETE FROM aip_empregadores WHERE provincia=?", (pv,))
                con.executemany(
                    "INSERT OR REPLACE INTO aip_empregadores (id,provincia,empresa,local,noc,data,fonte_url,nome_norm,atualizado) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    [(i["id"], i["provincia"], i["empresa"], i.get("local"), i.get("noc"), i.get("data"),
                      i.get("fonte_url"), aip.normalizar(i["empresa"]), agora_iso()) for i in itens])
                con.commit()
            db.kv_salvar(con, "aip_atualizado", agora_iso())
            return len(itens), len(itens)

        rodar("aip", aip.NOME, atlantico)
        try:
            n = cruzar_aip(con, perfil)
            if n:
                _log(f"{n} vaga(s)/empresa(s) do Canadá são de empregadores designados no AIP.")
        except Exception as e:  # noqa: BLE001
            _log(f"Cruzamento AIP falhou: {e}")
        expiradas = arquivar_antigas(con)
        if expiradas:
            _log(f"{expiradas} vagas antigas/encerradas foram arquivadas.")
        db.kv_salvar(con, "ultima_busca", agora_iso())
        try:
            avisos.avisar_novas(con, cfg.get("telegram", {}), ESTADO["inicio"], _log)
        except Exception as e:  # noqa: BLE001
            _log(f"Aviso no Telegram falhou: {e}")
        _log("Busca concluída.")
        return {"ok": True, "resumo": resumo}
    finally:
        ESTADO.update(rodando=False, fim=agora_iso())


def executar_em_segundo_plano(fontes=None) -> bool:
    if ESTADO["rodando"]:
        return False
    threading.Thread(target=executar, args=(fontes,), daemon=True).start()
    return True
