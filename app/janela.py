"""Porta livre automática e abertura do painel em janela de aplicativo.

- Antes de subir o servidor, verifica se a porta está ocupada. Se estiver
  ocupada por OUTRO programa, tenta a próxima; se for o próprio RotaNorte
  já aberto, apenas reabre a janela dele.
- Abre o painel em modo aplicativo (janela própria, sem abas nem barra de
  endereço) usando Edge ou Chrome. Se nenhum existir, usa o navegador padrão.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

from .util import PASTA_DADOS

PORTA_PADRAO = 8765
TENTATIVAS = 100
ARQ_PORTA = PASTA_DADOS / "porta.txt"


# ------------------------------------------------------------------ portas
def porta_em_uso(porta: int, host: str = "127.0.0.1") -> bool:
    """True se algum programa já atende conexões nessa porta."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, porta)) == 0


def rotanorte_na_porta(porta: int) -> bool:
    """True se quem ocupa a porta é o próprio RotaNorte."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/ping", timeout=1.5) as r:
            return json.loads(r.read().decode("utf-8")).get("app") == "RotaNorte"
    except Exception:  # noqa: BLE001
        return False


def candidatos(preferida: int):
    """Porta preferida, a última usada, e depois as seguintes."""
    vistas = set()
    ultima = None
    try:
        ultima = int(ARQ_PORTA.read_text().strip())
    except (OSError, ValueError):
        pass
    for p in [preferida, ultima, *range(preferida + 1, preferida + TENTATIVAS)]:
        if p and p not in vistas and 1024 < p < 65535:
            vistas.add(p)
            yield p


def salvar_porta(porta: int) -> None:
    try:
        ARQ_PORTA.write_text(str(porta))
    except OSError:
        pass


# ------------------------------------------------------------------ janela
def _navegadores_windows() -> list[str]:
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        rf"{pf86}\Microsoft\Edge\Application\msedge.exe",
        rf"{pf}\Microsoft\Edge\Application\msedge.exe",
        rf"{pf}\Google\Chrome\Application\chrome.exe",
        rf"{pf86}\Google\Chrome\Application\chrome.exe",
        rf"{local}\Google\Chrome\Application\chrome.exe",
        rf"{pf}\BraveSoftware\Brave-Browser\Application\brave.exe",
        rf"{local}\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]


def achar_navegador_app() -> str | None:
    if sys.platform.startswith("win"):
        for caminho in _navegadores_windows():
            if caminho and Path(caminho).is_file():
                return caminho
    elif sys.platform == "darwin":
        for caminho in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"):
            if Path(caminho).is_file():
                return caminho
    for nome in ("msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser", "brave"):
        achado = shutil.which(nome)
        if achado:
            return achado
    return None


def abrir_como_app(url: str) -> subprocess.Popen | None:
    """Abre `url` numa janela de aplicativo. Devolve o processo (ou None se
    precisou usar o navegador comum)."""
    exe = achar_navegador_app()
    if exe:
        perfil = PASTA_DADOS / "janela_app"   # perfil separado = janela própria na barra de tarefas
        perfil.mkdir(parents=True, exist_ok=True)
        args = [exe, f"--app={url}", f"--user-data-dir={perfil}", "--window-size=1320,900",
                "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"]
        try:
            flags = 0
            if sys.platform.startswith("win"):
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    creationflags=flags)
        except OSError:
            pass
    webbrowser.open(url)
    return None
