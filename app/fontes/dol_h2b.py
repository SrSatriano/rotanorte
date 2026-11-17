"""EUA – vagas H-2B oficiais do Departamento do Trabalho (SeasonalJobs.dol.gov).

Toda vaga desta fonte é de um empregador que pediu certificação para
contratar trabalhadores ESTRANGEIROS temporários (visto H-2B). O feed
oficial em JSON traz os pedidos aceitos pelo DOL nos últimos 20 dias e é
atualizado diariamente.
Feed: https://seasonaljobs.dol.gov/feeds
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import zipfile

from ..util import baixar, ErroRede

NOME = "EUA · H-2B (Dept. of Labor)"
URL_FEED = "https://api.seasonaljobs.dol.gov/datahub-search/sjCaseData/zip/h2b/{data}"
URL_VAGA = "https://seasonaljobs.dol.gov/jobs/{caso}"


# ------------------------------------------------------------ leitura tolerante
def _achatar(obj, prefixo="", saida=None):
    """Transforma JSON aninhado em {caminho_em_minusculas: valor}."""
    if saida is None:
        saida = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            _achatar(v, f"{prefixo}{str(k).lower()}.", saida)
    elif isinstance(obj, list):
        if obj and all(not isinstance(x, (dict, list)) for x in obj):
            saida[prefixo.rstrip(".")] = ", ".join(str(x) for x in obj if x not in (None, ""))
        else:
            for i, v in enumerate(obj[:5]):
                _achatar(v, f"{prefixo}{i}.", saida)
    else:
        if obj not in (None, ""):
            saida[prefixo.rstrip(".")] = obj
    return saida


def _chave_limpa(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", k.split(".")[-1])


def _pegar(plano: dict, candidatos: list[str], evitar: tuple = ()) -> str:
    """Procura o primeiro campo cujo nome (sem _ . -) bate com algum candidato."""
    indice = {}
    for k, v in plano.items():
        ck = _chave_limpa(k)
        if any(e in k.replace("_", "") for e in evitar):
            continue
        indice.setdefault(ck, v)
    for c in candidatos:
        c2 = re.sub(r"[^a-z0-9]", "", c.lower())
        if c2 in indice:
            return str(indice[c2]).strip()
    # busca parcial (contém)
    for c in candidatos:
        c2 = re.sub(r"[^a-z0-9]", "", c.lower())
        for ck, v in indice.items():
            if c2 and c2 in ck:
                return str(v).strip()
    return ""


def _registros(dados) -> list[dict]:
    if isinstance(dados, list):
        return [d for d in dados if isinstance(d, dict)]
    if isinstance(dados, dict):
        for chave in ("data", "records", "results", "cases", "items", "hits", "content"):
            if isinstance(dados.get(chave), list):
                return _registros(dados[chave])
            if isinstance(dados.get(chave), dict):
                r = _registros(dados[chave])
                if r:
                    return r
        # dicionário de casos {numero: {...}}
        valores = list(dados.values())
        if valores and all(isinstance(v, dict) for v in valores):
            return valores
        return [dados]
    return []


def _ler_pacote(conteudo: bytes) -> list[dict]:
    registros: list[dict] = []
    if conteudo[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            for nome in z.namelist():
                if nome.lower().endswith(".json"):
                    texto = z.read(nome).decode("utf-8", "replace")
                    registros.extend(_ler_json_texto(texto))
    else:
        registros.extend(_ler_json_texto(conteudo.decode("utf-8", "replace")))
    return registros


def _ler_json_texto(texto: str) -> list[dict]:
    texto = texto.strip()
    if not texto:
        return []
    try:
        return _registros(json.loads(texto))
    except json.JSONDecodeError:
        # pode ser JSON por linha
        saida = []
        for linha in texto.splitlines():
            linha = linha.strip().rstrip(",")
            if linha.startswith("{"):
                try:
                    saida.extend(_registros(json.loads(linha)))
                except json.JSONDecodeError:
                    pass
        return saida


def _numero(txt: str) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", (txt or "").replace(",", ""))
    return float(m.group(0)) if m else None


def _por_hora(valor: float | None, periodo: str) -> float | None:
    if valor is None:
        return None
    p = (periodo or "").lower()
    if p.startswith(("y", "a")) or "year" in p:
        return round(valor / 2080, 2)
    if p.startswith("m") and "month" in p:
        return round(valor / 173, 2)
    if p.startswith("w"):
        return round(valor / 40, 2)
    if valor > 200:  # provavelmente anual
        return round(valor / 2080, 2)
    return valor


MESES = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                        "oct", "nov", "dec"], 1)}


def _data_iso(txt: str) -> str:
    """'01-Jan-2027' / '2026-11-06T20:37:56Z' / '01/15/2027' -> '2027-01-01'."""
    t = (txt or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return m.group(0)
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", t)
    if m and m.group(2).lower() in MESES:
        return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def _util(v: str) -> str:
    return "" if (v or "").strip().upper() in ("N/A", "NA", "NONE", "0", "") else v.strip()


EVITAR = ("poc", "atty", "attorney", "agent", "lawfirm", "recruiters", "employmentlocations")


def converter(rec: dict) -> dict | None:
    p = _achatar(rec)
    caso = _pegar(p, ["case_number", "casenumber", "case_no", "caseno", "etacasenumber", "case_id"])
    if not caso:
        for v in p.values():
            if isinstance(v, str) and re.fullmatch(r"H-\d{3}-\d{5}-\d{6}", v.strip()):
                caso = v.strip()
                break
    titulo = _pegar(p, ["tempneedjobtitle", "job_title", "jobtitle", "title"], evitar=EVITAR + ("soc",))
    if not titulo:
        return None
    empresa = _pegar(p, ["empbusinessname", "employer_business_name", "employer_name", "employername",
                         "legal_business_name", "business_name", "trade_name", "tradename", "dba"],
                     evitar=EVITAR)
    cidade = _pegar(p, ["jobcity", "worksite_city", "worksitecity", "job_city", "empcity", "city"], evitar=EVITAR)
    estado = _pegar(p, ["jobstate", "worksite_state", "worksitestate", "job_state", "empstate", "state"], evitar=EVITAR)
    soc = _pegar(p, ["tempneedsoc", "soc_code", "soccode", "onet_code", "soc"], evitar=EVITAR + ("title",))
    soc_titulo = _pegar(p, ["tempneedsoctitle", "soc_title", "soctitle", "onet_title"], evitar=EVITAR)
    salario = _pegar(p, ["wagefrom", "wage_offered_from", "wageofferedfrom", "basic_wage_rate", "basic_rate",
                         "hourly_rate", "wage_rate"], evitar=EVITAR)
    salario_ate = _pegar(p, ["wageto", "wage_offered_to", "wageofferedto"], evitar=EVITAR)
    periodo = _pegar(p, ["wageper", "wage_per", "pay_period", "wage_unit"], evitar=EVITAR)
    inicio = _pegar(p, ["tempneedstart", "begin_date", "begindate", "employment_begin_date", "job_begin_date",
                        "start_date", "startdate"], evitar=EVITAR)
    fim = _pegar(p, ["tempneedend", "end_date", "enddate", "employment_end_date", "job_end_date"], evitar=EVITAR)
    qtd = _pegar(p, ["tempneedwkrpos", "total_workers_needed", "totalworkersneeded", "total_workers",
                     "workers_requested", "number_of_workers"], evitar=EVITAR)
    deveres = _pegar(p, ["jobduties", "job_duties", "duties", "job_description"], evitar=EVITAR)
    email = _util(_pegar(p, ["recapplyemail", "recruit_email", "apply_email", "applyemail"], evitar=EVITAR))
    tel = _util(_pegar(p, ["recapplyphone", "recruit_phone", "apply_phone", "applyphone"], evitar=EVITAR))
    site = _util(_pegar(p, ["recapplyurl", "apply_url", "applyurl"], evitar=EVITAR))
    postado = _pegar(p, ["dateacceptanceltrissued", "date_posted", "dateposted", "noa_date", "noadate",
                         "dateapplicationsubmitted"], evitar=EVITAR)
    exp_meses = _pegar(p, ["jobminexpmonths"])
    moradia = _pegar(p, ["recislodging"])
    transporte = _pegar(p, ["recisdailytransport"])
    requisitos_esp = _pegar(p, ["jobminspecialreq"])

    # recrutadores no exterior (Appendix C) e outros locais de trabalho (Appendix A)
    recrutadores, paises = [], []
    for i in range(5):
        org = str(p.get(f"recruiters.{i}.apdxcrecorg", "")).strip()
        pais = str(p.get(f"recruiters.{i}.apdxcreccountry", "")).strip()
        if org or pais:
            recrutadores.append(f"{org} ({pais.title()})" if pais else org)
            if pais and pais.title() not in paises:
                paises.append(pais.title())
    outros_locais = []
    for i in range(5):
        c = p.get(f"employmentlocations.{i}.apdxacity")
        e = p.get(f"employmentlocations.{i}.apdxastate")
        if c:
            outros_locais.append(f"{str(c).title()}, {e}")

    # sanidade: a busca tolerante pode pegar campos errados
    if len(estado) > 20:
        estado = ""
    if len(cidade) > 50:
        cidade = ""
    if not re.match(r"(?i)(hour|hr|week|bi-?week|month|year|annual|day|piece)", periodo or ""):
        periodo = ""
    if _numero(salario) is None:
        salario = ""
    titulo = titulo[:150]
    v_hora = _por_hora(_numero(salario), periodo)
    sal_txt = ""
    if salario:
        sal_txt = f"US$ {salario}" + (f" – {salario_ate}" if salario_ate and salario_ate != salario else "")
        sal_txt += f" / {periodo.lower()}" if periodo else ""

    aplicar = []
    if email:
        aplicar.append(f"E-mail: {email}")
    if tel:
        aplicar.append(f"Telefone: {tel}")
    if site:
        aplicar.append(f"Site: {site}")
    if recrutadores:
        aplicar.append("Recrutadores no exterior informados ao governo: " + "; ".join(recrutadores))
    aplicar.append("Confira 'Recruitment Information' na página oficial da vaga antes de enviar.")

    extras = []
    if exp_meses not in ("", None):
        n = _numero(str(exp_meses))
        extras.append("Experiência mínima: " + ("não exige" if not n else f"{n:g} meses"))
    if str(moradia) == "1":
        extras.append("Empregador oferece/ajuda com moradia (veja custos no anúncio)")
    if str(transporte) == "1":
        extras.append("Transporte diário oferecido")
    if outros_locais:
        extras.append("Também trabalha em: " + "; ".join(outros_locais))
    if requisitos_esp:
        extras.append("Requisitos especiais: " + requisitos_esp[:400])
    descricao = "\n".join(extras + ([""] if extras else []) + [(deveres or "")[:2500]])

    ident = caso or f"{empresa}-{titulo}-{inicio}"
    return {
        "id": f"h2b:{ident}",
        "fonte": NOME,
        "pais": "US",
        "programa": "H-2B (temporário/sazonal)",
        "titulo": titulo.title() if titulo.isupper() else titulo,
        "empresa": empresa.title() if empresa.isupper() else empresa,
        "cidade": cidade.title() if (cidade.isupper() or cidade.islower()) else cidade,
        "estado": estado,
        "salario_txt": sal_txt,
        "salario_hora": v_hora,
        "moeda": "USD",
        "data_publicacao": _data_iso(postado),
        "data_inicio": _data_iso(inicio),
        "data_fim": _data_iso(fim),
        "vagas_qtd": int(_numero(qtd)) if _numero(qtd) else None,
        "url": URL_VAGA.format(caso=caso) if caso else "https://seasonaljobs.dol.gov/",
        "como_aplicar": "\n".join(aplicar),
        "aceita_estrangeiro": 1,
        "lmia": None,
        "codigo_ocupacao": f"{soc} {soc_titulo}".strip(),
        "descricao": descricao,
        "extras": {"exp_min_meses": _numero(str(exp_meses)) if exp_meses not in ("", None) else None,
                   "moradia": str(moradia) == "1", "paises_recrutamento": paises},
    }


def coletar(cfg: dict, log) -> list[dict]:
    dias = int(cfg.get("dias_tentar", 5))
    hoje_leste = (dt.datetime.utcnow() - dt.timedelta(hours=5)).date()
    ultimo_erro = None
    for d in range(dias):
        data = (hoje_leste - dt.timedelta(days=d)).isoformat()
        url = URL_FEED.format(data=data)
        try:
            log(f"Baixando feed oficial H-2B de {data}…")
            conteudo = baixar(url, timeout=180)
        except ErroRede as e:
            ultimo_erro = e
            continue
        regs = _ler_pacote(conteudo)
        vagas = [v for v in (converter(r) for r in regs) if v]
        log(f"H-2B: {len(regs)} registros lidos, {len(vagas)} vagas válidas.")
        if vagas:
            return vagas
    raise ErroRede(f"Não consegui baixar o feed H-2B dos últimos {dias} dias. Último erro: {ultimo_erro}")
