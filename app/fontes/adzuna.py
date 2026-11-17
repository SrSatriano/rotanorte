"""(Opcional) Adzuna – agregador privado de vagas dos EUA e Canadá.

Precisa de chave gratuita em https://developer.adzuna.com/ (app_id e app_key).
Só são marcadas como "aceita estrangeiro" as vagas cujo texto fala
explicitamente em patrocínio de visto / LMIA. Sempre confirme com o empregador.
"""
from __future__ import annotations

import re
import urllib.parse

from ..util import baixar_json, limpar_html, sem_acento

NOME = "Adzuna (agregador privado)"
URL = ("https://api.adzuna.com/v1/api/jobs/{pais}/search/1?app_id={id}&app_key={key}"
       "&results_per_page=50&what={termo}&max_days_old={dias}&content-type=application/json")

POSITIVO = [r"visa sponsor", r"sponsorship (is )?(available|provided|offered)", r"will sponsor",
            r"\blmia\b", r"h-?2b", r"international (applicants|candidates) (welcome|accepted)",
            r"temporary foreign worker", r"\btfw\b", r"open to foreign"]
NEGATIVO = [r"no (visa )?sponsorship", r"not (able to )?sponsor", r"unable to sponsor",
            r"must be (legally )?(authorized|eligible) to work", r"citizens? (and|or) permanent residents? only"]


def coletar(cfg: dict, log) -> list[dict]:
    if not cfg.get("app_id") or not cfg.get("app_key"):
        log("Adzuna desativado: falta app_id/app_key em config/fontes.json.")
        return []
    vagas = []
    for pais in cfg.get("paises", ["us", "ca"]):
        for termo in cfg.get("termos", []):
            url = URL.format(pais=pais, id=cfg["app_id"], key=cfg["app_key"],
                             termo=urllib.parse.quote_plus(termo), dias=cfg.get("dias", 21))
            try:
                dados = baixar_json(url, timeout=45)
            except Exception as e:  # noqa: BLE001
                log(f"Adzuna {pais} '{termo}': falhou ({e})")
                continue
            for r in dados.get("results", []):
                desc = limpar_html(r.get("description", ""))
                t = sem_acento(f"{r.get('title','')} {desc}")
                aceita = None
                if any(re.search(p, t) for p in NEGATIVO):
                    aceita = 0
                elif any(re.search(p, t) for p in POSITIVO):
                    aceita = 1
                smin = r.get("salary_min")
                hora = None
                if smin:
                    hora = round(smin / 2080, 2) if smin > 1000 else smin
                loc = r.get("location", {}).get("area", [])
                vagas.append({
                    "id": f"adzuna:{r.get('id')}", "fonte": NOME, "pais": pais.upper(),
                    "programa": "Privado – confirmar patrocínio",
                    "titulo": limpar_html(r.get("title", "")),
                    "empresa": (r.get("company") or {}).get("display_name", ""),
                    "cidade": loc[-1] if loc else "", "estado": loc[1] if len(loc) > 1 else "",
                    "salario_txt": f"{smin:.0f}+" if smin else "", "salario_hora": hora,
                    "moeda": "USD" if pais == "us" else "CAD",
                    "data_publicacao": (r.get("created") or "")[:10], "url": r.get("redirect_url"),
                    "como_aplicar": "Pelo link do anúncio. Pergunte se patrocinam visto ANTES de enviar documentos.",
                    "aceita_estrangeiro": aceita, "lmia": None, "codigo_ocupacao": "",
                    "descricao": desc[:2000],
                })
            log(f"Adzuna {pais} '{termo}': {len(dados.get('results', []))} resultados.")
    return vagas
