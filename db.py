# -*- coding: utf-8 -*-
"""
Persistência em SQLite (módulo sqlite3 é nativo do Python -- nada para
instalar). Guarda todo imóvel já visto, quando foi visto pela primeira
vez e pela última vez, para sabermos o que é "novo" hoje.
"""
import json
import sqlite3
from datetime import date, datetime

import config
import utils
from utils import log

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

# Campos novos vindos do JSON-LD e do texto estruturado do card. Ficam NULL
# quando ausentes -- é NULL que permite medir completude e alimentar a fila
# de enriquecimento. O "Não Localizado" aparece só na exibição.
COLUNAS_NOVAS = {
    "logradouro": "TEXT",
    "banheiros": "INTEGER",
    "andar": "INTEGER",
    "idade_dias": "INTEGER",
    # custo decomposto (P-08): 'preco' sozinho misturava aluguel puro com
    # pacote de locação, e não havia como saber qual era qual
    "aluguel": "REAL",
    "condominio": "REAL",
    "iptu": "REAL",
    "custo_mensal_total": "REAL",
    "custo_completo": "INTEGER",
    "titulo_origem": "TEXT",
    "vagas": "INTEGER",
    "suites": "INTEGER",
    "descricao": "TEXT",
    "fotos": "TEXT",
    "condominio_nome": "TEXT",
    "imobiliaria": "TEXT",
    "telefone": "TEXT",
    "latitude": "REAL",
    "longitude": "REAL",
    "numero": "TEXT",
    "cep": "TEXT",
    # ligação com o imóvel consolidado (Fase 2)
    "imovel_id": "INTEGER",
    # ciclo de vida (Fase 3)
    "status": "TEXT",
    "ausencias_consec": "INTEGER",
    "ultima_confirmacao": "TEXT",
    "descricao_hash": "TEXT",
}

# ---------------------------------------------------------------------------
# Imóvel consolidado (P-03 da auditoria)
# ---------------------------------------------------------------------------
# A tabela 'imoveis' modela ANÚNCIO (uma publicação num portal, chaveada por
# URL). Faltava a unidade física: medido, 41 grupos de anúncios idênticos
# entre portais envolviam 101 dos 185 registros -- 55% da base era o mesmo
# apartamento repetido.
SQL_CRIAR_IMOVEL = """
CREATE TABLE IF NOT EXISTS imovel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT,
    cidade TEXT, bairro TEXT, logradouro TEXT, numero TEXT, cep TEXT,
    condominio_nome TEXT, latitude REAL, longitude REAL,
    quartos INTEGER, suites INTEGER, banheiros INTEGER, vagas INTEGER,
    area_m2 REAL, andar INTEGER,
    preco REAL, aluguel REAL, condominio REAL, iptu REAL,
    custo_mensal_total REAL, custo_completo INTEGER,
    preco_m2 REAL,
    qtd_fontes INTEGER,
    dias_anunciado INTEGER,
    titulo TEXT,
    primeiro_visto TEXT,
    ultimo_visto TEXT,
    ativo INTEGER DEFAULT 1
);
"""

# Ligação auditável: registra POR QUE estes anúncios são o mesmo imóvel,
# para que a decisão possa ser conferida e desfeita.
SQL_CRIAR_IMOVEL_ANUNCIO = """
CREATE TABLE IF NOT EXISTS imovel_anuncio (
    imovel_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    score_match REAL,
    classificacao TEXT,
    sinais TEXT,
    decidido_por TEXT DEFAULT 'auto',
    decidido_em TEXT,
    PRIMARY KEY (imovel_id, url)
);
"""

# Divergência entre fontes é registrada, nunca silenciada.
SQL_CRIAR_CONFLITO = """
CREATE TABLE IF NOT EXISTS conflito (
    imovel_id INTEGER NOT NULL,
    campo TEXT NOT NULL,
    valores TEXT,
    escolhido TEXT,
    criterio TEXT,
    detectado_em TEXT,
    PRIMARY KEY (imovel_id, campo)
);
"""

# ---------------------------------------------------------------------------
# Histórico por evento (P-07 da auditoria) -- Fase 3
# ---------------------------------------------------------------------------
# historico_precos guardava um snapshot por (url, data) com INSERT OR IGNORE:
# o preço era regravado igual todo dia e uma segunda mudança no mesmo dia era
# descartada em silêncio. Em 3 execuções isso produziu 261 linhas e ZERO
# variação observada.
#
# Evento grava só quando ALGO MUDA, com timestamp. Ocupa menos, não perde
# mudança intradiária, e o delta fica trivial de calcular.
SQL_CRIAR_EVENTO = """
CREATE TABLE IF NOT EXISTS evento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT,
    imovel_id INTEGER,
    execucao_id INTEGER,
    tipo TEXT NOT NULL,
    campo TEXT,
    valor_antes TEXT,
    valor_depois TEXT,
    delta REAL,
    delta_pct REAL,
    observado_em TEXT NOT NULL
);
"""
SQL_IX_EVENTO = [
    "CREATE INDEX IF NOT EXISTS ix_evento_url ON evento(url, observado_em)",
    "CREATE INDEX IF NOT EXISTS ix_evento_tipo ON evento(tipo, observado_em)",
    # As duas consultas mais quentes do pipeline faziam varredura completa.
    # Com 271 linhas isso é irrelevante; com coleta diária por 6 meses a
    # tabela passa de 20 mil e a varredura vira o gargalo.
    "CREATE INDEX IF NOT EXISTS ix_imoveis_visto ON imoveis(visto_na_ultima_execucao)",
    "CREATE INDEX IF NOT EXISTS ix_imoveis_imovel ON imoveis(imovel_id)",
    "CREATE INDEX IF NOT EXISTS ix_imoveis_site ON imoveis(site)",
    "CREATE INDEX IF NOT EXISTS ix_execfonte_fonte ON execucao_fonte(fonte, execucao_id)",
]

# Tipos de evento
EV_CRIADO = "CRIADO"
EV_PRECO = "PRECO_ALTERADO"
EV_DESCRICAO = "DESCRICAO_ALTERADA"
EV_ANUNCIANTE = "ANUNCIANTE_ALTERADO"
EV_SUMIU = "SUMIU"
EV_REAPARECEU = "REAPARECEU"
EV_SUSPEITO = "SUSPEITO"

# Ciclo de vida do anúncio
ATIVO = "ATIVO"
SUSPEITO = "SUSPEITO"
INATIVO = "INATIVO"

# Ausências consecutivas (com fonte saudável) antes de declarar o imóvel
# fora do ar. Duas, não uma: portal grande às vezes omite um anúncio de uma
# página por reordenação, e declarar "sumiu" na primeira falta gera alarme
# falso justamente nos imóveis que interessam.
AUSENCIAS_PARA_INATIVO = 2

SQL_CRIAR_HISTORICO = """
CREATE TABLE IF NOT EXISTS historico_precos (
    url TEXT NOT NULL,
    data TEXT NOT NULL,
    preco REAL,
    PRIMARY KEY (url, data)
);
"""

# ---------------------------------------------------------------------------
# Execuções (P-04 da auditoria)
# ---------------------------------------------------------------------------
# Sem registro de execução, ausência de um imóvel é ambígua: pode ser que ele
# saiu do ar, ou que o scraper daquela fonte quebrou. O código antigo tratava
# os dois casos igual -- marcava tudo como "não visto" antes de processar e
# seguia em frente mesmo quando uma fonte inteira falhava. Numa operação
# diária isso significaria anunciar que dezenas de imóveis sumiram sempre que
# um portal bloqueasse por alguns minutos.
SQL_CRIAR_EXECUCAO = """
CREATE TABLE IF NOT EXISTS execucao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    iniciada_em TEXT NOT NULL,
    encerrada_em TEXT,
    status TEXT,
    versao_codigo TEXT
);
"""

SQL_CRIAR_EXECUCAO_FONTE = """
CREATE TABLE IF NOT EXISTS execucao_fonte (
    execucao_id INTEGER NOT NULL,
    fonte TEXT NOT NULL,
    status TEXT NOT NULL,
    motivo TEXT,
    brutos INTEGER DEFAULT 0,
    aprovados INTEGER DEFAULT 0,
    indeterminados INTEGER DEFAULT 0,
    reprovados INTEGER DEFAULT 0,
    duracao_s REAL,
    erros INTEGER DEFAULT 0,
    PRIMARY KEY (execucao_id, fonte)
);
"""

# Status possíveis de uma fonte numa execução
OK = "OK"
PARCIAL = "PARCIAL"
FALHA = "FALHA"
BLOQUEADO = "BLOQUEADO"
SEM_ESTOQUE = "SEM_ESTOQUE"
PULADO = "PULADO"

# Uma fonte só autoriza concluir "este imóvel sumiu" se ela própria foi
# consultada com sucesso. PARCIAL fica de fora de propósito: volume anômalo
# é justamente o sintoma de extração quebrada.
STATUS_CONFIAVEIS = {OK}


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(config.ARQUIVO_DB)
    conn.execute(SQL_CRIAR_TABELA)
    conn.execute(SQL_CRIAR_HISTORICO)
    conn.execute(SQL_CRIAR_EXECUCAO)
    conn.execute(SQL_CRIAR_EXECUCAO_FONTE)
    conn.execute(SQL_CRIAR_IMOVEL)
    conn.execute(SQL_CRIAR_IMOVEL_ANUNCIO)
    conn.execute(SQL_CRIAR_CONFLITO)
    conn.execute(SQL_CRIAR_EVENTO)
    # migração: bancos criados antes do campo "cidade" existir não ganham a
    # coluna nova via CREATE TABLE IF NOT EXISTS (só afeta tabelas
    # inexistentes) -- adiciona à mão, ignorando se já existir.
    try:
        conn.execute(SQL_ADICIONAR_COLUNA_CIDADE)
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # mesma migração incremental para os campos de endereço/detalhe
    for coluna, tipo in COLUNAS_NOVAS.items():
        try:
            conn.execute(f"ALTER TABLE imoveis ADD COLUMN {coluna} {tipo}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # já existe

    # Índices SÓ depois do ALTER TABLE: indexar imovel_id antes de a coluna
    # existir levanta "no such column" e derruba toda conexão em banco antigo.
    for _ix in SQL_IX_EVENTO:
        try:
            conn.execute(_ix)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn


def abrir_execucao(versao_codigo: str = "") -> int:
    """Registra o início de uma rodada e devolve o id."""
    conn = conectar()
    cur = conn.execute(
        "INSERT INTO execucao (iniciada_em, status, versao_codigo) VALUES (?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), "EM_ANDAMENTO", versao_codigo),
    )
    execucao_id = cur.lastrowid
    conn.commit()
    conn.close()
    return execucao_id


def encerrar_execucao(execucao_id: int, status: str) -> None:
    conn = conectar()
    conn.execute(
        "UPDATE execucao SET encerrada_em = ?, status = ? WHERE id = ?",
        (datetime.now().isoformat(timespec="seconds"), status, execucao_id),
    )
    conn.commit()
    conn.close()


def mediana_brutos(fonte: str, n: int = 5) -> float | None:
    """Mediana de anúncios brutos das últimas n execuções bem-sucedidas
    desta fonte. Base da guarda de sanidade."""
    conn = conectar()
    cur = conn.execute(
        """
        SELECT brutos FROM execucao_fonte
        WHERE fonte = ? AND status IN (?, ?) AND brutos > 0
        ORDER BY execucao_id DESC LIMIT ?
        """,
        (fonte, OK, SEM_ESTOQUE, n),
    )
    valores = sorted(r[0] for r in cur)
    conn.close()
    if not valores:
        return None
    meio = len(valores) // 2
    if len(valores) % 2:
        return float(valores[meio])
    return (valores[meio - 1] + valores[meio]) / 2


def avaliar_sanidade(fonte: str, brutos: int, status: str) -> tuple[str, str | None]:
    """Rebaixa para PARCIAL quando o volume desaba sem erro técnico.

    Este é o ponto que impede o desastre do P-04. Se uma fonte devolve 3
    anúncios numa manhã em que a mediana histórica é 30, tecnicamente foi
    sucesso -- HTTP 200, sem exceção -- mas quase certamente o layout mudou.
    Tratar isso como sucesso faria o passo seguinte concluir que os 27
    imóveis restantes saíram do ar."""
    if status != OK:
        return status, None
    mediana = mediana_brutos(fonte)
    if mediana is None:
        return status, None  # sem histórico não há o que comparar
    if brutos == 0:
        return PARCIAL, f"zero anúncios (mediana histórica {mediana:.0f})"
    if brutos < mediana * 0.6:
        return PARCIAL, f"volume {brutos} < 60% da mediana histórica {mediana:.0f}"
    return status, None


def registrar_fonte(
    execucao_id: int,
    fonte: str,
    status: str,
    motivo: str | None = None,
    brutos: int = 0,
    aprovados: int = 0,
    indeterminados: int = 0,
    reprovados: int = 0,
    duracao_s: float | None = None,
    erros: int = 0,
) -> None:
    conn = conectar()
    conn.execute(
        """
        INSERT INTO execucao_fonte
            (execucao_id, fonte, status, motivo, brutos, aprovados,
             indeterminados, reprovados, duracao_s, erros)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(execucao_id, fonte) DO UPDATE SET
            status=excluded.status, motivo=excluded.motivo,
            brutos=excluded.brutos, aprovados=excluded.aprovados,
            indeterminados=excluded.indeterminados,
            reprovados=excluded.reprovados, duracao_s=excluded.duracao_s,
            erros=excluded.erros
        """,
        (execucao_id, fonte, status, motivo, brutos, aprovados,
         indeterminados, reprovados, duracao_s, erros),
    )
    conn.commit()
    conn.close()


def resumo_fontes(execucao_id: int) -> list[dict]:
    """Linhas de execucao_fonte de uma execução, para o painel de saúde."""
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM execucao_fonte WHERE execucao_id = ? ORDER BY brutos DESC",
        (execucao_id,),
    )
    resultado = [dict(r) for r in cur]
    conn.close()
    return resultado


def salvar_execucao(itens: list[dict], fontes_confiaveis: set[str] | None = None,
                    execucao_id: int | None = None) -> list[dict]:
    """Grava os itens encontrados na execução de hoje, atualiza
    primeiro_visto/ultimo_visto e devolve os itens com os campos
    'novo' (bool) e 'primeiro_visto' (str) preenchidos."""
    hoje = date.today().isoformat()
    conn = conectar()
    cur = conn.cursor()

    # Só zera o flag dos imóveis cujas fontes responderam com sucesso.
    #
    # A versão anterior fazia "UPDATE imoveis SET visto_na_ultima_execucao=0"
    # sem ressalva: se o Zap bloqueasse numa manhã, seus 37 imóveis saíam do
    # dashboard como se tivessem sido alugados. Agora, imóvel de fonte que
    # falhou preserva o estado anterior -- ausência só vira informação
    # quando a consulta foi confiável (STATUS_CONFIAVEIS).
    if fontes_confiaveis is None:
        cur.execute("UPDATE imoveis SET visto_na_ultima_execucao = 0")
    elif fontes_confiaveis:
        marcadores = ",".join("?" * len(fontes_confiaveis))
        cur.execute(
            f"UPDATE imoveis SET visto_na_ultima_execucao = 0 WHERE site IN ({marcadores})",
            tuple(fontes_confiaveis),
        )
    # fontes_confiaveis vazio = nenhuma fonte confiável nesta rodada;
    # não mexe em nada, para não esvaziar o dashboard por falha geral.

    for item in itens:
        cur.execute(
            """SELECT primeiro_visto, custo_mensal_total, preco, descricao_hash,
                      imobiliaria, COALESCE(status,'ATIVO')
               FROM imoveis WHERE url = ?""", (item["url"],))
        row = cur.fetchone()
        item["descricao_hash"] = _hash_texto(item.get("descricao"))

        if row:
            primeiro_visto = row[0]
            item["novo"] = False
            # Fase 3: registra o que MUDOU desde a última vez. Só grava
            # evento quando há diferença -- é essa a troca em relação ao
            # snapshot diário, que regravava o mesmo preço todo dia e
            # produziu 261 linhas com zero variação observada.
            custo_antes = row[1] if row[1] is not None else row[2]
            custo_agora = item.get("custo_mensal_total") or item.get("preco")
            if custo_antes and custo_agora and abs(custo_antes - custo_agora) >= 0.01:
                registrar_evento(cur, item["url"], EV_PRECO, "custo_mensal_total",
                                 custo_antes, custo_agora, execucao_id)
            if row[3] and item["descricao_hash"] and row[3] != item["descricao_hash"]:
                registrar_evento(cur, item["url"], EV_DESCRICAO, "descricao",
                                 execucao_id=execucao_id)
            if row[4] and item.get("imobiliaria") and row[4] != item["imobiliaria"]:
                registrar_evento(cur, item["url"], EV_ANUNCIANTE, "imobiliaria",
                                 row[4], item["imobiliaria"], execucao_id)
            # anúncio que estava fora do ar e voltou
            if row[5] in (SUSPEITO, INATIVO):
                registrar_evento(cur, item["url"], EV_REAPARECEU, execucao_id=execucao_id)
        else:
            primeiro_visto = hoje
            item["novo"] = True
            registrar_evento(cur, item["url"], EV_CRIADO, execucao_id=execucao_id)

        item["primeiro_visto"] = primeiro_visto

        cur.execute(
            """
            INSERT INTO imoveis (url, site, titulo, bairro, cidade, preco, quartos, area_m2,
                                  logradouro, banheiros, andar, idade_dias,
                                  aluguel, condominio, iptu, custo_mensal_total,
                                  custo_completo, titulo_origem, vagas, suites,
                                  descricao, fotos, condominio_nome, telefone, imobiliaria,
                                  descricao_hash, status, ausencias_consec, ultima_confirmacao,
                                  primeiro_visto, ultimo_visto, visto_na_ultima_execucao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(url) DO UPDATE SET
                site=excluded.site, titulo=excluded.titulo, bairro=excluded.bairro,
                cidade=excluded.cidade,
                preco=excluded.preco, quartos=excluded.quartos, area_m2=excluded.area_m2,
                logradouro=COALESCE(excluded.logradouro, imoveis.logradouro),
                banheiros=COALESCE(excluded.banheiros, imoveis.banheiros),
                andar=COALESCE(excluded.andar, imoveis.andar),
                idade_dias=excluded.idade_dias,
                aluguel=COALESCE(excluded.aluguel, imoveis.aluguel),
                condominio=COALESCE(excluded.condominio, imoveis.condominio),
                iptu=COALESCE(excluded.iptu, imoveis.iptu),
                custo_mensal_total=COALESCE(excluded.custo_mensal_total, imoveis.custo_mensal_total),
                custo_completo=excluded.custo_completo,
                titulo_origem=COALESCE(excluded.titulo_origem, imoveis.titulo_origem),
                vagas=COALESCE(excluded.vagas, imoveis.vagas),
                suites=COALESCE(excluded.suites, imoveis.suites),
                descricao=COALESCE(excluded.descricao, imoveis.descricao),
                fotos=COALESCE(excluded.fotos, imoveis.fotos),
                condominio_nome=COALESCE(excluded.condominio_nome, imoveis.condominio_nome),
                telefone=COALESCE(excluded.telefone, imoveis.telefone),
                imobiliaria=COALESCE(excluded.imobiliaria, imoveis.imobiliaria),
                descricao_hash=COALESCE(excluded.descricao_hash, imoveis.descricao_hash),
                status='ATIVO', ausencias_consec=0,
                ultima_confirmacao=excluded.ultima_confirmacao,
                ultimo_visto=excluded.ultimo_visto, visto_na_ultima_execucao=1
            """,
            (
                item["url"], item.get("site"), item.get("titulo"), item.get("bairro"),
                item.get("cidade"), item.get("preco"), item.get("quartos"), item.get("area_m2"),
                item.get("logradouro"), item.get("banheiros"), item.get("andar"),
                item.get("idade_dias"),
                item.get("aluguel"), item.get("condominio"), item.get("iptu"),
                item.get("custo_mensal_total"),
                1 if item.get("custo_completo") else 0,
                item.get("titulo_origem"), item.get("vagas"), item.get("suites"),
                item.get("descricao"),
                json.dumps(item["fotos"], ensure_ascii=False) if item.get("fotos") else None,
                item.get("condominio_nome"), item.get("telefone"), item.get("imobiliaria"),
                item.get("descricao_hash"), ATIVO, 0, hoje,
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


def _hash_texto(texto: str | None) -> str | None:
    """Hash curto de descrição, para detectar reescrita sem guardar tudo."""
    if not texto:
        return None
    import hashlib
    return hashlib.sha1(" ".join(texto.split()).lower().encode()).hexdigest()[:16]


def registrar_evento(cur, url, tipo, campo=None, antes=None, depois=None,
                     execucao_id=None, imovel_id=None):
    delta = delta_pct = None
    if isinstance(antes, (int, float)) and isinstance(depois, (int, float)) and antes:
        delta = round(depois - antes, 2)
        delta_pct = round(100 * (depois - antes) / antes, 2)
    cur.execute(
        """INSERT INTO evento (url, imovel_id, execucao_id, tipo, campo,
                               valor_antes, valor_depois, delta, delta_pct, observado_em)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (url, imovel_id, execucao_id, tipo, campo,
         None if antes is None else str(antes),
         None if depois is None else str(depois),
         delta, delta_pct, datetime.now().isoformat(timespec="seconds")),
    )


def aplicar_ciclo_de_vida(fontes_confiaveis: set[str] | None,
                          execucao_id: int | None = None) -> dict:
    """Marca ausentes como SUSPEITO e, na segunda falta, INATIVO.

    Só considera anúncio de fonte confiável -- é a mesma regra do P-04: se
    o Zap bloqueou, seus imóveis não 'sumiram', apenas não foram olhados.

    A dupla confirmação existe porque portal grande reordena resultado e
    às vezes omite um anúncio de uma página. Declarar 'sumiu' na primeira
    falta geraria alarme falso justamente nos imóveis que interessam."""
    if not fontes_confiaveis:
        return {"suspeitos": 0, "inativos": 0}

    conn = conectar()
    cur = conn.cursor()
    marcadores = ",".join("?" * len(fontes_confiaveis))
    ausentes = cur.execute(
        f"""SELECT url, site, COALESCE(ausencias_consec,0), COALESCE(status,'ATIVO')
            FROM imoveis
            WHERE visto_na_ultima_execucao = 0 AND site IN ({marcadores})
              AND COALESCE(status,'ATIVO') != ?""",
        (*fontes_confiaveis, INATIVO),
    ).fetchall()

    suspeitos = inativos = 0
    for url, _site, ausencias, _status in ausentes:
        ausencias += 1
        if ausencias >= AUSENCIAS_PARA_INATIVO:
            cur.execute("UPDATE imoveis SET status=?, ausencias_consec=? WHERE url=?",
                        (INATIVO, ausencias, url))
            registrar_evento(cur, url, EV_SUMIU, execucao_id=execucao_id)
            inativos += 1
        else:
            cur.execute("UPDATE imoveis SET status=?, ausencias_consec=? WHERE url=?",
                        (SUSPEITO, ausencias, url))
            suspeitos += 1

    conn.commit()
    conn.close()
    if suspeitos or inativos:
        log.info(f"Ciclo de vida: {suspeitos} suspeito(s), {inativos} marcado(s) como fora do ar")
    return {"suspeitos": suspeitos, "inativos": inativos}


def consolidar_imoveis(itens: list[dict]) -> list[dict]:
    """Agrupa os anúncios em imóveis físicos e persiste o resultado.

    Devolve a lista de imóveis consolidados, cada um com as fontes que o
    anunciam. É o que o dashboard passa a exibir: um apartamento, um card,
    N selos de fonte -- em vez das 3 linhas repetidas de hoje.

    O 'primeiro_visto' do imóvel é o MENOR entre os anúncios: se o Zap
    publicou primeiro e o Viva Real replicou depois, o imóvel está no mercado
    desde a data do Zap. Usar a data do anúncio mais recente faria um imóvel
    parado há meses parecer novidade."""
    import resolucao

    if not itens:
        return []

    agora = datetime.now().isoformat(timespec="seconds")
    grupos, _ = resolucao.agrupar(itens)
    conn = conectar()
    cur = conn.cursor()

    # Reconstrói a consolidação a cada rodada: os agrupamentos mudam quando
    # anúncios entram e saem, e manter ligação obsoleta é pior que refazer.
    cur.execute("DELETE FROM imovel_anuncio")
    cur.execute("DELETE FROM conflito")
    cur.execute("DELETE FROM imovel")

    consolidados = []
    for grupo in grupos:
        anuncios = [itens[i] for i in grupo]
        imovel, conflitos = resolucao.consolidar(anuncios)

        datas_ini = [a.get("primeiro_visto") for a in anuncios if a.get("primeiro_visto")]
        imovel["primeiro_visto"] = min(datas_ini) if datas_ini else date.today().isoformat()
        imovel["ultimo_visto"] = date.today().isoformat()
        imovel["dias_anunciado"] = (
            date.today() - date.fromisoformat(imovel["primeiro_visto"])
        ).days
        custo = imovel.get("custo_mensal_total") or imovel.get("preco")
        area = imovel.get("area_m2")
        imovel["preco_m2"] = round(custo / area, 2) if custo and area else None
        imovel["titulo"] = utils.gerar_titulo(imovel)
        imovel["novo"] = any(a.get("novo") for a in anuncios)

        # Anúncios individuais, do mais barato para o mais caro. É o que o
        # card expansível mostra: o mesmo apartamento costuma sair por
        # valores diferentes em cada portal, e ver a lista lado a lado
        # resolve duas coisas de uma vez -- mostra por onde fechar mais
        # barato, e deixa conferir a olho se o agrupamento faz sentido
        # (calibração pela interface, em vez de limiar cego).
        imovel["anuncios"] = sorted(
            [
                {
                    "site": a.get("site"),
                    "url": a.get("url"),
                    "preco": a.get("custo_mensal_total") or a.get("preco"),
                    "aluguel": a.get("aluguel"),
                    "condominio": a.get("condominio"),
                    "custo_completo": bool(a.get("custo_completo")),
                    "area_m2": a.get("area_m2"),
                    "quartos": a.get("quartos"),
                }
                for a in anuncios
            ],
            key=lambda x: (x["preco"] is None, x["preco"] or 0),
        )
        # o preço de vitrine é o menor: é o que você de fato pagaria
        precos = [x["preco"] for x in imovel["anuncios"] if x["preco"]]
        if precos:
            imovel["preco_min"] = min(precos)
            imovel["preco_max"] = max(precos)
            imovel["economia"] = round(max(precos) - min(precos), 2)

        cur.execute(
            """
            INSERT INTO imovel (criado_em, atualizado_em, cidade, bairro, logradouro,
                numero, cep, condominio_nome, latitude, longitude, quartos, suites,
                banheiros, vagas, area_m2, andar, preco, aluguel, condominio, iptu,
                custo_mensal_total, custo_completo, preco_m2, qtd_fontes,
                dias_anunciado, titulo, primeiro_visto, ultimo_visto, ativo)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            """,
            (agora, agora, imovel.get("cidade"), imovel.get("bairro"),
             imovel.get("logradouro"), imovel.get("numero"), imovel.get("cep"),
             imovel.get("condominio_nome"), imovel.get("latitude"), imovel.get("longitude"),
             imovel.get("quartos"), imovel.get("suites"), imovel.get("banheiros"),
             imovel.get("vagas"), imovel.get("area_m2"), imovel.get("andar"),
             imovel.get("preco"), imovel.get("aluguel"), imovel.get("condominio"),
             imovel.get("iptu"), imovel.get("custo_mensal_total"),
             1 if imovel.get("custo_completo") else 0, imovel.get("preco_m2"),
             imovel.get("qtd_fontes"), imovel["dias_anunciado"], imovel["titulo"],
             imovel["primeiro_visto"], imovel["ultimo_visto"]),
        )
        imovel_id = cur.lastrowid
        imovel["id"] = imovel_id

        for a in anuncios:
            cur.execute(
                """INSERT OR REPLACE INTO imovel_anuncio
                   (imovel_id, url, score_match, classificacao, decidido_em)
                   VALUES (?,?,?,?,?)""",
                (imovel_id, a.get("url"), 1.0 if len(grupo) == 1 else None,
                 "UNICO" if len(grupo) == 1 else resolucao.MESMO_IMOVEL, agora),
            )
            cur.execute("UPDATE imoveis SET imovel_id=? WHERE url=?",
                        (imovel_id, a.get("url")))

        for c in conflitos:
            cur.execute(
                """INSERT OR REPLACE INTO conflito
                   (imovel_id, campo, valores, escolhido, criterio, detectado_em)
                   VALUES (?,?,?,?,?,?)""",
                (imovel_id, c["campo"], json.dumps(c["valores"], ensure_ascii=False,
                                                   default=str),
                 str(c["escolhido"]), c["criterio"], agora),
            )
        imovel["conflitos"] = conflitos
        consolidados.append(imovel)

    conn.commit()
    conn.close()

    multi = sum(1 for i in consolidados if i.get("qtd_fontes", 1) > 1)
    log.info(
        f"Consolidação: {len(itens)} anúncios -> {len(consolidados)} imóveis "
        f"({multi} com 2+ fontes)"
    )
    return consolidados


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


