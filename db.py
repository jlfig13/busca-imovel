# -*- coding: utf-8 -*-
"""
Persistência em SQLite (módulo sqlite3 é nativo do Python -- nada para
instalar). Guarda todo imóvel já visto, quando foi visto pela primeira
vez e pela última vez, para sabermos o que é "novo" hoje.
"""
import sqlite3
from datetime import date, datetime

import config

SQL_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS imoveis (
    url TEXT PRIMARY KEY,
    site TEXT,
    titulo TEXT,
    bairro TEXT,
    cidade TEXT,
    preco REAL,
    quartos INTEGER,
    area_m2 REAL,
    primeiro_visto TEXT NOT NULL,
    ultimo_visto TEXT NOT NULL,
    visto_na_ultima_execucao INTEGER NOT NULL DEFAULT 1
);
"""

SQL_ADICIONAR_COLUNA_CIDADE = "ALTER TABLE imoveis ADD COLUMN cidade TEXT"

SQL_CRIAR_HISTORICO = """
CREATE TABLE IF NOT EXISTS historico_precos (
    url TEXT NOT NULL,
    data TEXT NOT NULL,
    preco REAL,
    PRIMARY KEY (url, data)
);
"""


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(config.ARQUIVO_DB)
    conn.execute(SQL_CRIAR_TABELA)
    conn.execute(SQL_CRIAR_HISTORICO)
    # migração: bancos criados antes do campo "cidade" existir não ganham a
    # coluna nova via CREATE TABLE IF NOT EXISTS (só afeta tabelas
    # inexistentes) -- adiciona à mão, ignorando se já existir.
    try:
        conn.execute(SQL_ADICIONAR_COLUNA_CIDADE)
        conn.commit()
    except sqlite3.OperationalError:
        pass
    return conn


def salvar_execucao(itens: list[dict]) -> list[dict]:
    """Grava os itens encontrados na execução de hoje, atualiza
    primeiro_visto/ultimo_visto e devolve os itens com os campos
    'novo' (bool) e 'primeiro_visto' (str) preenchidos."""
    hoje = date.today().isoformat()
    conn = conectar()
    cur = conn.cursor()

    # marca tudo como "não visto nesta execução" antes de processar
    cur.execute("UPDATE imoveis SET visto_na_ultima_execucao = 0")

    for item in itens:
        cur.execute("SELECT primeiro_visto FROM imoveis WHERE url = ?", (item["url"],))
        row = cur.fetchone()
        if row:
            primeiro_visto = row[0]
            item["novo"] = False
        else:
            primeiro_visto = hoje
            item["novo"] = True
        item["primeiro_visto"] = primeiro_visto

        cur.execute(
            """
            INSERT INTO imoveis (url, site, titulo, bairro, cidade, preco, quartos, area_m2,
                                  primeiro_visto, ultimo_visto, visto_na_ultima_execucao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(url) DO UPDATE SET
                site=excluded.site, titulo=excluded.titulo, bairro=excluded.bairro,
                cidade=excluded.cidade,
                preco=excluded.preco, quartos=excluded.quartos, area_m2=excluded.area_m2,
                ultimo_visto=excluded.ultimo_visto, visto_na_ultima_execucao=1
            """,
            (
                item["url"], item.get("site"), item.get("titulo"), item.get("bairro"),
                item.get("cidade"), item.get("preco"), item.get("quartos"), item.get("area_m2"),
                primeiro_visto, hoje,
            ),
        )
        if item.get("preco") is not None:
            cur.execute(
                "INSERT OR IGNORE INTO historico_precos (url, data, preco) VALUES (?, ?, ?)",
                (item["url"], hoje, item["preco"]),
            )

    conn.commit()
    conn.close()
    return itens


def listar_vistos_na_ultima_execucao() -> list[dict]:
    """Usado pelo dashboard: todos os imóveis vistos na execução mais
    recente, já com 'novo' calculado a partir de primeiro_visto == hoje."""
    hoje = date.today().isoformat()
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM imoveis WHERE visto_na_ultima_execucao = 1 ORDER BY preco ASC"
    )
    resultado = []
    for row in cur:
        d = dict(row)
        d["novo"] = d["primeiro_visto"] == hoje
        resultado.append(d)
    conn.close()
    return resultado


def obter_historico_todos(urls: list[str]) -> dict[str, list]:
    """Retorna dict url → [(data, preco), ...] ordenado por data asc,
    limitado às últimas 30 entradas por imóvel."""
    if not urls:
        return {}
    conn = conectar()
    placeholders = ",".join("?" * len(urls))
    cur = conn.execute(
        f"""
        SELECT url, data, preco FROM historico_precos
        WHERE url IN ({placeholders})
        ORDER BY url, data ASC
        """,
        urls,
    )
    resultado: dict[str, list] = {}
    for url, data, preco in cur:
        resultado.setdefault(url, []).append([data, preco])
    conn.close()
    # Keep last 30 entries per url
    return {u: v[-30:] for u, v in resultado.items()}


def contar_execucoes_anteriores() -> int:
    """Aproximação simples: nº de datas distintas em primeiro_visto,
    só para exibir 'desde quando' o histórico existe."""
    conn = conectar()
    cur = conn.execute("SELECT MIN(primeiro_visto) FROM imoveis")
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else date.today().isoformat()
