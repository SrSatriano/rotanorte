"""Avisos no celular pelo Telegram (grátis).

Como configurar (uma vez):
1. No Telegram, procure @BotFather, envie /newbot e siga as instruções.
   Ele devolve um TOKEN parecido com 123456789:ABCdef...
2. Cole o token no RotaNorte (Meu perfil → Avisos no celular).
3. Abra o seu bot no Telegram e mande qualquer mensagem (ex.: "oi").
4. Clique em "Descobrir meu chat" e depois em "Enviar teste".
"""
from __future__ import annotations

import html
import json
import urllib.request

from . import db
from .ocupacoes import nome_categoria

API = "https://api.telegram.org/bot{token}/{metodo}"
PAIS = {"US": "🇺🇸 EUA", "CA": "🇨🇦 Canadá"}


def _chamar(token: str, metodo: str, dados: dict | None = None) -> dict:
    url = API.format(token=token.strip(), metodo=metodo)
    corpo = json.dumps(dados).encode() if dados is not None else None
    req = urllib.request.Request(url, data=corpo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            resp = json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            raise RuntimeError(f"Telegram respondeu erro {e.code}") from e
    if not resp.get("ok"):
        desc = resp.get("description", "erro desconhecido")
        if "Unauthorized" in desc:
            desc = "token inválido – confira o que o @BotFather enviou"
        elif "chat not found" in desc:
            desc = "chat não encontrado – mande uma mensagem para o seu bot e clique em 'Descobrir meu chat'"
        raise RuntimeError(desc)
    return resp


def descobrir_chat(token: str) -> dict:
    resp = _chamar(token, "getUpdates")
    for upd in reversed(resp.get("result", [])):
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat")
        if chat:
            nome = chat.get("first_name") or chat.get("title") or chat.get("username") or ""
            return {"chat_id": str(chat["id"]), "nome": nome}
    raise RuntimeError("Nenhuma mensagem encontrada. Abra o seu bot no Telegram, mande 'oi' e tente de novo.")


def enviar(token: str, chat_id: str, texto: str) -> None:
    # Telegram limita a 4096 caracteres por mensagem
    partes, atual = [], ""
    for bloco in texto.split("\n\n"):
        if len(atual) + len(bloco) > 3800:
            partes.append(atual)
            atual = ""
        atual += bloco + "\n\n"
    partes.append(atual)
    for p in partes:
        if p.strip():
            _chamar(token, "sendMessage", {"chat_id": chat_id, "text": p.strip(), "parse_mode": "HTML",
                                           "disable_web_page_preview": True})


def _linha_vaga(v) -> str:
    local = ", ".join(x for x in (v["cidade"], v["estado"]) if x)
    e = html.escape
    sal = f"\n💵 {e(v['salario_txt'])}" if v["salario_txt"] else ""
    return (f"<b>{v['score']}</b> · {e((v['titulo'] or '').title())}\n{PAIS.get(v['pais'], v['pais'])} · "
            f"{e(v['empresa'] or '')}{' · ' + e(local) if local else ''}{sal}\n"
            f"🧰 {e(nome_categoria(v['categoria']))} · <a href=\"{e(v['url'] or '')}\">ver anúncio</a>")


def avisar_novas(con, cfg: dict, inicio_busca: str, log=print) -> int:
    if not cfg.get("ativo") or not cfg.get("token") or not cfg.get("chat_id"):
        return 0
    nota = int(cfg.get("nota_minima", 60))
    novas = con.execute(
        "SELECT * FROM vagas WHERE ativo=1 AND aceita_estrangeiro=1 AND score>=? AND primeira_vez>=? "
        "ORDER BY score DESC LIMIT 12", (nota, inicio_busca)).fetchall()
    total = con.execute("SELECT COUNT(*) FROM vagas WHERE ativo=1 AND aceita_estrangeiro=1 AND score>=? "
                        "AND primeira_vez>=?", (nota, inicio_busca)).fetchone()[0]
    hoje = inicio_busca[:10]
    lembretes = con.execute(
        "SELECT v.titulo, v.empresa FROM candidaturas c JOIN vagas v ON v.id=c.vaga_id WHERE COALESCE(c.lembrete,'')<>'' "
        "AND c.lembrete<=? AND c.status NOT IN ('recusado','descartado')", (hoje,)).fetchall()
    if not novas and not lembretes:
        return 0
    partes = []
    if novas:
        partes.append(f"🧭 <b>RotaNorte: {total} vaga(s) nova(s) com nota ≥ {nota}</b>")
        partes += [_linha_vaga(v) for v in novas]
        if total > len(novas):
            partes.append(f"…e mais {total - len(novas)} no RotaNorte.")
    if lembretes:
        partes.append("⏰ <b>Cobrar resposta hoje:</b>\n" + "\n".join(
            f"• {html.escape((t or '').title())} – {html.escape(emp or '')}" for t, emp in lembretes))
    enviar(cfg["token"], cfg["chat_id"], "\n\n".join(partes))
    log(f"Aviso enviado no Telegram ({len(novas)} vagas, {len(lembretes)} lembretes).")
    return len(novas)
