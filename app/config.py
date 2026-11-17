"""Perfil do candidato e configuração das fontes (arquivos em config/)."""
from __future__ import annotations

import copy

from .util import PASTA_CONFIG, ler_json, salvar_json

ARQ_PERFIL = PASTA_CONFIG / "perfil.json"
ARQ_FONTES = PASTA_CONFIG / "fontes.json"

PERFIL_PADRAO = {
    "nome": "",
    "email": "",
    "telefone": "",
    "cidade": "",
    "estado": "",
    "pais_cidadania": "Brasil",
    "idade": None,
    "estado_civil": "solteiro",          # solteiro | casado | uniao_estavel
    "conjuge": {"profissao": "", "ingles": "nao_informado", "escolaridade": "", "experiencia_anos": None},
    "filhos": [],                         # [{"idade": 5}, ...]
    "renda_mensal_brl": None,
    "reserva_financeira_brl": None,
    "ingles": "nao_informado",            # nenhum | basico | intermediario | avancado | fluente
    "frances": "nenhum",
    "teste_idioma": {"tipo": "", "clb_estimado": None, "data": ""},
    "escolaridade": {"nivel": "medio", "curso": "", "instituicao": "", "previsao_conclusao": ""},
    "experiencias": [],                   # [{"categoria": "construcao", "cargo": "...", "anos": 2, "empresa": "", "comprovavel": true}]
    "cursos": [],                         # [{"categoria": "soldagem", "nome": "...", "instituicao": "", "horas": 160, "processos": "MIG, eletrodo"}]
    "passaportes_familia_ok": None,
    "paises_interesse": ["EUA", "Canada"],
    "preferencias": {"score_minimo": 40, "so_aceita_estrangeiro": True},
}

FONTES_PADRAO = {
    "dol_h2b": {"ativo": True, "dias_tentar": 5},
    "jobbank": {
        "ativo": True,
        "dias": 14,
        "max_checagens_por_execucao": 100,
        "termos": [
            "welder", "welder helper", "welder fitter", "metal fabricator",
            "construction labourer", "construction helper", "general labourer",
            "electrician", "plumber", "construction trades helper", "carpenter helper",
            "maintenance worker", "janitor", "farm worker",
        ],
    },
    "lmia": {"ativo": True, "trimestres": 4,
             "categorias": ["soldagem", "construcao", "eletrica", "hidraulica", "servicos_gerais", "producao"]},
    "perm": {"ativo": True,
             "categorias": ["soldagem", "construcao", "eletrica", "hidraulica", "servicos_gerais", "producao"]},
    "aip": {"ativo": True, "dias_entre_atualizacoes": 7},
    "telegram": {"ativo": False, "token": "", "chat_id": "", "nota_minima": 60},
    "adzuna": {"ativo": False, "app_id": "", "app_key": "", "paises": ["us", "ca"], "dias": 21,
               "termos": ["welder visa sponsorship", "welder LMIA", "construction labourer LMIA",
                          "H-2B construction"]},
}


def _mesclar(base: dict, novo: dict) -> dict:
    saida = copy.deepcopy(base)
    for k, v in (novo or {}).items():
        if isinstance(v, dict) and isinstance(saida.get(k), dict):
            saida[k] = _mesclar(saida[k], v)
        else:
            saida[k] = v
    return saida


def carregar_perfil() -> dict:
    return _mesclar(PERFIL_PADRAO, ler_json(ARQ_PERFIL, {}) or {})


def salvar_perfil(p: dict) -> dict:
    p = _mesclar(PERFIL_PADRAO, p)
    salvar_json(ARQ_PERFIL, p)
    return p


def carregar_fontes() -> dict:
    return _mesclar(FONTES_PADRAO, ler_json(ARQ_FONTES, {}) or {})


def salvar_fontes(f: dict) -> dict:
    f = _mesclar(FONTES_PADRAO, f)
    salvar_json(ARQ_FONTES, f)
    return f


def garantir_arquivos() -> None:
    if not ARQ_FONTES.exists():
        salvar_json(ARQ_FONTES, FONTES_PADRAO)
    if not ARQ_PERFIL.exists():
        salvar_json(ARQ_PERFIL, PERFIL_PADRAO)
