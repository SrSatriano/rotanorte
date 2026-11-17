"""Canadá – empregadores DESIGNADOS no Atlantic Immigration Program (AIP).

Uma oferta de emprego de empregador designado pode levar direto à
RESIDÊNCIA PERMANENTE (sem LMIA). Cada província publica sua lista:
- Terra Nova e Labrador (NL): tabela no site do governo (com códigos NOC);
- Nova Escócia (NS): PDF oficial;
- New Brunswick (NB) e Ilha do Príncipe Eduardo (PEI): consulte os links
  oficiais (os sites não permitem leitura automática).
A leitura do PDF usa a biblioteca opcional 'pypdf' (INSTALAR_EXTRAS.bat).
"""
from __future__ import annotations

import hashlib
import io
import re

from ..util import ErroRede, baixar, limpar_html

NOME = "Canadá · Empregadores designados AIP"
URL_NL = "https://www.gov.nl.ca/immigration/designated-employers/"
PAGINA_NS = "https://liveinnovascotia.com/atlantic-immigration-program"
URL_NS_PADRAO = "https://liveinnovascotia.com/sites/default/files/2024-07/Designated_AIP_employers.pdf"

LINKS_OFICIAIS = {
    "NL": URL_NL,
    "NS": PAGINA_NS,
    "NB": "https://www.gnb.ca/content/dam/GNB3/t/fhc-fmc/immigration/docs/designated-employers-employeurs-designes.pdf",
    "PE": "https://www.princeedwardisland.ca/en/information/office-of-immigration/atlantic-immigration-program-designated-employers",
}

_SUFIXOS = r"\b(inc|ltd|limited|corp|corporation|co|company|llc|ulc|lp|incorporated|ltee|ltée|the)\b\.?"


def normalizar(nome: str) -> str:
    """Nome simplificado para comparar empresas de listas diferentes."""
    n = (nome or "").lower()
    n = re.split(r"\b(o/a|a/o|dba|operating as|carrying on business as)\b", n)
    partes = [p for p in n if p and not re.fullmatch(r"\s*(o/a|a/o|dba|operating as|carrying on business as)\s*", p)]
    nomes = []
    for p in partes:
        p = re.sub(_SUFIXOS, " ", p)
        p = re.sub(r"[^a-z0-9 ]", " ", p)
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) >= 3:
            nomes.append(p)
    return "|".join(nomes)


def _id(prov, nome):
    return "aip:" + hashlib.sha1(f"{prov}|{nome}".encode()).hexdigest()[:16]


def coletar_nl(log) -> list[dict]:
    html = baixar(URL_NL, timeout=60).decode("utf-8", "replace")
    itens = []
    for linha in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        cel = [re.sub(r"\s+", " ", limpar_html(c)).strip() for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", linha)]
        if len(cel) < 2 or cel[0].lower().startswith("employer name") or not cel[0]:
            continue
        itens.append({"id": _id("NL", cel[0]), "provincia": "NL", "empresa": cel[0],
                      "local": cel[1] if len(cel) > 1 else "", "data": cel[2] if len(cel) > 2 else "",
                      "noc": cel[3] if len(cel) > 3 else "", "fonte_url": URL_NL})
    log(f"AIP Terra Nova e Labrador: {len(itens)} empregadores designados.")
    return itens


def coletar_ns(log) -> list[dict]:
    try:
        import pypdf  # opcional
    except ImportError:
        log("AIP Nova Escócia: instale o extra 'pypdf' (INSTALAR_EXTRAS.bat) para ler o PDF oficial.")
        return []
    url = URL_NS_PADRAO
    try:
        pagina = baixar(PAGINA_NS, timeout=60).decode("utf-8", "replace")
        m = re.search(r'href="([^"]*Designated[^"]*AIP[^"]*\.pdf)"', pagina, re.I)
        if m:
            url = m.group(1) if m.group(1).startswith("http") else "https://liveinnovascotia.com" + m.group(1)
    except ErroRede:
        pass
    leitor = pypdf.PdfReader(io.BytesIO(baixar(url, timeout=120)))
    texto = "\n".join((p.extract_text() or "") for p in leitor.pages)
    atual = re.search(r"Current as of ([A-Za-z]+ \d{1,2}, \d{4})", texto)
    itens = []
    for linha in texto.splitlines():
        linha = linha.strip()
        m = re.match(r"^[••·\-–]\s*(.+)$", linha)
        if not m:
            continue
        nome = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(nome) < 3 or nome.lower().startswith(("http", "www")):
            continue
        itens.append({"id": _id("NS", nome), "provincia": "NS", "empresa": nome, "local": "", "noc": "",
                      "data": atual.group(1) if atual else "", "fonte_url": url})
    log(f"AIP Nova Escócia: {len(itens)} empregadores designados"
        + (f" (lista de {atual.group(1)})." if atual else "."))
    return itens


def coletar(cfg: dict, log) -> list[dict]:
    itens = []
    for nome, func in (("NL", coletar_nl), ("NS", coletar_ns)):
        try:
            itens += func(log)
        except Exception as e:  # noqa: BLE001 – uma província falhar não impede a outra
            log(f"AIP {nome}: falhou ({e}).")
    if not itens:
        raise RuntimeError("Nenhuma lista AIP pôde ser lida agora.")
    return itens
