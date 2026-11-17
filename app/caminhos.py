"""Avalia os caminhos de visto (EUA e Canadá) para o perfil e monta um plano de ação.

ATENÇÃO: regras de imigração mudam com frequência. Tudo aqui foi conferido
em fontes oficiais e de advogados de imigração em REGRAS_VERIFICADAS_EM.
Antes de qualquer decisão, confira os links oficiais de cada caminho.
"""
from __future__ import annotations

from .pontuacao import experiencia_por_categoria
from .util import REGRAS_VERIFICADAS_EM

NIVEIS_INGLES = ["nao_informado", "nenhum", "basico", "intermediario", "avancado", "fluente"]

ALERTAS_RECENTES = [
    {"data": "2026-08-25", "pais": "EUA",
     "texto": "O Departamento de Estado pausou/remarcou entrevistas de visto de IMIGRANTE (green card) no mundo "
              "todo para treinar os cônsules sobre 'public charge' (risco de depender de benefícios). Não houve "
              "anúncio oficial de data de retomada até o fim de outubro/2026. Vistos temporários (como H-2B) não "
              "fazem parte dessa pausa.",
     "link": "https://travel.state.gov/content/travel/en/News/visas-news.html"},
    {"data": "2026-08-21", "pais": "EUA",
     "texto": "Acabou, por ordem judicial, a pausa de vistos de imigrante para 75 países que incluía o Brasil "
              "(estava em vigor desde 21/01/2026). A análise individual continua rigorosa.",
     "link": "https://travel.state.gov/content/travel/en/News/visas-news.html"},
    {"data": "2026-07-24", "pais": "EUA",
     "texto": "A taxa extra de US$ 100 mil para novos H-1B de quem está fora dos EUA está suspensa pela "
              "Justiça (decisão mantida pela Corte de Apelação). O governo ainda recorre – pode mudar.",
     "link": "https://www.uscis.gov/working-in-the-united-states/h-1b-specialty-occupations"},
    {"data": "2026-10-09", "pais": "Canadá",
     "texto": "LMIA de BAIXO salário não é processado em 30 regiões metropolitanas com desemprego ≥ 6% "
              "(período de 09/10/2026 a 07/01/2027). Vagas de salário alto e de cidades pequenas/rurais não "
              "têm essa trava – prefira-as.",
     "link": "https://www.canada.ca/en/employment-social-development/services/foreign-workers/refusal.html"},
    {"data": "2026-10-01", "pais": "Canadá",
     "texto": "Último sorteio do Express Entry só para ofícios (inclui soldadores): 3.500 convites, nota de corte "
              "CRS 476. Antes, em 02/04/2026, o corte foi 477. É alto para quem ainda não tem experiência no Canadá.",
     "link": "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/rounds-invitations.html"},
    {"data": "2025-01-21", "pais": "Canadá",
     "texto": "Cônjuge de trabalhador estrangeiro só recebe permissão de trabalho aberta se a ocupação do "
              "trabalhador for TEER 0/1 ou uma TEER 2/3 da lista (inclui ofícios 72xxx/73xxx como SOLDADOR, "
              "eletricista, encanador). Ajudante de obra (NOC 75110, TEER 5) não dá esse direito.",
     "link": "https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada/permit/temporary/open-work-permit-spouses-dependent-children/eligibility.html"},
]

ONDE_CONFERIR = [
    ("Lista de países elegíveis H-2A/H-2B (DHS)", "https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-2b-temporary-non-agricultural-workers"),
    ("Vagas H-2B oficiais (SeasonalJobs)", "https://seasonaljobs.dol.gov/"),
    ("Lista de recrutadores estrangeiros do DOL (verificar agências)", "https://www.dol.gov/agencies/eta/foreign-labor/recruiter-list"),
    ("Boletim de vistos (fila do green card)", "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"),
    ("Job Bank – vagas para candidatos estrangeiros", "https://www.jobbank.gc.ca/findajob/foreign-candidates"),
    ("Registro de consultores de imigração do Canadá (CICC)", "https://register.college-ic.ca/Public-Register-EN/RCIC_Search.aspx"),
    ("Taxas oficiais do IRCC", "https://www.cic.gc.ca/english/information/fees/fees.asp"),
    ("Calculadora oficial CRS (Express Entry)", "https://www.cic.gc.ca/english/immigrate/skilled/crs-tool.asp"),
    ("Denunciar fraude de emprego/imigração no Canadá", "https://www.canada.ca/en/immigration-refugees-citizenship/services/protect-fraud.html"),
]


def _nivel_ingles(p: dict) -> int:
    try:
        return NIVEIS_INGLES.index(p.get("ingles") or "nao_informado")
    except ValueError:
        return 0


def _req(texto, ok):
    return {"texto": texto, "ok": ok}


def avaliar(perfil: dict) -> dict:
    exp = experiencia_por_categoria(perfil)
    solda = exp.get("soldagem", {"anos": 0, "curso": False, "informado": True})
    anos_solda = solda["anos"] if solda.get("informado", True) else 0
    tem_curso_solda = solda.get("curso", False)
    oficios = {k: v for k, v in exp.items() if k in ("soldagem", "eletrica", "hidraulica")}
    entrada = {k: v for k, v in exp.items() if k in ("construcao", "servicos_gerais", "producao", "agricultura", "hotelaria")}
    anos_entrada = max([v["anos"] for v in entrada.values()] or [0])
    ingles = _nivel_ingles(perfil)
    esc = (perfil.get("escolaridade") or {}).get("nivel", "")
    graduado = esc in ("superior_completo", "pos")
    cursando = esc == "superior_cursando"
    n_filhos = len(perfil.get("filhos") or [])
    casado = perfil.get("estado_civil") in ("casado", "uniao_estavel")
    familia = 1 + (1 if casado else 0) + n_filhos
    pais = (perfil.get("pais_cidadania") or "").lower()
    brasileiro = pais.startswith("bra")

    caminhos = []

    # ------------------------------------------------------------------ EUA
    caminhos.append({
        "id": "us_h2b", "pais": "EUA", "nome": "H-2B – trabalho temporário não agrícola",
        "viabilidade": "agora" if (anos_entrada > 0 or anos_solda > 0) else "preparar",
        "resumo": "Empregadores americanos certificados pelo governo contratam estrangeiros para trabalho "
                  "sazonal/temporário (construção, paisagismo, hotelaria, frigoríficos etc.). Não exige diploma "
                  "nem inglês avançado. É o caminho MAIS RÁPIDO para trabalhar nos EUA, mas é TEMPORÁRIO "
                  "(geralmente até 9–10 meses por contrato) e não leva sozinho ao green card.",
        "familia": "Cônjuge e filhos podem ir com visto H-4, mas o cônjuge NÃO pode trabalhar e o empregador "
                   "não paga os custos da família. Muitos trabalhadores vão sozinhos na primeira temporada "
                   "para juntar dinheiro – avalie se o salário sustenta 5 pessoas lá.",
        "custos": "O trabalhador NÃO pode pagar taxa de recrutamento. O empregador deve reembolsar a taxa do "
                  "visto e a passagem de ida (até metade do contrato) e a volta se você cumprir o contrato.",
        "requisitos": [
            _req("Ser de país da lista H-2B (o Brasil está na lista; ela é revista todo ano)", True if brasileiro else None),
            _req("Ter oferta de empregador com certificação do Departamento do Trabalho", None),
            _req("Experiência na função (muitas vagas pedem 0–3 meses)", anos_entrada > 0 or anos_solda > 0 or None),
            _req("Entrevista no consulado mostrando vínculo com o Brasil (visto não imigrante)", None),
        ],
        "proximos_passos": [
            "Use a aba Vagas filtrando 'EUA · H-2B' – todas são de empregadores certificados.",
            "Contate o empregador ou o agente listado na vaga. Pergunte se recrutam no Brasil.",
            "Confira a agência na lista de recrutadores do DOL antes de mandar documentos.",
            "Procure vagas que comecem daqui a 2–5 meses (o processo leva esse tempo).",
        ],
        "links": [("Programa H-2B (USCIS)", "https://www.uscis.gov/working-in-the-united-states/temporary-workers/h-2b-temporary-non-agricultural-workers"),
                  ("Vagas oficiais", "https://seasonaljobs.dol.gov/"),
                  ("Direitos do trabalhador H-2B", "https://www.dol.gov/agencies/whd/immigration/h2b")],
    })

    caminhos.append({
        "id": "us_eb3", "pais": "EUA", "nome": "EB-3 – green card patrocinado por empregador",
        "viabilidade": "longo",
        "resumo": "Um empregador americano faz o processo (PERM + I-140) para você ter residência permanente. "
                  "Existem duas filas: 'Skilled Workers' (função exige 2+ anos de experiência – ex.: soldador "
                  "experiente) e 'Other Workers' (funções sem qualificação). Pelo boletim de novembro/2026, a "
                  "fila 'Other Workers' para o Brasil está em 01/06/2022 (~4,5 anos só de espera) e a 'Skilled' "
                  "em 15/06/2024 (~2,5 anos), fora o tempo do PERM.",
        "familia": "Cônjuge e filhos menores de 21 recebem green card junto. É o melhor resultado para a família, "
                   "mas o mais demorado e incerto.",
        "custos": "Os custos do PERM (certificação trabalhista) são OBRIGATORIAMENTE do empregador. Ofertas de "
                  "'green card EB-3 pago' por dezenas de milhares de dólares exigem muita cautela.",
        "requisitos": [
            _req("Empregador disposto a patrocinar e esperar anos", None),
            _req("Para a fila 'Skilled': 2+ anos comprovados de experiência na função", anos_solda >= 2),
            _req("Entrevista de visto de imigrante – estão pausadas/remarcadas desde 25/08/2026", None),
        ],
        "proximos_passos": [
            "Acumule e documente 2+ anos de experiência como soldador (abre a fila 'Skilled', mais curta).",
            "Pergunte a empregadores H-2B que gostarem do seu trabalho se patrocinam EB-3.",
            "Nunca pague 'vaga' de green card. Exija contrato e confira o empregador e o advogado.",
        ],
        "links": [("Boletim de vistos", "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"),
                  ("EB-3 (USCIS)", "https://www.uscis.gov/working-in-the-united-states/permanent-workers/employment-based-immigration-third-preference-eb-3")],
    })

    caminhos.append({
        "id": "us_h1b", "pais": "EUA", "nome": "H-1B – profissional com diploma (depois de formar em CC)",
        "viabilidade": "agora" if graduado and ingles >= 4 else "longo",
        "resumo": "Para quem tem bacharelado e oferta de emprego em área especializada (ex.: TI). Há sorteio anual "
                  "das vagas. A taxa extra de US$ 100 mil está suspensa pela Justiça desde julho/2026, mas o caso "
                  "continua em recurso.",
        "familia": "Cônjuge e filhos vão com H-4 (cônjuge só trabalha em casos específicos).",
        "custos": "Taxas pagas pelo empregador; concorrência alta para recém-formados estrangeiros.",
        "requisitos": [
            _req("Bacharelado concluído (Ciência da Computação)", True if graduado else (None if cursando else False)),
            _req("Inglês avançado para entrevistas técnicas", ingles >= 4 if ingles else None),
            _req("Oferta de empresa disposta a entrar no sorteio", None),
        ],
        "proximos_passos": [
            "Conclua a faculdade e monte portfólio (GitHub) – vale também para o Canadá.",
            "Estude inglês técnico desde já.",
        ],
        "links": [("H-1B (USCIS)", "https://www.uscis.gov/working-in-the-united-states/h-1b-specialty-occupations")],
    })

    # --------------------------------------------------------------- CANADÁ
    via_lmia = "agora" if (anos_solda >= 1 or anos_entrada >= 1) else "preparar"
    caminhos.append({
        "id": "ca_lmia", "pais": "Canadá", "nome": "Permissão de trabalho com oferta + LMIA",
        "viabilidade": via_lmia,
        "resumo": "Um empregador canadense prova ao governo (LMIA) que precisa de um estrangeiro e te contrata. "
                  "Você recebe permissão de trabalho ligada a ele. Experiência no Canadá depois abre portas para a "
                  "residência permanente (Express Entry e programas provinciais).",
        "familia": ("Se a vaga for de SOLDADOR (NOC 72106, TEER 2) ou outro ofício 72xxx/73xxx, com permissão "
                    "válida por 16+ meses, seu cônjuge pode pedir permissão de trabalho ABERTA e os filhos estudam "
                    "em escola pública. Em vaga de ajudante (TEER 5) o cônjuge em geral não pode trabalhar.")
                   if casado else "Filhos menores costumam poder estudar em escola pública enquanto você trabalha.",
        "custos": "O LMIA (CAD 1.000) é pago pelo EMPREGADOR – cobrar isso de você é crime. Você paga a taxa da "
                  "permissão de trabalho, biometria e exame médico (veja valores no site do IRCC).",
        "requisitos": [
            _req("Oferta de emprego de empregador que obtenha LMIA", None),
            _req("Experiência/qualificação exigida no anúncio", (anos_solda >= 1 or anos_entrada >= 1) or None),
            _req("Inglês para comunicação no trabalho (alguns empregadores pedem teste)", ingles >= 3 if ingles else None),
            _req("Prefira salário alto ou cidade fora das 30 metrópoles com trava (regras de 2026)", None),
        ],
        "proximos_passos": [
            "Aba Vagas → Canadá com selo 'aceita estrangeiro' (conferido no anúncio do Job Bank).",
            "Aba Empresas: empregadores que JÁ tiveram LMIA aprovado na sua área – mande currículo direto.",
            "Priorize vagas de soldador (TEER 2): permitem que sua esposa trabalhe.",
        ],
        "links": [("Job Bank – candidatos estrangeiros", "https://www.jobbank.gc.ca/findajob/foreign-candidates"),
                  ("Permissão do cônjuge (IRCC)", "https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada/permit/temporary/open-work-permit-spouses-dependent-children/eligibility.html"),
                  ("Lista oficial de empregadores com LMIA", "https://open.canada.ca/data/en/dataset/90fed587-1364-4f33-a9ee-208181dc0b97")],
    })

    caminhos.append({
        "id": "ca_ee", "pais": "Canadá", "nome": "Express Entry – Ofícios (Federal Skilled Trades)",
        "viabilidade": "longo" if anos_solda < 2 else "preparar",
        "resumo": "Residência permanente direta para a família toda. Para ofícios exige: 2 anos de experiência no "
                  "ofício (últimos 5 anos), inglês CLB 5 (fala/escuta) e 4 (leitura/escrita) e uma oferta de "
                  "emprego de 1 ano OU certificado de qualificação de uma província. Os sorteios só de ofícios em "
                  "2026 tiveram corte de 476–477 pontos – difícil sem experiência canadense ou nomeação provincial "
                  "(que soma 600 pontos).",
        "familia": "Residência permanente para você, cônjuge e filhos (podem trabalhar e estudar livremente).",
        "custos": "Exige comprovar dinheiro para a família (valor atualizado todo ano – para 5 pessoas são dezenas "
                  "de milhares de dólares canadenses), salvo quando já trabalha no Canadá com autorização.",
        "requisitos": [
            _req("2 anos de experiência como soldador (ou outro ofício) nos últimos 5 anos", anos_solda >= 2 if solda.get("informado", True) else None),
            _req("Teste de inglês aprovado (IELTS General, CELPIP ou PTE Core) – CLB 5/4", None if not perfil.get("teste_idioma", {}).get("tipo") else True),
            _req("Oferta de emprego OU certificado de qualificação canadense", None),
            _req("Avaliação do diploma (ECA) se for usar a faculdade para pontos", None),
        ],
        "proximos_passos": [
            "Trabalhe como soldador no Brasil com carteira assinada e guarde comprovantes.",
            "Faça o teste de inglês quando estiver perto de CLB 5 (meta: o mais alto possível).",
            "Calcule sua pontuação na calculadora oficial CRS.",
        ],
        "links": [("Federal Skilled Trades", "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/who-can-apply/federal-skilled-trades.html"),
                  ("Sorteios do Express Entry", "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/rounds-invitations.html")],
    })

    caminhos.append({
        "id": "ca_pnp", "pais": "Canadá", "nome": "Programas provinciais e pilotos regionais",
        "viabilidade": "preparar",
        "resumo": "Cada província tem programas próprios (ex.: Saskatchewan, Manitoba, Alberta, New Brunswick, "
                  "Nova Scotia), além do Atlantic Immigration Program e do piloto de comunidades rurais (RCIP). "
                  "Quase todos exigem oferta de emprego na província; alguns aceitam ofícios e funções de entrada. "
                  "As regras mudam várias vezes por ano.",
        "familia": "Leva à residência permanente da família toda.",
        "custos": "Taxas de cada província + IRCC. Programas oficiais não vendem vaga nem oferta de emprego.",
        "requisitos": [_req("Oferta de emprego de empregador da província (na maioria)", None),
                       _req("Inglês mínimo (varia; muitos pedem CLB 4–5)", None)],
        "proximos_passos": [
            "Use a aba Empresas filtrando por província (SK, MB, AB, NB, NS são boas para ofícios).",
            "Leia a página oficial do programa da província antes de aceitar oferta.",
        ],
        "links": [("Programas provinciais (IRCC)", "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/provincial-nominees.html"),
                  ("Atlantic Immigration Program", "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/atlantic-immigration.html"),
                  ("Rural Community Immigration Pilot", "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/rural-franco-pilots/rural-immigration.html")],
    })

    caminhos.append({
        "id": "nao", "pais": "Atenção", "nome": "O que NÃO fazer",
        "viabilidade": "nao",
        "resumo": "Não trabalhe com visto de turista (B1/B2 nos EUA ou eTA/visitante no Canadá): é ilegal e pode "
                  "gerar proibição de entrada por anos. Não pague por vaga, LMIA, 'carta-oferta' ou 'green card "
                  "garantido'. Não entregue passaporte original a agências.",
        "familia": "", "custos": "", "requisitos": [], "proximos_passos": [], "links": [],
    })

    return {
        "verificado_em": REGRAS_VERIFICADAS_EM,
        "caminhos": caminhos,
        "alertas": ALERTAS_RECENTES,
        "onde_conferir": [{"nome": n, "url": u} for n, u in ONDE_CONFERIR],
        "plano": plano_de_acao(perfil, anos_solda, tem_curso_solda, ingles, familia, cursando, graduado),
    }


def plano_de_acao(perfil, anos_solda, tem_curso_solda, ingles, familia, cursando, graduado) -> list[dict]:
    plano = []

    def item(prazo, titulo, detalhe, feito=None):
        plano.append({"prazo": prazo, "titulo": titulo, "detalhe": detalhe, "feito": feito})

    faltando = []
    if perfil.get("ingles") in (None, "", "nao_informado"):
        faltando.append("seu nível de inglês")
    exps = perfil.get("experiencias") or []
    if any(e.get("anos") in (None, "") for e in exps):
        faltando.append("os anos de cada experiência")
    if not perfil.get("nome"):
        faltando.append("nome e contato (para o currículo)")
    if faltando:
        item("Hoje", "Completar o perfil",
             "Preencha " + ", ".join(faltando) + " na aba Perfil. As notas das vagas e este plano ficam mais precisos.",
             False)

    item("Esta semana", "Proteger-se de golpes",
         "Regra de ouro: vaga real não cobra. Cole qualquer oferta que receber na aba 'Verificar oferta'.")
    item("Este mês", "Passaportes da família",
         f"Os {familia} passaportes precisam estar válidos antes de qualquer visto (agendamento na Polícia Federal).",
         perfil.get("passaportes_familia_ok"))
    item("Este mês", "Organizar provas de experiência",
         "Carteira de trabalho, holerites e cartas de referência em papel timbrado com função, datas, horas por "
         "semana e tarefas. Depois traduza para inglês.")
    if anos_solda < 1:
        item("Próximos 1–3 meses", "Conseguir emprego registrado como SOLDADOR no Brasil",
             "É o passo que mais aumenta suas chances: soldador é ofício qualificado (TEER 2) no Canadá e abre "
             "a fila 'Skilled' do EB-3 nos EUA. Meta: 1 ano para vagas com LMIA; 2 anos para Express Entry.")
    elif anos_solda < 2:
        item("Próximos 12 meses", "Completar 2 anos como soldador",
             "Com 2 anos você passa a atender o Federal Skilled Trades e a fila 'Skilled' do EB-3.")
    item("Próximos 3–6 meses", "Certificação de solda reconhecida",
         "Empregadores lá fora pedem testes práticos (ex.: posições 3G/4G, processos MIG/FCAW/SMAW). Uma "
         "certificação como a AWS Certified Welder, feita em centro credenciado, ajuda muito. "
         + ("Você já tem o curso – documente processos e horas." if tem_curso_solda else ""))
    if ingles < 3:
        item("Começar já (contínuo)", "Inglês até nível intermediário",
             "Meta prática: CLB 5 (conversação no trabalho). 30–60 min por dia com apps gratuitos e vídeos de "
             "soldagem em inglês (aprende o vocabulário técnico junto).")
    item("Quando chegar ao nível", "Teste oficial de inglês",
         "IELTS General Training, CELPIP-General ou PTE Core são aceitos pelo Canadá. Só faça quando os simulados "
         "indicarem CLB 5+ (o teste é caro).")
    item("Contínuo (semanal)", "Candidatar-se com o RotaNorte",
         "Rode a busca, marque as vagas com nota alta, gere currículo em inglês e envie. Registre tudo na aba "
         "Candidaturas. Meta: 10 candidaturas bem feitas por semana.")
    if cursando:
        item("Até a formatura", "Concluir Ciência da Computação",
             "O diploma abre H-1B (EUA) e ocupações TEER 1 no Canadá, que dão mais pontos e permitem o cônjuge trabalhar.")
    item("Antes de embarcar", "Reserva para a mudança",
         "Calcule passagens para a família, primeiro aluguel e 2–3 meses de despesas. Com renda atual, considere "
         "ir sozinho primeiro (ex.: H-2B ou LMIA) e trazer a família quando estiver estável.")
    return plano
