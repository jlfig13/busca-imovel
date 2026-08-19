# -*- coding: utf-8 -*-
"""
Checagem de robots.txt por fonte, com veredito datado.

P-17 da auditoria. O config afirmava, para Nogueira e Paulo Miranda, que "o
robots.txt deste site proíbe explicitamente acesso automatizado". Verificado:
nenhum dos dois TEM robots.txt -- ambos devolvem 404 com o HTML da home. Duas
fontes ficaram meses fora do monitoramento por uma restrição inexistente.

E o inverso também aconteceu: o Harry Fernandes, que de fato bloqueia
(`User-agent: * / Disallow: /` com allowlist nomeada), quase entrou como
fonte ativa -- a plataforma dele é Kenlo, tecnicamente trivial de raspar.

A lição não é "conferir uma vez". Política de acesso muda sem aviso, e nada
no sistema perceberia. Por isso o veredito é gravado com data e revalidado
periodicamente.
"""
import sqlite3
import urllib.parse
import urllib.robotparser
from datetime import date, datetime

import config
import utils
from utils import log

# Nosso agente. Um scraper próprio não é Googlebot nem Claude-User: quando o
# site publica allowlist nomeada, caímos na regra do "*" -- foi exatamente o
# que passou despercebido no Harry Fernandes.
USER_AGENT = "apt-scraper (monitor pessoal de aluguel)"

PERMITIDO = "PERMITIDO"
PROIBIDO = "PROIBIDO"
SEM_ROBOTS = "SEM_ROBOTS"
INDISPONIVEL = "INDISPONIVEL"

# Revalida quando o veredito passa disto. Política muda sem aviso.
DIAS_REVALIDACAO = 30

SQL_CRIAR = """
CREATE TABLE IF NOT EXISTS robots_veredito (
    dominio TEXT PRIMARY KEY,
    veredito TEXT NOT NULL,
    detalhe TEXT,
    crawl_delay REAL,
    verificado_em TEXT NOT NULL
);
"""


def _conectar():
    conn = sqlite3.connect(config.ARQUIVO_DB)
    conn.execute(SQL_CRIAR)
    return conn


def _dominio(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}" if p.netloc else ""


def consultar(url: str) -> dict:
    """Busca e interpreta o robots.txt do domínio da URL.

    Distingue os três casos que o config confundia:
      SEM_ROBOTS  -- arquivo não existe (404, ou devolve HTML). NÃO é
                     proibição: é ausência de política declarada.
      PROIBIDO    -- existe e nega o caminho para o nosso agente.
      PERMITIDO   -- existe e libera.
    """
    dominio = _dominio(url)
    if not dominio:
        return {"veredito": INDISPONIVEL, "detalhe": "URL sem domínio",
                "crawl_delay": None}

    alvo = f"{dominio}/robots.txt"
    try:
        # Busca com UA de navegador: alguns sites (o OLX entre eles) devolvem
        # 403 para agentes desconhecidos ATÉ no /robots.txt. Ler o arquivo com
        # UA comum e depois avaliar as regras contra a nossa identidade é o
        # que evita concluir "não tem robots" quando na verdade não deixaram
        # ler -- conclusão que erraria para o lado permissivo.
        resp = utils.requests.get(alvo, headers=utils.HEADERS, timeout=20)
    except Exception as e:
        return {"veredito": INDISPONIVEL, "detalhe": str(e)[:120],
                "crawl_delay": None}

    if resp.status_code != 200:
        return {"veredito": SEM_ROBOTS,
                "detalhe": f"HTTP {resp.status_code} em /robots.txt",
                "crawl_delay": None}

    corpo = resp.text
    # Servidor que devolve a home para qualquer caminho responde 200 com
    # HTML -- e isso não é um robots.txt. Foi o caso de Paulo Miranda e
    # Nogueira, e é o que fez a nota errada parecer verdadeira.
    if "<html" in corpo[:400].lower() or "<!doctype" in corpo[:400].lower():
        return {"veredito": SEM_ROBOTS,
                "detalhe": "/robots.txt devolve HTML, não diretivas",
                "crawl_delay": None}

    parser = urllib.robotparser.RobotFileParser()
    parser.parse(corpo.splitlines())
    permitido = parser.can_fetch(USER_AGENT, url)
    try:
        atraso = parser.crawl_delay(USER_AGENT)
    except Exception:
        atraso = None

    if permitido:
        return {"veredito": PERMITIDO, "detalhe": "", "crawl_delay": atraso}
    return {"veredito": PROIBIDO,
            "detalhe": "regra do User-agent '*' nega este caminho",
            "crawl_delay": atraso}


def veredito_para(url: str, forcar: bool = False) -> dict:
    """Veredito em cache, revalidado a cada DIAS_REVALIDACAO."""
    dominio = _dominio(url)
    conn = _conectar()
    linha = conn.execute(
        "SELECT veredito, detalhe, crawl_delay, verificado_em "
        "FROM robots_veredito WHERE dominio = ?", (dominio,)
    ).fetchone()

    if linha and not forcar:
        idade = (date.today() - date.fromisoformat(linha[3][:10])).days
        if idade < DIAS_REVALIDACAO:
            conn.close()
            return {"veredito": linha[0], "detalhe": linha[1],
                    "crawl_delay": linha[2], "em_cache": True}

    r = consultar(url)
    conn.execute(
        """INSERT INTO robots_veredito (dominio, veredito, detalhe, crawl_delay, verificado_em)
           VALUES (?,?,?,?,?)
           ON CONFLICT(dominio) DO UPDATE SET
             veredito=excluded.veredito, detalhe=excluded.detalhe,
             crawl_delay=excluded.crawl_delay, verificado_em=excluded.verificado_em""",
        (dominio, r["veredito"], r["detalhe"], r["crawl_delay"],
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    r["em_cache"] = False
    return r


def pode_raspar(url: str) -> bool:
    """False só quando há proibição EXPLÍCITA.

    Ausência de robots.txt não proíbe nada -- tratá-la como proibição foi o
    erro que tirou duas fontes do ar. Falha de rede também não: o site pode
    estar fora do ar, e negar por isso silenciaria a fonte sem motivo."""
    return veredito_para(url)["veredito"] != PROIBIDO


def auditar_fontes() -> list[dict]:
    """Confere todas as fontes do config. Usado no relatório e nos testes."""
    resultado = []
    vistos = set()
    for site in config.SITES:
        url = site.get("url_listagem") or site.get("base_url")
        if not url or _dominio(url) in vistos:
            continue
        vistos.add(_dominio(url))
        r = veredito_para(url)
        resultado.append({"fonte": site["nome"], "dominio": _dominio(url), **r})
        if r["veredito"] == PROIBIDO:
            log.warning(
                f"[{site['nome']}] robots.txt PROÍBE: {r['detalhe']} "
                f"-- a fonte não deve ser raspada"
            )
    return resultado
