"""Canadá – Job Bank (jobbank.gc.ca), o site oficial de empregos do governo.

1. Lê o feed RSS público de busca para cada termo configurado.
2. Para cada vaga nova publicada no próprio Job Bank, abre o anúncio e
   verifica se ele aceita candidatos internacionais ("Candidates with or
   without a valid Canadian work permit" / "international candidates") e se
   menciona LMIA.
Só vagas confirmadas como abertas a estrangeiros recebem a marca verde.
"""
from __future__ import annotations

import email.utils
import re
import urllib.parse
import xml.etree.ElementTree as ET

from ..util import ErroRede, baixar, limpar_html, sem_acento

NOME = "Canadá · Job Bank (governo)"
URL_RSS = ("https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed"
           "?searchstring={termo}&sort=D&rows=100&fage={dias}")
URL_VAGA = "https://www.jobbank.gc.ca/jobsearch/jobposting/{id}"

PROVINCIAS = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}

# Frases exatas usadas pelo Job Bank na seção "Who can apply to this job?".
# (Não usar só "international candidates": o site mostra um aviso genérico
#  com essa expressão em TODAS as páginas.)
MARCAS_INTERNACIONAL = [
    "other candidates with or without a valid canadian work permit",
    "candidates with or without a valid canadian work permit",
    "autres candidats avec ou sans permis de travail",
    "avec ou sans permis de travail valide",
]
MARCAS_SO_LOCAIS = [
    "do not apply if you are not authorized to work in canada",
    "ne postulez pas si vous n'etes pas autorise",
    "ne postulez pas si vous n'etes pas autorisee",
]
MARCAS_LMIA_APROVADO = ["approved lmia", "lmia approved", "positive lmia", "eimt approuv"]
MARCAS_LMIA = ["labour market impact assessment", "lmia", "eimt", "étude d'impact sur le marché du travail"]


def _texto(el, tag):
    x = el.find(tag)
    return (x.text or "").strip() if x is not None and x.text else ""


ATOM = "{http://www.w3.org/2005/Atom}"


def ler_rss(conteudo: bytes) -> list[dict]:
    """Lê o feed do Job Bank (hoje em formato Atom; aceita RSS 2.0 também)."""
    raiz = ET.fromstring(conteudo)
    itens = []
    for item in raiz.iter("item"):
        link = _texto(item, "link")
        m = re.search(r"jobposting/(\d+)", link)
        if not m:
            continue
        pub = _texto(item, "pubDate")
        try:
            pub = email.utils.parsedate_to_datetime(pub).date().isoformat()
        except (TypeError, ValueError):
            pub = pub[:16]
        itens.append({"jid": m.group(1), "titulo": limpar_html(_texto(item, "title")),
                      "link": link, "desc": limpar_html(_texto(item, "description")), "pub": pub})
    for ent in raiz.iter(f"{ATOM}entry"):
        link = ""
        for ln in ent.findall(f"{ATOM}link"):
            if "jobposting" in (ln.get("href") or ""):
                link = ln.get("href")
        m = re.search(r"jobposting/(\d+)", link)
        if not m:
            continue
        itens.append({"jid": m.group(1), "titulo": limpar_html(_texto(ent, f"{ATOM}title")),
                      "link": link, "desc": limpar_html(_texto(ent, f"{ATOM}summary")),
                      "pub": _texto(ent, f"{ATOM}updated")[:10]})
    return itens


def _extrair_basico(item: dict) -> dict:
    """Tira empresa/cidade/salário do texto do RSS (formato varia)."""
    d = item["desc"]
    titulo = item["titulo"]
    empresa = cidade = prov = sal = ""
    m = re.search(r"(?i)(?:employer|employeur)\s*[:\-]\s*(.+)", d)
    if m:
        empresa = m.group(1).split("\n")[0].strip()
    m = re.search(r"(?i)(?:location|lieu)\s*[:\-]?\s*([A-Za-zÀ-ÿ'.\- ]+?)\s*\(?\b([A-Z]{2})\b\)?", d)
    if m and m.group(2) in PROVINCIAS:
        cidade, prov = m.group(1).strip(" ,"), m.group(2)
    m = re.search(r"(?i)(?:salary|salaire)\s*[:\-]?\s*([^\n]+)", d)
    if m:
        sal = m.group(1).strip()
    if not sal:
        m = re.search(r"\$\s?\d[\d,.]*(?:\s?(?:to|-|à)\s?\$?\s?\d[\d,.]*)?\s*(?:hourly|annually|yearly|/hour|per hour|weekly|monthly)?", d)
        sal = m.group(0) if m else ""
    # títulos do RSS às vezes vêm como "Welder - Empresa - Cidade (PROV)"
    partes = [p.strip() for p in re.split(r"\s+[-–|]\s+", titulo) if p.strip()]
    if len(partes) >= 2 and not empresa:
        titulo = partes[0]
        empresa = partes[1]
        if len(partes) >= 3 and not cidade:
            mm = re.match(r"(.+?)\s*\(([A-Z]{2})\)", partes[2])
            if mm:
                cidade, prov = mm.group(1), mm.group(2)
    return {"titulo": titulo, "empresa": empresa, "cidade": cidade, "estado": prov, "salario_txt": sal}


def salario_por_hora(txt: str) -> float | None:
    if not txt:
        return None
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*\.?\d*", txt)]
    nums = [n for n in nums if n > 0]
    if not nums:
        return None
    v = nums[0]
    t = txt.lower()
    if "annual" in t or "year" in t or "annuel" in t or v > 1000:
        return round(v / 2080, 2)
    if "week" in t or "hebdo" in t:
        return round(v / 40, 2)
    if "month" in t or "mois" in t:
        return round(v / 173, 2)
    return v


def analisar_anuncio(html: str) -> dict:
    texto = limpar_html(html)
    t = re.sub(r"\s+", " ", re.sub(r"[,;:]", " ", sem_acento(texto)))
    res = {"aceita_estrangeiro": None, "lmia": None, "codigo_ocupacao": "", "descricao": "",
           "parceiro_externo": "provided by a partner site" in t or "fournie par un site partenaire" in t}
    if any(sem_acento(m) in t for m in MARCAS_INTERNACIONAL):
        res["aceita_estrangeiro"] = 1
    elif any(sem_acento(m) in t for m in MARCAS_SO_LOCAIS):
        res["aceita_estrangeiro"] = 0
    if any(m in t for m in MARCAS_LMIA_APROVADO):
        res["lmia"] = "aprovado"
    elif any(sem_acento(m) in t for m in MARCAS_LMIA):
        res["lmia"] = "solicitado"
    m = re.search(r"\b(?:NOC|CNP)\s*(?:2021)?\s*[:#]?\s*(\d{5})", texto) or re.search(r"\b(\d{5})\b\s*[-–]\s*[A-Z][a-z]", texto)
    if m:
        res["codigo_ocupacao"] = m.group(1)
    m = re.search(r"(?is)(Job details|Overview|Détails du poste)(.{0,2500})", texto)
    res["descricao"] = (m.group(2) if m else texto[:2500]).strip()
    sal = re.search(r"\$\s?\d[\d,.]*\s*(?:to\s*\$?\s?\d[\d,.]*)?\s*(?:hourly|annually|per hour|/ hour|weekly|monthly)", texto)
    res["salario_txt"] = sal.group(0) if sal else ""
    return res


def coletar(cfg: dict, log, ja_verificados: set[str]) -> list[dict]:
    termos = cfg.get("termos") or ["welder"]
    dias = int(cfg.get("dias", 14))
    limite = int(cfg.get("max_checagens_por_execucao", 100))
    vistos: dict[str, dict] = {}
    for termo in termos:
        url = URL_RSS.format(termo=urllib.parse.quote_plus(termo), dias=dias)
        try:
            itens = ler_rss(baixar(url, timeout=60, intervalo_host=2.0))
            log(f"Job Bank '{termo}': {len(itens)} anúncios no feed.")
        except (ErroRede, ET.ParseError) as e:
            log(f"Job Bank '{termo}': falhou ({e}).")
            continue
        for it in itens:
            vistos.setdefault(it["jid"], it)

    vagas = []
    checados = 0
    for jid, it in vistos.items():
        base = _extrair_basico(it)
        vaga = {
            "id": f"jobbank:{jid}", "fonte": NOME, "pais": "CA", "programa": "Canadá – oferta de emprego",
            **base, "salario_hora": salario_por_hora(base["salario_txt"]), "moeda": "CAD",
            "data_publicacao": it["pub"], "url": URL_VAGA.format(id=jid),
            "como_aplicar": "Abra o anúncio no Job Bank e veja a seção 'How to apply'.",
            "aceita_estrangeiro": None, "lmia": None, "codigo_ocupacao": "", "descricao": it["desc"][:1500],
        }
        if jid not in ja_verificados and checados < limite:
            try:
                info = analisar_anuncio(baixar(URL_VAGA.format(id=jid), timeout=30, tentativas=2,
                                               intervalo_host=1.5).decode("utf-8", "replace"))
                checados += 1
                if checados % 10 == 0:
                    log(f"Job Bank: {checados} anúncios conferidos…")
                vaga.update({k: v for k, v in info.items() if v not in (None, "") and k in vaga})
                vaga["aceita_estrangeiro"] = info["aceita_estrangeiro"]
                if info.get("parceiro_externo"):
                    vaga["como_aplicar"] = ("Anúncio vindo de site parceiro (ex.: Indeed). Na página do Job Bank, "
                                            "use o link 'View the full job posting' para se candidatar.")
                vaga["lmia"] = info["lmia"]
                if info.get("salario_txt") and not vaga.get("salario_hora"):
                    vaga["salario_txt"] = info["salario_txt"]
                    vaga["salario_hora"] = salario_por_hora(info["salario_txt"])
                vaga["_verificado"] = True
            except ErroRede as e:
                log(f"Não consegui abrir o anúncio {jid}: {e}")
        else:
            vaga["_verificado"] = jid in ja_verificados
        vagas.append(vaga)
    log(f"Job Bank: {len(vagas)} vagas únicas, {checados} anúncios conferidos agora.")
    return vagas
