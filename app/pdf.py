"""Gera PDF do currículo usando o próprio Edge/Chrome em modo invisível."""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from .janela import achar_navegador_app
from .util import PASTA_DADOS, PASTA_DOCS


def nome_arquivo(*partes: str) -> str:
    base = " - ".join(p for p in partes if p)
    base = re.sub(r'[\\/:*?"<>|]+', " ", base)
    return re.sub(r"\s+", " ", base).strip()[:120] or "Curriculo"


def gerar_pdf(url: str, destino: Path, timeout: int = 60) -> Path:
    exe = achar_navegador_app()
    if not exe:
        raise RuntimeError("Não encontrei Edge ou Chrome para gerar o PDF. Use Ctrl+P → Salvar como PDF.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        destino.unlink()
    perfil = PASTA_DADOS / "perfil_pdf"
    args = [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            "--no-pdf-header-footer", "--print-to-pdf-no-header", f"--user-data-dir={perfil}",
            f"--print-to-pdf={destino}", url]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0
    proc = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout,
                          creationflags=flags)
    for _ in range(20):  # o navegador às vezes termina de gravar logo depois
        if destino.exists() and destino.stat().st_size > 1000:
            return destino
        time.sleep(0.5)
    raise RuntimeError(f"O navegador não gerou o PDF (código {proc.returncode}).")


def pasta_documentos() -> Path:
    PASTA_DOCS.mkdir(parents=True, exist_ok=True)
    return PASTA_DOCS
