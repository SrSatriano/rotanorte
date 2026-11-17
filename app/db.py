"""Banco de dados local (SQLite) – fica em dados/rotanorte.db."""
from __future__ import annotations

import json
import sqlite3
import threading

from .util import PASTA_DADOS, agora_iso

ARQUIVO = PASTA_DADOS / "rotanorte.db"
VERSAO_BANCO = 2
_trava = threading.Lock()

ESQUEMA = """
CREATE TABLE IF NOT EXISTS vagas (
    id TEXT PRIMARY KEY,
    fonte TEXT, pais TEXT, programa TEXT,
    titulo TEXT, empresa TEXT, cidade TEXT, estado TEXT,
    salario_txt TEXT, salario_hora REAL, moeda TEXT,
    data_publicacao TEXT, data_inicio TEXT, data_fim TEXT,
    vagas_qtd INTEGER,
    url TEXT, como_aplicar TEXT,
    aceita_estrangeiro INTEGER,       -- 1 sim / 0 não / NULL desconhecido
    lmia TEXT,                         -- 'solicitado' / 'aprovado' / NULL
    codigo_ocupacao TEXT,              -- SOC (EUA) ou NOC (Canadá)
    categoria TEXT,
    descricao TEXT,
    score INTEGER, motivos TEXT, extras TEXT,
    risco_golpe INTEGER, alertas_golpe TEXT,
    primeira_vez TEXT, ultima_vez TEXT, ativo INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_vagas_score ON vagas(score);
CREATE TABLE IF NOT EXISTS candidaturas (
    vaga_id TEXT PRIMARY KEY,
    status TEXT, notas TEXT, atualizado TEXT, lembrete TEXT, aplicado_em TEXT
);
CREATE TABLE IF NOT EXISTS perm_empregadores (
    id TEXT PRIMARY KEY, empresa TEXT, cidade TEXT, estado TEXT, soc TEXT, soc_titulo TEXT, categoria TEXT,
    cargo TEXT, casos INTEGER, salario_min REAL, salario_max REAL, locais TEXT, ultima_decisao TEXT,
    telefone TEXT, funcionarios TEXT, periodo TEXT, fonte_url TEXT
);
CREATE TABLE IF NOT EXISTS aip_empregadores (
    id TEXT PRIMARY KEY, provincia TEXT, empresa TEXT, local TEXT, noc TEXT, data TEXT, fonte_url TEXT,
    nome_norm TEXT, atualizado TEXT
);
CREATE TABLE IF NOT EXISTS kv (
    chave TEXT PRIMARY KEY, valor TEXT, atualizado TEXT
);
CREATE TABLE IF NOT EXISTS empregadores (
    id TEXT PRIMARY KEY,
    pais TEXT, regiao TEXT, empresa TEXT, endereco TEXT,
    ocupacao TEXT, programa TEXT, posicoes INTEGER, periodo TEXT,
    categoria TEXT, fonte_url TEXT, atualizado TEXT
);
CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte TEXT, inicio TEXT, fim TEXT, ok INTEGER, mensagem TEXT, novos INTEGER, total INTEGER
);
CREATE TABLE IF NOT EXISTS vistos_jobbank (
    id TEXT PRIMARY KEY, verificado TEXT
);
"""

CAMPOS_VAGA = [
    "id", "fonte", "pais", "programa", "titulo", "empresa", "cidade", "estado",
    "salario_txt", "salario_hora", "moeda", "data_publicacao", "data_inicio",
    "data_fim", "vagas_qtd", "url", "como_aplicar", "aceita_estrangeiro", "lmia",
    "codigo_ocupacao", "categoria", "descricao", "score", "motivos", "extras",
    "risco_golpe", "alertas_golpe",
]


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(ARQUIVO, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    colunas = {r[1] for r in con.execute("PRAGMA table_info(vagas)")}
    if "extras" not in colunas:  # atualização de bancos antigos
        con.execute("ALTER TABLE vagas ADD COLUMN extras TEXT")
    if "aip" not in {r[1] for r in con.execute("PRAGMA table_info(empregadores)")}:
        con.execute("ALTER TABLE empregadores ADD COLUMN aip TEXT")
    col_c = {r[1] for r in con.execute("PRAGMA table_info(candidaturas)")}
    for nova in ("lembrete", "aplicado_em"):
        if nova not in col_c:
            con.execute(f"ALTER TABLE candidaturas ADD COLUMN {nova} TEXT")
    versao = con.execute("PRAGMA user_version").fetchone()[0]
    if versao < VERSAO_BANCO:
        # regras de leitura dos anúncios melhoraram: confere tudo de novo
        con.execute("DELETE FROM vistos_jobbank")
        con.execute(f"PRAGMA user_version={VERSAO_BANCO}")
        con.commit()
    return con


def salvar_vaga(con: sqlite3.Connection, v: dict) -> bool:
    """Insere ou atualiza. Devolve True se a vaga é nova."""
    agora = agora_iso()
    reg = {k: v.get(k) for k in CAMPOS_VAGA}
    for k in ("motivos", "alertas_golpe", "extras"):
        if isinstance(reg[k], (list, dict)):
            reg[k] = json.dumps(reg[k], ensure_ascii=False)
    with _trava:
        existe = con.execute("SELECT 1 FROM vagas WHERE id=?", (reg["id"],)).fetchone()
        if existe:
            sets = ", ".join(f"{k}=?" for k in CAMPOS_VAGA if k != "id")
            con.execute(f"UPDATE vagas SET {sets}, ultima_vez=?, ativo=1 WHERE id=?",
                        [reg[k] for k in CAMPOS_VAGA if k != "id"] + [agora, reg["id"]])
            return False
        cols = ", ".join(CAMPOS_VAGA + ["primeira_vez", "ultima_vez"])
        marc = ", ".join("?" * (len(CAMPOS_VAGA) + 2))
        con.execute(f"INSERT INTO vagas ({cols}) VALUES ({marc})",
                    [reg[k] for k in CAMPOS_VAGA] + [agora, agora])
        return True


def salvar_empregador(con, e: dict) -> None:
    with _trava:
        con.execute(
            """INSERT OR REPLACE INTO empregadores
               (id,pais,regiao,empresa,endereco,ocupacao,programa,posicoes,periodo,categoria,fonte_url,atualizado)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (e["id"], e.get("pais"), e.get("regiao"), e.get("empresa"), e.get("endereco"),
             e.get("ocupacao"), e.get("programa"), e.get("posicoes"), e.get("periodo"),
             e.get("categoria"), e.get("fonte_url"), agora_iso()))


def registrar_execucao(con, fonte, inicio, ok, mensagem, novos=0, total=0):
    with _trava:
        con.execute(
            "INSERT INTO execucoes (fonte,inicio,fim,ok,mensagem,novos,total) VALUES (?,?,?,?,?,?,?)",
            (fonte, inicio, agora_iso(), 1 if ok else 0, mensagem, novos, total))
        con.commit()


def linha_para_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    for k in ("motivos", "alertas_golpe", "extras"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except (TypeError, ValueError):
                pass
    return d


def kv_ler(con, chave: str, padrao=None):
    r = con.execute("SELECT valor FROM kv WHERE chave=?", (chave,)).fetchone()
    if not r:
        return padrao
    try:
        return json.loads(r[0])
    except (TypeError, ValueError):
        return padrao


def kv_salvar(con, chave: str, valor) -> None:
    with _trava:
        con.execute("INSERT OR REPLACE INTO kv (chave, valor, atualizado) VALUES (?,?,?)",
                    (chave, json.dumps(valor, ensure_ascii=False), agora_iso()))
        con.commit()
