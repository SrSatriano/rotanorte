"""Utilidades gerais: caminhos, JSON, datas e rede (somente biblioteca padrão)."""
from __future__ import annotations

import datetime as _dt
import gzip
import json
import os
import re
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_CONFIG = RAIZ / "config"
PASTA_DADOS = RAIZ / "dados"
PASTA_WEB = RAIZ / "web"
PASTA_DOCS = PASTA_DADOS / "documentos"

VERSAO = "1.2.0"
REGRAS_VERIFICADAS_EM = "2026-11-10"

USER_AGENT = (
    "RotaNorte/1.0 (busca pessoal de emprego; uso individual; "
    "respeita limites de acesso)"
)

for _p in (PASTA_CONFIG, PASTA_DADOS, PASTA_DOCS):
    _p.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- JSON
def ler_json(caminho: Path, padrao=None):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return padrao
    except json.JSONDecodeError as e:
        raise ValueError(f"Arquivo {caminho.name} está com erro de formatação: {e}") from e


def salvar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho)


# ---------------------------------------------------------------- texto
def sem_acento(txt: str) -> str:
    if not txt:
        return ""
    n = unicodedata.normalize("NFKD", str(txt))
    return "".join(c for c in n if not unicodedata.combining(c)).lower()


def limpar_html(txt: str) -> str:
    if not txt:
        return ""
    txt = re.sub(r"(?is)<(script|style).*?</\1>", " ", txt)
    txt = re.sub(r"(?s)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", txt)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    import html as _html
    txt = _html.unescape(txt)
    txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()


def agora_iso() -> str:
    return _dt.datetime.now().replace(microsecond=0).isoformat()


def hoje() -> _dt.date:
    return _dt.date.today()


# ---------------------------------------------------------------- rede
class ErroRede(Exception):
    pass


_ultimo_acesso: dict[str, float] = {}
_trava = threading.Lock()


def _esperar_vez(host: str, intervalo: float) -> None:
    """Respeita um intervalo mínimo entre acessos ao mesmo site."""
    with _trava:
        ultimo = _ultimo_acesso.get(host, 0.0)
        espera = ultimo + intervalo - time.time()
        if espera > 0:
            time.sleep(espera)
        _ultimo_acesso[host] = time.time()


def baixar(url: str, *, timeout: int = 60, tentativas: int = 3,
           intervalo_host: float = 1.5, aceitar: str = "*/*") -> bytes:
    """Baixa uma URL e devolve os bytes. Tenta de novo em falhas temporárias."""
    host = urllib.parse.urlparse(url).netloc
    ctx = ssl.create_default_context()
    ultimo_erro = None
    for n in range(tentativas):
        _esperar_vez(host, intervalo_host)
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": aceitar,
            "Accept-Encoding": "gzip",
            "Accept-Language": "en-CA,en;q=0.9,pt-BR;q=0.6",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                dados = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    dados = gzip.decompress(dados)
                return dados
        except urllib.error.HTTPError as e:
            ultimo_erro = e
            if e.code in (400, 401, 403, 404, 410):
                break  # não adianta tentar de novo
        except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as e:
            ultimo_erro = e
        time.sleep(2 * (n + 1))
    raise ErroRede(f"Falha ao acessar {url}: {ultimo_erro}")


def baixar_json(url: str, **kw):
    return json.loads(baixar(url, aceitar="application/json", **kw).decode("utf-8", "replace"))
