"""Cotação oficial do dólar americano e canadense (PTAX do Banco Central do Brasil).

Usada só para mostrar uma ESTIMATIVA do salário em reais (bruto, antes de
impostos e sem considerar o custo de vida lá fora).
"""
from __future__ import annotations

import datetime as dt

from . import db
from .util import baixar_json

URL = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
       "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
       "?@moeda='{moeda}'&@dataInicial='{ini}'&@dataFinalCotacao='{fim}'&$top=100&$format=json"
       "&$select=cotacaoVenda,dataHoraCotacao")


def _cotacao(moeda: str) -> dict | None:
    hoje = dt.date.today()
    ini = (hoje - dt.timedelta(days=10)).strftime("%m-%d-%Y")
    fim = hoje.strftime("%m-%d-%Y")
    url = URL.format(moeda=moeda, ini=ini, fim=fim)
    dados = baixar_json(url, timeout=30, tentativas=2)
    valores = dados.get("value") or []
    if not valores:
        return None
    ultimo = valores[-1]
    return {"valor": float(ultimo["cotacaoVenda"]), "data": str(ultimo["dataHoraCotacao"])[:10]}


def atualizar(con, log=print) -> dict:
    cambio = db.kv_ler(con, "cambio", {}) or {}
    for moeda in ("USD", "CAD"):
        try:
            c = _cotacao(moeda)
            if c:
                cambio[moeda] = c
        except Exception as e:  # noqa: BLE001 – câmbio é opcional
            log(f"Cotação {moeda} indisponível agora ({e}).")
    if cambio:
        db.kv_salvar(con, "cambio", cambio)
        log("Cotação PTAX: " + ", ".join(f"{m} R$ {v['valor']:.2f} ({v['data']})" for m, v in cambio.items()))
    return cambio


def salario_mensal_brl(salario_hora: float | None, moeda: str | None, cambio: dict) -> float | None:
    """Estimativa bruta: horas × 40 h/semana × 4,33 semanas × cotação."""
    if not salario_hora or not moeda or moeda not in cambio:
        return None
    return round(salario_hora * 40 * 4.33 * cambio[moeda]["valor"], -1)
