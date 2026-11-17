"""Mapa de ocupações: liga palavras-chave e códigos oficiais (SOC dos EUA e
NOC 2021 do Canadá) às áreas de experiência do perfil."""
from __future__ import annotations

import re

from .util import sem_acento

CATEGORIAS = {
    "soldagem": {
        "nome": "Soldagem / caldeiraria",
        "en": "Welder",
        "palavras": [r"\bweld", r"soudeu", r"soudage", r"\bfitter\b", r"metal fabricat",
                     r"boilermaker", r"brazer", r"\bmig\b", r"\btig\b", r"\bsmaw\b", r"\bfcaw\b"],
        "soc": ["51-4121", "51-4122", "47-2011", "51-2041"],
        "noc": ["72106", "72105", "72102", "94105"],
    },
    "construcao": {
        "nome": "Construção civil",
        "en": "Construction Labourer",
        "palavras": [r"construction (labo|help|work)", r"general labo", r"labou?rer", r"concrete",
                     r"cement", r"mason", r"drywall", r"roofer", r"framer", r"carpent",
                     r"demolition", r"scaffold", r"paver", r"manoeuvre", r"aide de chantier",
                     r"trades? helper", r"helpers?.{0,20}(brick|carpent|construction)"],
        "soc": ["47-2061", "47-2051", "47-2031", "47-2181", "47-2081", "47-3011",
                "47-3012", "47-3016", "47-3019", "47-2071", "47-4051", "47-2021"],
        "noc": ["75110", "73100", "73101", "72310", "73110", "73112", "75119", "73113"],
    },
    "eletrica": {
        "nome": "Elétrica",
        "en": "Electrician Helper",
        "palavras": [r"electric", r"electrici", r"wiring", r"lineman", r"lineworker"],
        "soc": ["47-3013", "47-2111", "49-9051"],
        "noc": ["72200", "72201", "72203"],
    },
    "hidraulica": {
        "nome": "Hidráulica / encanamento",
        "en": "Plumber Helper",
        "palavras": [r"plumb", r"pipefit", r"steamfit", r"pipe ?layer", r"sprinkler fit", r"plombier"],
        "soc": ["47-3015", "47-2152", "47-2151"],
        "noc": ["72300", "72301", "72302"],
    },
    "servicos_gerais": {
        "nome": "Serviços gerais / manutenção / limpeza",
        "en": "General Maintenance Worker",
        "palavras": [r"janitor", r"custodian", r"cleaner", r"housekeep", r"maintenance (worker|tech|helper)",
                     r"groundskeep", r"landscap", r"handyman", r"general maintenance", r"concierge",
                     r"\bporter\b", r"entretien"],
        "soc": ["37-2011", "37-2012", "37-3011", "49-9071", "37-3012", "37-3013"],
        "noc": ["65310", "65312", "85121", "73201", "75114"],
    },
    "producao": {
        "nome": "Produção / indústria / armazém",
        "en": "Production Worker",
        "palavras": [r"production (worker|labo|associate)", r"machine operator", r"assembl", r"factory",
                     r"warehouse", r"material handler", r"forklift", r"labou?rers? in .*processing",
                     r"meat (cutter|processing)", r"fish processing", r"packer", r"sawmill"],
        "soc": ["51-9198", "51-2090", "53-7062", "53-7064", "53-7051", "51-3022", "51-3023",
                "51-9111", "51-4031"],
        "noc": ["94141", "95100", "95103", "95106", "95107", "95109", "94142", "75101", "94143"],
    },
    "agricultura": {
        "nome": "Agricultura",
        "en": "Farm Worker",
        "palavras": [r"\bfarm", r"harvest", r"greenhouse", r"nursery", r"orchard", r"crop", r"livestock",
                     r"dairy", r"ouvrier agricole"],
        "soc": ["45-2092", "45-2093", "45-2091", "45-2041"],
        "noc": ["85100", "85101", "85103", "84120"],
    },
    "hotelaria": {
        "nome": "Hotelaria / alimentação",
        "en": "Hospitality Worker",
        "palavras": [r"\bcook\b", r"dishwash", r"kitchen", r"food (service|counter)", r"server",
                     r"housekeeping attendant", r"room attendant", r"amusement", r"recreation attendant",
                     r"lifeguard"],
        "soc": ["35-2014", "35-2021", "35-9021", "35-3023", "35-2012", "39-3091", "37-2012"],
        "noc": ["65200", "65201", "63200", "65210", "65211", "64314"],
    },
    "ti": {
        "nome": "Tecnologia da informação",
        "en": "IT / Software",
        "palavras": [r"software", r"developer", r"programmer", r"it support", r"help ?desk",
                     r"computer", r"data analyst", r"web develop", r"network tech"],
        "soc": ["15-1252", "15-1232", "15-1211", "15-1254", "15-1244"],
        "noc": ["21231", "21232", "21234", "22220", "22221", "21222"],
    },
}

ORDEM = list(CATEGORIAS)

# NOC 2021: 2º dígito = TEER. Lista de TEER 2/3 elegíveis para que o cônjuge
# receba open work permit (regra de 21/jan/2025; confirmar no site do IRCC).
PREFIXOS_SOWP_TEER23 = ("22", "32", "33", "72", "73", "82", "83")


def teer_do_noc(noc: str | None) -> int | None:
    if not noc:
        return None
    m = re.search(r"\b(\d{5})\b", str(noc))
    if not m:
        return None
    return int(m.group(1)[1])


def conjuge_pode_trabalhar_canada(noc: str | None) -> bool | None:
    """Regra geral do spousal open work permit (SOWP) para trabalhadores."""
    m = re.search(r"\b(\d{5})\b", str(noc or ""))
    if not m:
        return None
    codigo = m.group(1)
    teer = int(codigo[1])
    if teer in (0, 1):
        return True
    if teer in (2, 3):
        return codigo.startswith(PREFIXOS_SOWP_TEER23)
    return False


def classificar(titulo: str = "", codigo: str = "", texto: str = "") -> str | None:
    """Devolve a chave da categoria mais provável, ou None."""
    cod = (codigo or "").strip()
    if cod:
        cod5 = re.search(r"\d{5}", cod)
        socm = re.search(r"\d{2}-\d{4}", cod)
        for chave, c in CATEGORIAS.items():
            if socm and any(socm.group(0).startswith(s[:7]) for s in c["soc"]):
                return chave
            if cod5 and cod5.group(0) in c["noc"]:
                return chave
    alvo = sem_acento(f"{titulo} {codigo}")
    for chave in ORDEM:
        if any(re.search(p, alvo) for p in CATEGORIAS[chave]["palavras"]):
            return chave
    if texto:
        alvo2 = sem_acento(texto[:600])
        for chave in ORDEM:
            if any(re.search(p, alvo2) for p in CATEGORIAS[chave]["palavras"]):
                return chave
    if cod:
        socm = re.search(r"(\d{2})-\d{4}", cod)
        if socm:
            prefixo = socm.group(1)
            return {"47": "construcao", "51": "producao", "53": "producao", "37": "servicos_gerais",
                    "45": "agricultura", "35": "hotelaria", "15": "ti", "49": "servicos_gerais"}.get(prefixo)
    return None


def nome_categoria(chave: str | None) -> str:
    return CATEGORIAS.get(chave or "", {}).get("nome", "Outra área")
