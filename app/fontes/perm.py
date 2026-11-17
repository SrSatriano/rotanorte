"""EUA – empresas que patrocinaram GREEN CARD (PERM / EB-2 / EB-3).

Fonte: arquivo oficial de "disclosure" do programa PERM do Departamento do
Trabalho (OFLC), publicado a cada trimestre em
https://www.dol.gov/agencies/eta/foreign-labor/performance
Cada linha é um pedido de certificação para contratar um estrangeiro de
forma PERMANENTE. Aqui ficam só os pedidos CERTIFICADOS nas ocupações do
seu perfil, agrupados por empresa. O arquivo é grande (~150 MB), então só é
baixado quando sai uma versão nova.
"""
from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict

from ..ocupacoes import classificar
from ..planilha import iterar_xlsx
from ..util import PASTA_DADOS, baixar

NOME = "EUA · Green card por empregador (PERM)"
PAGINA = "https://www.dol.gov/agencies/eta/foreign-labor/performance"


def achar_arquivo_mais_recente() -> tuple[str, str]:
    html = baixar(PAGINA, timeout=60).decode("utf-8", "replace")
    achados = []
    for href in set(re.findall(r'href="([^"]+PERM_Disclosure_Data[^"]+\.xlsx)"', html, re.I)):
        m = re.search(r"FY_?(\d{2,4})(?:_Q(\d))?", href, re.I)
        if not m:
            continue
        ano = int(m.group(1))
        ano = ano + 2000 if ano < 100 else ano
        tri = int(m.group(2) or 4)
        url = href if href.startswith("http") else "https://www.dol.gov" + href
        achados.append(((ano, tri, "New_Form" not in href), url, f"FY{ano} T{tri}"))
    if not achados:
        raise RuntimeError("Não encontrei o arquivo PERM na página do Departamento do Trabalho.")
    achados.sort(reverse=True)
    _, url, periodo = achados[0]
    return url, periodo


def _data(t: str) -> str:
    """Datas vêm como número de série do Excel (ex.: 45964) ou texto."""
    t = (t or "").strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", t):
        import datetime as dt
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(float(t)))).isoformat()
    return t[:10]


def _num(t: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", (t or "").replace(",", ""))
    return float(m.group(0)) if m else None


def _hora(valor: float | None, por: str) -> float | None:
    if not valor:
        return None
    p = (por or "").lower()
    if p.startswith("year") or valor > 1000:
        return round(valor / 2080, 2)
    if p.startswith("month"):
        return round(valor / 173, 2)
    if p.startswith("week"):
        return round(valor / 40, 2)
    if p.startswith("bi"):
        return round(valor / 80, 2)
    return round(valor, 2)


def processar(caminho, periodo: str, fonte_url: str, categorias: set[str], log=print) -> list[dict]:
    linhas = iterar_xlsx(caminho)
    cab = [c.strip().upper() for c in next(linhas)]
    i = {c: n for n, c in enumerate(cab)}

    def g(linha, col):
        n = i.get(col)
        return linha[n] if n is not None and n < len(linha) else ""

    grupos: dict[tuple, dict] = defaultdict(lambda: {"casos": 0, "locais": defaultdict(int), "salarios": [],
                                                     "cargos": defaultdict(int), "ultima": ""})
    lidas = 0
    for linha in linhas:
        lidas += 1
        if lidas % 50000 == 0:
            log(f"PERM: {lidas} pedidos lidos…")
        if not g(linha, "CASE_STATUS").lower().startswith("certified"):
            continue
        soc = g(linha, "PWD_SOC_CODE")
        cargo = g(linha, "JOB_TITLE")
        cat = classificar(cargo, soc)
        if cat not in categorias:
            continue
        empresa = g(linha, "EMP_BUSINESS_NAME").strip()
        if not empresa:
            continue
        chave = (empresa.upper(), soc[:7])
        d = grupos[chave]
        d.update(empresa=empresa, soc=soc[:7], soc_titulo=g(linha, "PWD_SOC_TITLE"), categoria=cat,
                 cidade=g(linha, "EMP_CITY"), estado=g(linha, "EMP_STATE"), telefone=g(linha, "EMP_PHONE"),
                 funcionarios=g(linha, "EMP_NUM_PAYROLL"))
        d["casos"] += 1
        d["cargos"][cargo.strip().title()] += 1
        local = ", ".join(x for x in (g(linha, "PRIMARY_WORKSITE_CITY").title(), g(linha, "PRIMARY_WORKSITE_STATE")) if x)
        if local:
            d["locais"][local] += 1
        h = _hora(_num(g(linha, "JOB_OPP_WAGE_FROM")), g(linha, "JOB_OPP_WAGE_PER"))
        if h and 5 < h < 200:
            d["salarios"].append(h)
        data = _data(g(linha, "DECISION_DATE"))
        if data > d["ultima"]:
            d["ultima"] = data
    log(f"PERM: {lidas} pedidos lidos, {len(grupos)} empresas nas suas áreas.")
    saida = []
    for (emp, soc), d in grupos.items():
        sal = sorted(d["salarios"])
        saida.append({
            "id": "perm:" + hashlib.sha1(f"{emp}|{soc}|{periodo}".encode()).hexdigest()[:16],
            "empresa": d["empresa"], "cidade": (d["cidade"] or "").title(), "estado": d["estado"],
            "soc": d["soc"], "soc_titulo": d["soc_titulo"], "categoria": d["categoria"],
            "cargo": max(d["cargos"], key=d["cargos"].get) if d["cargos"] else "",
            "casos": d["casos"], "salario_min": sal[0] if sal else None, "salario_max": sal[-1] if sal else None,
            "locais": "; ".join(k for k, _ in sorted(d["locais"].items(), key=lambda x: -x[1])[:4]),
            "ultima_decisao": d["ultima"], "telefone": d["telefone"], "funcionarios": d["funcionarios"],
            "periodo": periodo, "fonte_url": fonte_url,
        })
    return saida


def coletar(cfg: dict, log, categorias: set[str], url_anterior: str | None, forcar=False) -> tuple[list[dict], str]:
    url, periodo = achar_arquivo_mais_recente()
    if url == url_anterior and not forcar:
        log(f"PERM: arquivo oficial ainda é o mesmo ({periodo}) – nada novo.")
        return [], url
    log(f"PERM: baixando arquivo oficial {periodo} (~150 MB, pode levar alguns minutos)…")
    cache = PASTA_DADOS / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    arq = cache / "perm.xlsx"
    arq.write_bytes(baixar(url, timeout=900, tentativas=2))
    try:
        itens = processar(arq, periodo, url, categorias, log)
    finally:
        try:
            os.remove(arq)  # libera espaço; só baixa de novo quando sair outro trimestre
        except OSError:
            pass
    return itens, url
