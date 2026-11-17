"""Canadá – lista OFICIAL de empregadores que receberam LMIA positivo.

Publicada a cada trimestre pelo ESDC no Portal de Dados Abertos:
https://open.canada.ca/data/en/dataset/90fed587-1364-4f33-a9ee-208181dc0b97
São empresas que comprovadamente tiveram aprovação para contratar
trabalhadores estrangeiros na sua ocupação. Não são vagas abertas – são
alvos para você procurar vagas e mandar currículo.
"""
from __future__ import annotations

import hashlib
import re

from ..ocupacoes import classificar
from ..planilha import ler_tabela, para_dicionarios
from ..util import baixar, baixar_json, sem_acento

NOME = "Canadá · Empregadores com LMIA aprovado (ESDC)"
DATASET = "90fed587-1364-4f33-a9ee-208181dc0b97"
URL_API = f"https://open.canada.ca/data/api/action/package_show?id={DATASET}"


def _idioma(res: dict) -> str:
    lang = res.get("language")
    if isinstance(lang, list):
        return ",".join(lang).lower()
    return str(lang or "").lower()


def _periodo(nome: str) -> str:
    m = re.search(r"(20\d\d)\s*Q([1-4])", nome or "", re.I)
    if m:
        return f"{m.group(1)}T{m.group(2)}"
    m = re.search(r"(20\d\d)", nome or "")
    return m.group(1) if m else ""


def recursos_recentes(pacote: dict, quantidade: int) -> list[dict]:
    recursos = pacote.get("result", pacote).get("resources", [])
    bons = []
    for r in recursos:
        nome = r.get("name") or ""
        if isinstance(nome, dict):
            nome = nome.get("en") or next(iter(nome.values()), "")
        fmt = (r.get("format") or "").upper()
        if fmt not in ("XLSX", "CSV", "XLS"):
            continue
        if "en" not in _idioma(r) and "_fr" in (r.get("url") or "").lower():
            continue
        if _idioma(r) and "en" not in _idioma(r):
            continue
        if "positive" not in nome.lower() and "positive" not in (r.get("url") or "").lower():
            continue
        if fmt == "XLS":
            continue  # formato antigo não suportado
        r["_nome"] = nome
        r["_periodo"] = _periodo(nome) or _periodo(r.get("url", ""))
        bons.append(r)
    bons.sort(key=lambda r: (r["_periodo"], r.get("created") or ""), reverse=True)
    vistos, saida = set(), []
    for r in bons:
        if r["_periodo"] in vistos:
            continue
        vistos.add(r["_periodo"])
        saida.append(r)
        if len(saida) >= quantidade:
            break
    return saida


def _campo(linha: dict, *nomes) -> str:
    for k, v in linha.items():
        kk = sem_acento(k)
        if any(n in kk for n in nomes):
            return (v or "").strip()
    return ""


def processar_tabela(dados: bytes, periodo: str, fonte_url: str, categorias_interesse: set[str]) -> list[dict]:
    linhas = para_dicionarios(ler_tabela(dados), "employer")
    saida = []
    ult_prov = ult_prog = ""
    for ln in linhas:
        prov = _campo(ln, "province", "territor") or ult_prov
        prog = _campo(ln, "stream", "program") or ult_prog
        ult_prov, ult_prog = prov, prog
        empresa = _campo(ln, "employer")
        ocup = _campo(ln, "occupation", "noc")
        if not empresa or not ocup:
            continue
        cat = classificar(ocup, ocup)
        if categorias_interesse and cat not in categorias_interesse:
            continue
        posicoes = _campo(ln, "positions", "approved positions")
        try:
            posicoes_n = int(float(re.sub(r"[^\d.]", "", posicoes) or 0))
        except ValueError:
            posicoes_n = None
        endereco = _campo(ln, "address")
        chave = hashlib.sha1(f"{empresa}|{endereco}|{ocup}|{periodo}".encode()).hexdigest()[:16]
        saida.append({"id": f"lmia:{chave}", "pais": "CA", "regiao": prov, "empresa": empresa,
                      "endereco": endereco, "ocupacao": ocup, "programa": prog, "posicoes": posicoes_n,
                      "periodo": periodo, "categoria": cat, "fonte_url": fonte_url})
    return saida


def coletar(cfg: dict, log, categorias_interesse: set[str]) -> list[dict]:
    qtd = int(cfg.get("trimestres", 4))
    pacote = baixar_json(URL_API, timeout=60)
    recursos = recursos_recentes(pacote, qtd)
    if not recursos:
        raise RuntimeError("Não encontrei arquivos recentes de LMIA positivo no portal de dados abertos.")
    todos = []
    for r in recursos:
        log(f"Baixando lista oficial de LMIA {r['_periodo']}…")
        dados = baixar(r["url"], timeout=240)
        itens = processar_tabela(dados, r["_periodo"], r["url"], categorias_interesse)
        log(f"LMIA {r['_periodo']}: {len(itens)} empregadores nas suas áreas.")
        todos.extend(itens)
    return todos
