"""Detector de golpes em ofertas de emprego no exterior.

Regras baseadas em alertas oficiais: no Canadá é ilegal cobrar do
trabalhador por LMIA ou por oferta de emprego; nos EUA, trabalhadores
H-2B não podem pagar taxas de recrutamento e o empregador deve
reembolsar custos de visto e viagem.
"""
from __future__ import annotations

import re

from .util import sem_acento

# (peso, padrão regex, explicação)
REGRAS = [
    # ---- dinheiro adiantado (o sinal mais forte)
    (45, r"(taxa|tarifa|fee|cobran|pagamento|pagar|deposit|deposito|sinal|caucao|investimento)"
         r".{0,40}(lmia|visto|visa|vaga|emprego|job|contrat|document|processo|inscri|reserva|agenci|recrut|place?ment)",
     "Pede dinheiro para vaga, visto, LMIA ou documentos. No Canadá é ILEGAL cobrar do trabalhador por "
     "LMIA ou oferta de emprego; no programa H-2B dos EUA o trabalhador também não pode pagar taxa de recrutamento."),
    (45, r"(lmia|visto|visa|vaga|emprego|job offer|contrato|carta oferta).{0,40}"
         r"(taxa|fee|custa|valor|pagar|pagamento|r\$|us\$|cad\$|\$ ?\d|usd|cad|reais|dolares)",
     "Associa a vaga/visto a um valor em dinheiro. Oferta legítima não se compra."),
    (40, r"\b(pix|western union|moneygram|bitcoin|cripto|usdt|gift ?card|cartao presente)\b",
     "Pede pagamento por PIX, Western Union, cripto ou cartão-presente – típico de golpe."),
    (35, r"(comprar|vend[eo]|venda de).{0,15}\blmia\b|\blmia\b.{0,20}(a venda|for sale|vend)",
     "Fala em comprar/vender LMIA. Vender LMIA é crime no Canadá."),
    # ---- promessas impossíveis
    (30, r"(visto|visa|green ?card|aprovacao|aprovado|emprego|vaga).{0,25}(garantid|guaranteed|100 ?%|certeza)",
     "Promete visto ou aprovação garantida. Ninguém pode garantir visto – a decisão é do governo."),
    (20, r"sem (experiencia|ingles|entrevista|documento)s?.{0,30}(visto|canada|eua|estados unidos|usa|patrocin)",
     "Promete visto sem experiência/inglês/entrevista – irrealista para a maioria dos programas."),
    (15, r"(salario|ganhe|renda).{0,30}(us\$|cad|\$|dolares)\s?(\d{2,3}[.,]?\d{3}|\d{2,3} ?mil).{0,15}(por mes|mensa|/mes|month)",
     "Salário mensal muito alto para função de entrada – confira com a média oficial do cargo."),
    # ---- contato suspeito
    (20, r"\b(whats ?app|telegram|signal)\b",
     "Contato só por WhatsApp/Telegram. Empregadores reais costumam usar e-mail corporativo e sites oficiais."),
    (15, r"@(gmail|hotmail|outlook|yahoo|live|icloud|proton|bol|uol)\.",
     "E-mail gratuito (gmail/hotmail etc.) em nome de empresa – confirme pelo site oficial da empresa."),
    (10, r"(urgente|ultimas vagas|apenas hoje|so hoje|vagas limitadas|responda em \d+ ?h|act now|limited slots)",
     "Pressão por urgência – golpistas apressam para você não pesquisar."),
    # ---- dados sensíveis cedo demais
    (20, r"(envie|mande|send).{0,30}(passaporte|passport|cpf|rg|dados banc|bank|cartao|senha|password)",
     "Pede passaporte, dados bancários ou senha antes de existir contrato verificado."),
    # ---- consultor/agente sem registro
    (10, r"(consultor|consultant|agente|agent|despachante|assessoria).{0,40}(imigra|immigration|visto|visa)",
     "Envolve consultor/agente. No Canadá ele precisa ser RCIC registrado no CICC (college-ic.ca); "
     "nos EUA, confira se o recrutador está na Foreign Labor Recruiter List do DOL."),
    (15, r"(curso|treinamento|training|certificac).{0,30}(obrigatori|required|antes).{0,30}(pago|pagar|fee|r\$|\$)",
     "Exige curso/treinamento pago como condição para a vaga – golpe comum."),
]

SINAIS_BONS = [
    (r"seasonaljobs\.dol\.gov|jobbank\.gc\.ca|\.gov\b|\.gc\.ca\b|canada\.ca", 10,
     "Cita fonte governamental verificável."),
    (r"h-400-\d{5}-\d{6}", 10, "Tem número de caso H-2B (ETA case number) – dá para conferir no SeasonalJobs."),
    (r"(employer|empregador).{0,30}(pay|paga|reembols|reimburs)", 5,
     "Diz que o empregador paga/reembolsa custos (correto pelas regras)."),
]


def analisar(texto: str) -> dict:
    """Devolve {'risco': 0-100, 'nivel': str, 'alertas': [...], 'positivos': [...]}"""
    t = sem_acento(texto or "")
    t = re.sub(r"\s+", " ", t)
    alertas, pontos = [], 0
    for peso, padrao, explicacao in REGRAS:
        if re.search(padrao, t):
            pontos += peso
            alertas.append({"peso": peso, "motivo": explicacao})
    positivos = []
    for padrao, peso, explicacao in SINAIS_BONS:
        if re.search(padrao, t):
            pontos -= peso
            positivos.append(explicacao)
    risco = max(0, min(100, pontos))
    if risco >= 45:
        nivel = "ALTO"
    elif risco >= 20:
        nivel = "MÉDIO"
    else:
        nivel = "BAIXO"
    return {"risco": risco, "nivel": nivel, "alertas": alertas, "positivos": positivos,
            "lembrete": ("Mesmo com risco baixo: nunca pague por vaga, confira a empresa no site "
                         "oficial dela e o caso no site do governo antes de enviar documentos.")}
