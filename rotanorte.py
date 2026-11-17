#!/usr/bin/env python3
"""RotaNorte – buscador pessoal de vagas com visto para EUA e Canadá.

Uso:
  python rotanorte.py              abre o painel no navegador
  python rotanorte.py coletar      busca vagas em todas as fontes (para agendar)
  python rotanorte.py diagnostico  testa a conexão com cada fonte oficial
  python rotanorte.py repontuar    recalcula as notas depois de mudar o perfil
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 9):
    print("O RotaNorte precisa do Python 3.9 ou mais novo. Baixe em https://www.python.org/downloads/")
    sys.exit(1)

SEM_CONSOLE = sys.stdout is None  # aberto com pythonw (sem janela preta)
if SEM_CONSOLE:
    import os as _os
    _os.makedirs(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "dados"), exist_ok=True)
    _log = open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "dados", "painel.log"),
                "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = _log

for _fluxo in (sys.stdout, sys.stderr):  # evita erro de acentos no Windows
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from app import coleta, config  # noqa: E402
from app.util import ErroRede, baixar  # noqa: E402


def diagnostico() -> int:
    import datetime as dt
    testes = [
        ("EUA – feed H-2B (DOL)", "https://api.seasonaljobs.dol.gov/datahub-search/sjCaseData/zip/h2b/"
         + (dt.date.today() - dt.timedelta(days=1)).isoformat()),
        ("Canadá – Job Bank RSS", "https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed?term=welder&sort=D&rows=5&fage=7"),
        ("Canadá – Dados abertos (LMIA)", "https://open.canada.ca/data/api/action/package_show?id=90fed587-1364-4f33-a9ee-208181dc0b97"),
    ]
    falhas = 0
    for nome, url in testes:
        try:
            dados = baixar(url, timeout=60, tentativas=1)
            print(f"  OK    {nome}  ({len(dados)//1024} KB)")
        except ErroRede as e:
            falhas += 1
            print(f"  FALHA {nome}\n        {e}")
    print("\nSe algo falhou: confira a internet, antivírus/firewall ou tente mais tarde (sites do governo"
          " às vezes ficam fora do ar à noite).")
    return 1 if falhas else 0


def main() -> int:
    config.garantir_arquivos()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "painel"
    if cmd == "coletar":
        r = coleta.executar(sys.argv[2:] or None)
        return 0 if r.get("ok") else 1
    if cmd == "diagnostico":
        return diagnostico()
    if cmd == "repontuar":
        print(f"{coleta.repontuar_tudo()} vagas recalculadas.")
        return 0
    if cmd == "painel":
        from app import servidor
        numeros = [a for a in sys.argv[2:] if a.isdigit()]
        porta = int(numeros[0]) if numeros else 8765
        servidor.iniciar(porta, abrir_navegador="--sem-navegador" not in sys.argv, sem_console=SEM_CONSOLE)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
