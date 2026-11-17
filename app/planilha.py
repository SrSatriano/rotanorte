"""Leitor mínimo de planilhas XLSX e CSV, sem bibliotecas externas.

Os dados oficiais do governo do Canadá vêm em XLSX. Um arquivo XLSX é um
ZIP com XMLs dentro; aqui lemos só o necessário (textos e números da
primeira aba).
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col_indice(ref: str) -> int:
    letras = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letras:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def ler_xlsx(dados: bytes, aba: int = 0) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nomes = z.namelist()
        compartilhados: list[str] = []
        if "xl/sharedStrings.xml" in nomes:
            raiz = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in raiz.findall("m:si", _NS):
                compartilhados.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))

        # descobre o arquivo da aba pelo workbook.xml + rels
        caminho_aba = None
        try:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            abas = wb.findall("m:sheets/m:sheet", _NS)
            rid = abas[aba].get(_REL)
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            for rel in rels:
                if rel.get("Id") == rid:
                    alvo = rel.get("Target").lstrip("/")
                    caminho_aba = alvo if alvo.startswith("xl/") else "xl/" + alvo
        except Exception:
            caminho_aba = None
        if not caminho_aba or caminho_aba not in nomes:
            planilhas = sorted(n for n in nomes if n.startswith("xl/worksheets/sheet"))
            caminho_aba = planilhas[aba]

        raiz = ET.fromstring(z.read(caminho_aba))
        linhas: list[list[str]] = []
        for row in raiz.iter(f"{{{_NS['m']}}}row"):
            num = row.get("r")
            if num and num.isdigit():
                while len(linhas) < int(num) - 1:  # mantém linhas vazias no lugar certo
                    linhas.append([])
            valores: dict[int, str] = {}
            for c in row.findall("m:c", _NS):
                ref = c.get("r")
                tipo = c.get("t")
                v = c.find("m:v", _NS)
                if tipo == "s" and v is not None:
                    texto = compartilhados[int(v.text)]
                elif tipo == "inlineStr":
                    texto = "".join(t.text or "" for t in c.iter(f"{{{_NS['m']}}}t"))
                else:
                    texto = v.text if v is not None and v.text is not None else ""
                idx = _col_indice(ref) if ref else len(valores)
                valores[idx] = (texto or "").strip()
            if valores:
                largura = max(valores) + 1
                linhas.append([valores.get(i, "") for i in range(largura)])
            else:
                linhas.append([])
        return linhas


def ler_csv(dados: bytes) -> list[list[str]]:
    for cod in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = dados.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    return [[c.strip() for c in linha] for linha in csv.reader(io.StringIO(texto))]


def ler_tabela(dados: bytes) -> list[list[str]]:
    if dados[:2] == b"PK":
        return ler_xlsx(dados)
    return ler_csv(dados)


def para_dicionarios(linhas: list[list[str]], palavra_cabecalho: str) -> list[dict]:
    """Acha a linha de cabeçalho (que contém `palavra_cabecalho`) e devolve
    as linhas seguintes como dicionários."""
    alvo = palavra_cabecalho.lower()
    inicio = None
    for i, linha in enumerate(linhas[:60]):
        preenchidas = [c for c in linha if (c or "").strip()]
        if len(preenchidas) >= 3 and any(alvo in (c or "").lower() for c in linha):
            inicio = i
            break
    if inicio is None:
        return []
    cab = [(c or f"col{j}").strip() for j, c in enumerate(linhas[inicio])]
    saida = []
    for linha in linhas[inicio + 1:]:
        if not any(linha):
            continue
        saida.append({cab[j]: (linha[j] if j < len(linha) else "") for j in range(len(cab))})
    return saida


def iterar_xlsx(caminho, aba: int = 0):
    """Lê um XLSX GRANDE linha por linha, sem carregar tudo na memória.
    Gera listas de textos (uma por linha)."""
    with zipfile.ZipFile(caminho) as z:
        nomes = z.namelist()
        compartilhados: list[str] = []
        if "xl/sharedStrings.xml" in nomes:
            with z.open("xl/sharedStrings.xml") as f:
                tag_si, tag_t = f"{{{_NS['m']}}}si", f"{{{_NS['m']}}}t"
                for _ev, el in ET.iterparse(f, events=("end",)):
                    if el.tag == tag_si:
                        compartilhados.append("".join(t.text or "" for t in el.iter(tag_t)))
                        el.clear()
        planilhas = sorted(n for n in nomes if n.startswith("xl/worksheets/sheet"))
        alvo = "xl/worksheets/sheet1.xml" if "xl/worksheets/sheet1.xml" in nomes else planilhas[aba]
        tag_row, tag_c, tag_v = (f"{{{_NS['m']}}}{x}" for x in ("row", "c", "v"))
        tag_is_t = f"{{{_NS['m']}}}t"
        with z.open(alvo) as f:
            contexto = ET.iterparse(f, events=("start", "end"))
            _ev, raiz = next(contexto)
            for ev, el in contexto:
                if ev != "end" or el.tag != tag_row:
                    continue
                valores: dict[int, str] = {}
                for c in el.findall(tag_c):
                    ref = c.get("r")
                    tipo = c.get("t")
                    if tipo == "inlineStr":
                        texto = "".join(t.text or "" for t in c.iter(tag_is_t))
                    else:
                        v = c.find(tag_v)
                        texto = v.text if v is not None and v.text is not None else ""
                        if tipo == "s" and texto:
                            texto = compartilhados[int(texto)]
                    valores[_col_indice(ref) if ref else len(valores)] = texto.strip()
                if valores:
                    largura = max(valores) + 1
                    yield [valores.get(i, "") for i in range(largura)]
                raiz.clear()  # libera memória das linhas já lidas
