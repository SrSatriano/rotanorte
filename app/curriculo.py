"""Gera currículo (resume) e carta de apresentação em inglês, no padrão EUA/Canadá.

Padrão norte-americano: sem foto, sem idade, sem estado civil, sem CPF.
O texto das funções vem de uma biblioteca de frases em inglês por área –
revise e ajuste para que tudo seja verdadeiro sobre você.
"""
from __future__ import annotations

import html
from datetime import date

from .ocupacoes import CATEGORIAS

FRASES = {
    "soldagem": [
        "Performed welding and cutting on carbon steel components following drawings and supervisor instructions",
        "Prepared joints by grinding, fitting and tack welding; inspected welds for defects",
        "Operated welding equipment safely, using PPE and following shop safety procedures",
    ],
    "construcao": [
        "Supported construction crews with site preparation, material handling and clean-up",
        "Mixed and poured concrete, assisted with masonry, framing and finishing work",
        "Operated hand and power tools safely; followed site safety rules and supervisor instructions",
    ],
    "eletrica": [
        "Assisted electricians with installation of conduit, wiring, outlets, switches and lighting",
        "Pulled cable, prepared materials and kept the work area organized and safe",
        "Helped troubleshoot basic electrical issues under supervision",
    ],
    "hidraulica": [
        "Assisted plumbers with installation and repair of water supply and drainage pipes",
        "Cut, threaded and fitted PVC and metal pipes; helped install fixtures",
        "Dug trenches, moved materials and maintained tools and the job site",
    ],
    "servicos_gerais": [
        "Performed general maintenance and cleaning of buildings and outdoor areas",
        "Carried out minor repairs (painting, fixtures, small electrical and plumbing fixes)",
        "Moved and organized materials and equipment; followed safety and cleaning procedures",
    ],
    "producao": [
        "Operated production equipment and met daily output and quality targets",
        "Loaded, unloaded and organized materials; kept the work area clean and safe",
    ],
    "agricultura": [
        "Performed planting, harvesting and general farm duties in all weather conditions",
        "Operated basic farm equipment and handled materials safely",
    ],
    "hotelaria": [
        "Supported kitchen/housekeeping operations, following hygiene and safety standards",
    ],
    "ti": [
        "Developed academic software projects and provided basic IT support",
    ],
}

TITULOS_EN = {
    "soldagem": "Welder", "construcao": "Construction Labourer", "eletrica": "Electrician Helper",
    "hidraulica": "Plumber Helper", "servicos_gerais": "General Maintenance Worker",
    "producao": "Production Worker", "agricultura": "Farm Worker", "hotelaria": "Hospitality Worker",
    "ti": "IT Assistant",
}

INGLES_EN = {"nenhum": "Beginner (studying)", "basico": "Basic (studying)", "intermediario": "Intermediate",
             "avancado": "Advanced", "fluente": "Fluent", "nao_informado": "Studying"}

ESCOLARIDADE_EN = {
    "fundamental": "Elementary School", "medio": "High School Diploma",
    "tecnico": "Technical Diploma", "superior_cursando": "Bachelor's Degree (in progress)",
    "superior_completo": "Bachelor's Degree", "pos": "Postgraduate Degree",
}

CURSO_EN = {"ciencia da computacao": "Computer Science", "ciência da computação": "Computer Science"}

HABILIDADES = {
    "soldagem": ["Welding (MIG/GMAW, stick/SMAW – adjust to your real processes)", "Blueprint reading (basic)",
                 "Grinding and cutting", "Measuring and fitting"],
    "construcao": ["Concrete and masonry support", "Hand and power tools", "Material handling"],
    "eletrica": ["Residential wiring support", "Conduit and cable pulling"],
    "hidraulica": ["Pipe cutting and fitting (PVC/metal)", "Fixture installation support"],
    "servicos_gerais": ["Building maintenance", "Painting and minor repairs", "Cleaning procedures"],
}


def _e(t) -> str:
    return html.escape(str(t or ""))


def _uso_pais(pais: str) -> str:
    return "Canada" if pais == "CA" else "United States"


ESTILO = """
<style>
 body{font-family:Calibri,Arial,sans-serif;max-width:780px;margin:24px auto;color:#111;line-height:1.35;padding:0 18px}
 h1{margin:0;font-size:26px} .contato{color:#333;margin:4px 0 14px}
 h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;border-bottom:1.5px solid #222;padding-bottom:2px;margin:18px 0 6px}
 ul{margin:4px 0 8px 18px;padding:0} li{margin:2px 0}
 .linha{display:flex;justify-content:space-between;font-weight:bold}
 .aviso{background:#fff4d6;border:1px solid #e3b341;padding:8px 10px;font-size:13px;margin-bottom:16px;font-family:Arial}
 @media print{.aviso{display:none} body{margin:0}}
</style>"""


def gerar_curriculo(perfil: dict, vaga: dict | None = None) -> str:
    vaga = vaga or {}
    cat_alvo = vaga.get("categoria")
    titulo_alvo = vaga.get("titulo") or TITULOS_EN.get(cat_alvo or "", "")
    if not titulo_alvo:
        cats = [e.get("categoria") for e in perfil.get("experiencias", [])] + \
               [c.get("categoria") for c in perfil.get("cursos", [])]
        titulo_alvo = " / ".join(dict.fromkeys(TITULOS_EN[c] for c in cats if c in TITULOS_EN)) or "General Labourer"
    pais = vaga.get("pais") or "CA"
    titulo_alvo = " ".join(w[:1].upper() + w[1:] for w in str(titulo_alvo).split())

    contato = " · ".join(x for x in [
        f"{perfil.get('cidade','')}, {perfil.get('estado','')}, Brazil".strip(", "),
        perfil.get("telefone"), perfil.get("email")] if x)

    # Ordena experiências: primeiro a área da vaga
    exps = sorted(perfil.get("experiencias") or [],
                  key=lambda e: (e.get("categoria") != cat_alvo, -(float(e.get("anos") or 0))))

    resumo_partes = []
    anos_total = sum(float(e.get("anos") or 0) for e in exps)
    if anos_total:
        resumo_partes.append(f"Hard-working tradesperson with {anos_total:.0f}+ years of hands-on experience in "
                             + ", ".join(dict.fromkeys(CATEGORIAS[e['categoria']]['en'].lower()
                                                       for e in exps if e.get('categoria') in CATEGORIAS)) + ".")
    else:
        resumo_partes.append("Hard-working, reliable worker with hands-on experience in construction trades and maintenance.")
    if any(c.get("categoria") == "soldagem" for c in perfil.get("cursos", [])):
        resumo_partes.append("Trained welder seeking to grow in welding and metal fabrication.")
    resumo_partes.append(f"Seeking a position as {titulo_alvo} in {_uso_pais(pais)}; available to relocate.")
    resumo_partes.append("Safety-minded, punctual and quick to learn.")

    h = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Resume – "
         + _e(perfil.get("nome") or "Candidate") + "</title>" + ESTILO + "</head><body>"]
    h.append("<div class='aviso'><b>RotaNorte:</b> revise TUDO antes de enviar. Apague o que não for verdade e "
             "ajuste processos de solda, datas e empresas. Para salvar em PDF: Ctrl+P → 'Salvar como PDF'. "
             "Este aviso não sai na impressão.</div>")
    h.append(f"<h1>{_e(perfil.get('nome') or '[YOUR NAME]')}</h1>")
    h.append(f"<div class='contato'>{_e(contato)}</div>")
    h.append(f"<h2>Objective</h2><p>{_e(' '.join(resumo_partes))}</p>")

    habilidades = []
    for c in dict.fromkeys([cat_alvo] + [e.get("categoria") for e in exps] + [c.get("categoria") for c in perfil.get("cursos", [])]):
        habilidades += HABILIDADES.get(c or "", [])
    habilidades = list(dict.fromkeys(habilidades))[:9] + ["Workplace safety and PPE", "Teamwork and following instructions"]
    h.append("<h2>Skills</h2><ul>" + "".join(f"<li>{_e(x)}</li>" for x in habilidades) + "</ul>")

    if exps:
        h.append("<h2>Work Experience</h2>")
        for e in exps:
            cat = e.get("categoria")
            cargo = e.get("cargo_en") or TITULOS_EN.get(cat, e.get("cargo", ""))
            periodo = e.get("periodo") or (f"{e['anos']:g} year(s)" if e.get("anos") not in (None, "") else "")
            empresa = e.get("empresa") or ""
            onde = f"{empresa}, Brazil" if empresa else "Brazil"
            h.append(f"<div class='linha'><span>{_e(cargo)} – {_e(onde)}</span><span>{_e(periodo)}</span></div>")
            h.append("<ul>" + "".join(f"<li>{_e(x)}</li>" for x in FRASES.get(cat, [])) + "</ul>")

    cursos = perfil.get("cursos") or []
    esc = perfil.get("escolaridade") or {}
    h.append("<h2>Education &amp; Training</h2><ul>")
    for c in cursos:
        nome = "Welding Course" if c.get("categoria") == "soldagem" else (c.get("nome_en") or c.get("nome", ""))
        extra = []
        if c.get("horas"):
            extra.append(f"{c['horas']} hours")
        if c.get("processos"):
            extra.append(f"processes: {c['processos']}")
        if c.get("instituicao"):
            extra.append(c["instituicao"])
        h.append(f"<li><b>{_e(nome)}</b>{(' – ' + _e(', '.join(extra))) if extra else ''}</li>")
    if esc.get("nivel"):
        curso = CURSO_EN.get((esc.get("curso") or "").lower(), esc.get("curso") or "")
        txt = ESCOLARIDADE_EN.get(esc["nivel"], "")
        if curso:
            txt += f" in {curso}"
        if esc.get("previsao_conclusao") and esc["nivel"] == "superior_cursando":
            txt += f" – expected {esc['previsao_conclusao']}"
        if esc.get("instituicao"):
            txt += f", {esc['instituicao']}"
        h.append(f"<li>{_e(txt)}</li>")
    h.append("</ul>")

    h.append("<h2>Languages</h2><ul><li>Portuguese – Native</li>"
             f"<li>English – {_e(INGLES_EN.get(perfil.get('ingles') or 'nao_informado'))}</li></ul>")
    h.append("<h2>Work Authorization</h2><p>Brazilian citizen. Requires employer-supported work permit/visa "
             + ("(e.g., LMIA-based work permit)." if pais == "CA" else "(e.g., H-2B).")
             + " Valid passport. Available to start as soon as the work authorization is approved.</p>")
    h.append("<h2>References</h2><p>Available upon request.</p></body></html>")
    return "".join(h)


def texto_carta(perfil: dict, vaga: dict) -> tuple[str, str]:
    """Devolve (assunto, corpo) da carta em texto puro – serve para e-mail."""
    nome = perfil.get("nome") or "[Your Name]"
    titulo = " ".join(w[:1].upper() + w[1:] for w in (vaga.get("titulo") or "[Job Title]").split())
    empresa = vaga.get("empresa") or "[Company]"
    local = ", ".join(x for x in [vaga.get("cidade"), vaga.get("estado")] if x)
    cat = vaga.get("categoria")
    exps = [e for e in perfil.get("experiencias") or [] if e.get("categoria") == cat]
    anos = sum(float(e.get("anos") or 0) for e in exps)
    if anos:
        exp_txt = f"I have {anos:g} year(s) of hands-on experience in this type of work in Brazil"
    elif any(c.get("categoria") == cat for c in perfil.get("cursos", [])):
        exp_txt = "I completed professional training in this field and have practical experience in construction trades"
    else:
        exp_txt = "I have practical experience in construction, electrical and plumbing support and general maintenance"
    programa = "an LMIA-supported work permit" if vaga.get("pais") == "CA" else "the H-2B temporary worker program"
    ref = f" (Job Bank #{vaga['id'].split(':',1)[1]})" if str(vaga.get("id", "")).startswith("jobbank:") else ""
    caso = f" (ETA case {vaga['id'].split(':',1)[1]})" if str(vaga.get("id", "")).startswith("h2b:") else ""
    hoje = date.today().strftime("%B %d, %Y")
    assunto = f"Application for {titulo}{ref}{caso} – {nome}"
    corpo = f"""Dear Hiring Manager,

I am writing to apply for the {titulo} position at {empresa}. {exp_txt}, and I am used to physical work, following safety rules and working as part of a team.

I am a Brazilian citizen and I understand this position is open to international candidates through {programa}. I am ready to complete all steps of the process, including any practical test, and I can start as soon as my work authorization is approved.

I would appreciate the opportunity to show my skills. Thank you for your time and consideration.

Sincerely,
{nome}
{perfil.get('telefone') or ''}  {perfil.get('email') or ''}

(Resume attached.)
"""
    return assunto, corpo.strip() + "\n"


def gerar_carta(perfil: dict, vaga: dict) -> str:
    assunto, corpo = texto_carta(perfil, vaga)
    empresa = vaga.get("empresa") or "[Company]"
    local = ", ".join(x for x in [vaga.get("cidade"), vaga.get("estado")] if x)
    hoje = date.today().strftime("%B %d, %Y")
    corpo = f"{hoje}\n\nHiring Manager\n{empresa}" + (f"\n{local}" if local else "") + \
            f"\n\nSubject: {assunto}\n\n" + corpo.replace("\n\n(Resume attached.)", "")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Cover letter</title>" + ESTILO +
            "</head><body><div class='aviso'><b>RotaNorte:</b> revise e personalize antes de enviar. Copie o texto "
            "para o corpo do e-mail ou salve em PDF (Ctrl+P).</div><pre style='white-space:pre-wrap;font-family:"
            "Calibri,Arial;font-size:15px'>" + _e(corpo) + "</pre></body></html>")
