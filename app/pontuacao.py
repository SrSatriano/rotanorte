"""Calcula o quanto uma vaga combina com o perfil (0 a 100) e explica o porquê."""
from __future__ import annotations

from .ocupacoes import (CATEGORIAS, classificar, conjuge_pode_trabalhar_canada,
                        nome_categoria, teer_do_noc)


def experiencia_por_categoria(perfil: dict) -> dict[str, dict]:
    """Junta experiências e cursos do perfil por categoria."""
    saida: dict[str, dict] = {}
    for e in perfil.get("experiencias", []) or []:
        cat = e.get("categoria")
        if not cat:
            continue
        d = saida.setdefault(cat, {"anos": 0.0, "informado": True, "curso": False})
        if e.get("anos") in (None, ""):
            d["informado"] = False
            d["anos"] += 0.5  # suposição conservadora até o usuário informar
        else:
            d["anos"] += float(e.get("anos") or 0)
    for c in perfil.get("cursos", []) or []:
        cat = c.get("categoria")
        if cat:
            saida.setdefault(cat, {"anos": 0.0, "informado": True, "curso": False})["curso"] = True
    return saida


def pontuar(vaga: dict, perfil: dict) -> tuple[int, list[str]]:
    motivos: list[str] = []
    pts = 0
    exp = experiencia_por_categoria(perfil)

    cat = vaga.get("categoria") or classificar(vaga.get("titulo", ""), vaga.get("codigo_ocupacao", ""),
                                               vaga.get("descricao", ""))
    vaga["categoria"] = cat

    # 1) Combina com sua experiência? (até 45)
    if cat and cat in exp:
        d = exp[cat]
        if d["anos"] >= 2:
            pts += 45
            motivos.append(f"✔ Você tem {d['anos']:.0f}+ anos em {nome_categoria(cat)}")
        elif d["anos"] >= 1:
            pts += 38
            motivos.append(f"✔ Você tem experiência em {nome_categoria(cat)}")
        elif d["anos"] > 0:
            pts += 30
            motivos.append(f"✔ Área da sua experiência ({nome_categoria(cat)})"
                           + ("" if d["informado"] else " – informe os anos no perfil"))
        if d["curso"]:
            pts += 8 if d["anos"] < 1 else 4
            motivos.append(f"✔ Você tem curso em {nome_categoria(cat)}")
    elif cat in ("construcao", "servicos_gerais", "producao", "agricultura", "hotelaria"):
        pts += 18
        motivos.append(f"• Função de entrada ({nome_categoria(cat)}) – costuma aceitar pouca experiência")
    elif cat:
        motivos.append(f"✖ Área fora do seu perfil ({nome_categoria(cat)})")
    else:
        motivos.append("• Não foi possível identificar a área da vaga")

    # 2) Aceita quem está fora do país? (até 25)
    if vaga.get("aceita_estrangeiro") == 1:
        pts += 25
        motivos.append("✔ Confirmado: aceita candidatos do exterior / programa de visto")
    elif vaga.get("aceita_estrangeiro") == 0:
        pts -= 40
        motivos.append("✖ Anúncio diz que só aceita quem já pode trabalhar no país")
    else:
        motivos.append("? Não confirmado se aceita estrangeiros – pergunte antes de investir tempo")
    if vaga.get("lmia") in ("solicitado", "aprovado"):
        pts += 5
        motivos.append(f"✔ LMIA {vaga['lmia']} (empregador já está no processo de contratar estrangeiro)")

    # 2b) Detalhes do pedido H-2B
    ex = vaga.get("extras") or {}
    if isinstance(ex, dict):
        paises = ex.get("paises_recrutamento") or []
        if any("brazil" in p.lower() or "brasil" in p.lower() for p in paises):
            pts += 10
            motivos.append("✔ Empregador declarou recrutamento no BRASIL")
        elif paises:
            motivos.append("• Recrutadores declarados em: " + ", ".join(paises)
                           + " – pergunte se aceitam brasileiros")
        meses = ex.get("exp_min_meses")
        if meses is not None:
            anos_cat = exp.get(cat, {}).get("anos", 0) if cat else 0
            if meses == 0:
                pts += 5
                motivos.append("✔ Não exige experiência mínima")
            elif anos_cat * 12 >= meses:
                motivos.append(f"✔ Você atende a experiência mínima ({meses:g} meses)")
            else:
                pts -= 5
                motivos.append(f"• Pede {meses:g} meses de experiência na função")
        if ex.get("aip"):
            pts += 8
            motivos.append(f"✔ Empregador DESIGNADO no Atlantic Immigration Program ({ex['aip']}) – "
                           "oferta dele pode levar direto à residência permanente")
        if ex.get("moradia"):
            pts += 3
            motivos.append("✔ Empregador oferece ou ajuda com moradia")

    # 3) Família (até 15)
    pais = vaga.get("pais")
    tem_familia = bool(perfil.get("filhos")) or perfil.get("estado_civil") in ("casado", "uniao_estavel")
    if pais == "CA":
        ok = conjuge_pode_trabalhar_canada(vaga.get("codigo_ocupacao"))
        teer = teer_do_noc(vaga.get("codigo_ocupacao"))
        if ok is True:
            pts += 15
            motivos.append(f"✔ Ocupação TEER {teer}: cônjuge pode pedir permissão de trabalho aberta (SOWP)")
        elif ok is False and tem_familia:
            motivos.append(f"• Ocupação TEER {teer}: cônjuge em geral NÃO recebe permissão de trabalho aberta")
        elif cat == "soldagem":
            pts += 10
            motivos.append("✔ Soldador (NOC 72106, TEER 2) está na lista em que o cônjuge pode trabalhar")
    elif pais == "US" and (vaga.get("programa") or "").startswith("H-2B"):
        pts += 5
        motivos.append("• H-2B: cônjuge e filhos podem ir (H-4), mas o cônjuge não pode trabalhar; visto temporário")

    # 4) Salário (até 10)
    sh = vaga.get("salario_hora")
    if sh:
        if pais == "US" and sh >= 20 or pais == "CA" and sh >= 28:
            pts += 10
            motivos.append(f"✔ Salário bom para a função ({sh:.2f}/hora)")
        elif pais == "US" and sh >= 16 or pais == "CA" and sh >= 20:
            pts += 5

    # 5) Caminho para residência (até 5)
    if pais == "CA" and cat in ("soldagem", "eletrica", "hidraulica") and (teer_do_noc(vaga.get("codigo_ocupacao")) or 2) <= 3:
        pts += 5
        motivos.append("✔ Ofício qualificado: experiência no Canadá conta para residência permanente")

    return max(0, min(100, pts)), motivos
