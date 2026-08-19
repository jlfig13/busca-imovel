# -*- coding: utf-8 -*-
import logging
import random
import re
import time
from datetime import date

import requests

import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def setup_logger():
    import os
    os.makedirs(config.PASTA_SAIDA, exist_ok=True)
    logger = logging.getLogger("apt_scraper")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(config.ARQUIVO_LOG, encoding="utf-8")
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger


log = setup_logger()


# ---------------------------------------------------------------------------
# Classificação de falha (P-11 da auditoria)
# ---------------------------------------------------------------------------
# "Deu erro" não é informação suficiente: bloqueio anti-bot, timeout e página
# legitimamente vazia exigem reações opostas. Sem essa distinção, uma falha
# de rede de 5 segundos zera uma fonte e -- combinada com P-04 -- faz o
# sistema anunciar que 30 imóveis desapareceram.
FALHA_TIMEOUT = "timeout"
FALHA_CONEXAO = "conexao"
FALHA_HTTP_4XX = "http_4xx"
FALHA_HTTP_5XX = "http_5xx"
FALHA_BLOQUEIO = "challenge_anti_bot"

# Marcas de página de desafio (Cloudflare / DataDome / reCAPTCHA). Uma
# resposta 200 contendo isto NÃO é conteúdo: é bloqueio disfarçado de
# sucesso, e tratá-la como página vazia é o que faz o scraper concluir
# "esta fonte não tem mais imóveis".
_MARCAS_BLOQUEIO = (
    "cf-browser-verification", "cf_chl_opt", "just a moment",
    "checking your browser", "datadome", "captcha-delivery",
    "geo.captcha-delivery.com", "verificando seu navegador",
    "access denied", "unusual traffic",
)


def detectar_bloqueio(html: str | None) -> bool:
    """True quando o corpo é uma página de desafio anti-bot, não conteúdo."""
    if not html:
        return False
    # o teto evita varrer 600 KB de listagem legítima a cada chamada:
    # desafios são páginas pequenas
    amostra = html[:20000].lower()
    return any(m in amostra for m in _MARCAS_BLOQUEIO)


def get_html(url: str, timeout: int = 20, retries: int = 2) -> str | None:
    """Compatibilidade: só o HTML, descartando o diagnóstico."""
    html, _ = get_html_diag(url, timeout=timeout, retries=retries)
    return html


def get_html_diag(
    url: str, timeout: int = 20, retries: int = 2
) -> tuple[str | None, str | None]:
    """Busca uma página e devolve (html, motivo_da_falha).

    Backoff exponencial com jitter, em vez do sleep fixo de 1,5 s: repetir
    na mesma cadência contra um servidor sob pressão costuma prolongar o
    problema em vez de contorná-lo. O jitter evita que todas as fontes
    voltem a bater no mesmo instante."""
    motivo = None
    for tentativa in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                if detectar_bloqueio(resp.text):
                    motivo = FALHA_BLOQUEIO
                    log.warning(f"Bloqueio anti-bot detectado em {url}")
                else:
                    return resp.text, None
            elif 400 <= resp.status_code < 500:
                motivo = FALHA_BLOQUEIO if resp.status_code in (403, 429) else FALHA_HTTP_4XX
                log.warning(f"HTTP {resp.status_code} em {url}")
                # 404/410 não melhoram com repetição
                if resp.status_code in (404, 410):
                    return None, motivo
            else:
                motivo = FALHA_HTTP_5XX
                log.warning(f"HTTP {resp.status_code} em {url}")
        except requests.Timeout:
            motivo = FALHA_TIMEOUT
            log.warning(f"Timeout em {url}")
        except requests.RequestException as e:
            motivo = FALHA_CONEXAO
            log.warning(f"Erro ao buscar {url}: {e}")

        if tentativa < retries:
            espera = (2 ** tentativa) * 1.5 + random.uniform(0, 0.75)
            time.sleep(espera)
    return None, motivo


def get_html_brightdata(url: str) -> str | None:
    """Busca uma página via Bright Data Web Unlocker (bypassa Cloudflare/
    DataDome). Requer BRIGHTDATA_API_KEY e BRIGHTDATA_UNLOCKER_ZONE em config.py."""
    if not config.BRIGHTDATA_API_KEY or not config.BRIGHTDATA_UNLOCKER_ZONE:
        return None
    try:
        resp = requests.post(
            "https://api.brightdata.com/request",
            headers={"Authorization": f"Bearer {config.BRIGHTDATA_API_KEY}"},
            json={"zone": config.BRIGHTDATA_UNLOCKER_ZONE, "url": url, "format": "raw"},
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.text
        log.warning(f"Bright Data HTTP {resp.status_code} em {url}")
    except requests.RequestException as e:
        log.warning(f"Erro Bright Data em {url}: {e}")
    return None


def fetch(url: str, prefer_brightdata: bool = False) -> str | None:
    """Escolhe a melhor estratégia de busca disponível."""
    if prefer_brightdata:
        html = get_html_brightdata(url)
        if html:
            return html
        log.info(f"Bright Data indisponível/falhou, tentando requests simples: {url}")
    return get_html(url)


# ---------------------------------------------------------------------------
# Bairro a partir do slug da URL (P-18 da auditoria)
# ---------------------------------------------------------------------------
# O bairro costuma estar escrito na própria URL do anúncio, gerado pelo
# portal a partir do cadastro -- normalmente mais confiável que o texto
# renderizado do card, e de graça (não custa requisição).
#   Portal CRECI:    /Anuncio/Index/apartamento-3-quarto-alugar-114m2-pina-recife--pe_33327742
#   Cristina Mirele: /imovel/4314734/apartamento-locacao-olinda-pe-bairro-novo-edf-estacao-verde
#
# Só devolve valor que casa com a lista canônica de bairros -- do contrário
# repetiríamos o erro do P-05, em que regex solto gravou "Pernambuco" e
# "somos a referência local em so" como se fossem bairros.

# Bairros de Recife, Olinda e Jaboatão em forma de slug. Núcleo inicial do
# gazetteer que a Fase 2 vai completar a partir de fonte oficial (IBGE /
# prefeitura); por ora cobre o que aparece na base real.
BAIRROS_CANONICOS = {
    # Recife
    "boa-viagem": "Boa Viagem", "pina": "Pina", "imbiribeira": "Imbiribeira",
    "iputinga": "Iputinga", "varzea": "Várzea", "cordeiro": "Cordeiro",
    "madalena": "Madalena", "torre": "Torre", "gracas": "Graças",
    "espinheiro": "Espinheiro", "rosarinho": "Rosarinho", "aflitos": "Aflitos",
    "casa-forte": "Casa Forte", "casa-amarela": "Casa Amarela",
    "parnamirim": "Parnamirim", "tamarineira": "Tamarineira",
    "encruzilhada": "Encruzilhada", "arruda": "Arruda", "campo-grande": "Campo Grande",
    "boa-vista": "Boa Vista", "santo-amaro": "Santo Amaro", "derby": "Derby",
    "ilha-do-leite": "Ilha do Leite", "afogados": "Afogados", "barro": "Barro",
    "cohab": "Cohab", "ibura": "Ibura", "jordao": "Jordão", "setubal": "Setúbal",
    "caxanga": "Caxangá", "san-martin": "San Martin", "areias": "Areias",
    "estancia": "Estância", "tejipio": "Tejipió", "curado": "Curado",
    "jardim-sao-paulo": "Jardim São Paulo", "sancho": "Sancho",
    "torroes": "Torrões", "engenho-do-meio": "Engenho do Meio",
    "cidade-universitaria": "Cidade Universitária", "zumbi": "Zumbi",
    "prado": "Prado", "soledade": "Soledade", "santo-antonio": "Santo Antônio",
    "recife-antigo": "Recife Antigo", "sao-jose": "São José",
    "poco-da-panela": "Poço da Panela", "monteiro": "Monteiro",
    "apipucos": "Apipucos", "dois-irmaos": "Dois Irmãos",
    # Olinda
    "casa-caiada": "Casa Caiada", "bairro-novo": "Bairro Novo",
    "jardim-atlantico": "Jardim Atlântico", "rio-doce": "Rio Doce",
    "fragoso": "Fragoso", "ouro-preto": "Ouro Preto", "aguas-compridas": "Águas Compridas",
    "peixinhos": "Peixinhos", "agua-fria": "Água Fria", "carmo": "Carmo",
    "amaro-branco": "Amaro Branco", "bonsucesso": "Bonsucesso",
    "jardim-brasil": "Jardim Brasil", "sitio-historico": "Sítio Histórico",
    # Jaboatão dos Guararapes
    "piedade": "Piedade", "candeias": "Candeias", "barra-de-jangada": "Barra de Jangada",
    "prazeres": "Prazeres", "cajueiro-seco": "Cajueiro Seco",
    "curado-ii": "Curado II", "socorro": "Socorro",
}

# Cidade de cada bairro. Sem isso, um anúncio do OLX em Casa Caiada ou Rio
# Doce (Olinda) entrava como Recife -- o padrão do site --, e com isso era
# avaliado pelo perfil errado (Recife exige 2 quartos/60m², Olinda 3/70) e
# sumia do filtro de cidade no dashboard.
CIDADE_DO_BAIRRO = {}
for _slug in ("casa-caiada", "bairro-novo", "jardim-atlantico", "rio-doce",
              "fragoso", "ouro-preto", "aguas-compridas", "peixinhos",
              "agua-fria", "carmo", "amaro-branco", "bonsucesso",
              "jardim-brasil", "sitio-historico"):
    CIDADE_DO_BAIRRO[_slug] = "Olinda"
for _slug in ("piedade", "candeias", "barra-de-jangada", "prazeres",
              "cajueiro-seco", "curado-ii", "socorro"):
    CIDADE_DO_BAIRRO[_slug] = "Jaboatão dos Guararapes"


def cidade_do_bairro(bairro: str) -> str | None:
    """Cidade a que um bairro canônico pertence, quando não é Recife.

    Bairro é o dado mais confiável que temos depois da correção do P-18;
    usá-lo para corrigir a cidade evita que o padrão do site (quase sempre
    'Recife') contamine anúncios da região metropolitana."""
    if not bairro:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", _sem_acento(bairro).lower()).strip("-")
    return CIDADE_DO_BAIRRO.get(slug)


# Ordena do slug mais longo para o mais curto: sem isso "casa-forte" seria
# capturado por "casa-caiada"? não -- mas "curado" casaria dentro de
# "curado-ii" e devolveria o bairro errado.
_BAIRROS_ORDENADOS = sorted(BAIRROS_CANONICOS, key=len, reverse=True)


# Texto usado quando um campo não foi encontrado. Preenchido na saída
# (dashboard/Excel), nunca no banco: no banco o ausente continua sendo NULL,
# porque é NULL que permite contar completude e alimentar a fila de
# enriquecimento. Gravar a string faria "Não Localizado" virar um valor.
NAO_LOCALIZADO = "Não Localizado"


def ou_nao_localizado(valor, sufixo: str = "") -> str:
    """Formata para exibição, marcando explicitamente o que falta."""
    if valor is None or valor == "" or valor == []:
        return NAO_LOCALIZADO
    return f"{valor}{sufixo}"


# Endereço no texto do card. Dois formatos medidos ao vivo em 18/08/2026:
#   Imovelweb: "Av. Min. Marcos Freire\nCasa Caiada, Olinda"
#   Moradasol: "...ApartamentoBoa Viagem - Recife - PEEd. Bouganvile60 m²..."
# Eram os dois únicos responsáveis pelos 13% de imóveis sem bairro.
_RE_LOGRADOURO = re.compile(
    r"^((?:R\.|Rua|Av\.|Avenida|Trav\.|Travessa|Estrada|Rod\.|Pra[çc]a|Alameda)"
    r"[^\n,]{3,70})$",
    re.MULTILINE | re.IGNORECASE,
)
# "Bairro, Cidade" em linha própria (Imovelweb)
_RE_BAIRRO_CIDADE = re.compile(
    r"^([A-Za-zÀ-ú][A-Za-zÀ-ú .']{2,34}),\s*"
    r"(Recife|Olinda|Jaboat[aã]o(?: dos Guararapes)?|Paulista|Camaragibe)\s*$",
    re.MULTILINE,
)
# "Bairro - Cidade - PE" (Moradasol)
_RE_BAIRRO_TRACO = re.compile(
    r"([A-Za-zÀ-ú][A-Za-zÀ-ú .']{2,34})\s*-\s*"
    r"(Recife|Olinda|Jaboat[aã]o(?: dos Guararapes)?|Paulista|Camaragibe)\s*-\s*PE"
)


def endereco_do_texto(texto: str) -> tuple[str | None, str | None, str | None]:
    """Extrai (logradouro, bairro, cidade) do texto do card.

    O bairro só é aceito se casar com BAIRROS_CANONICOS -- mesma trava de
    bairro_do_slug. Sem ela, um regex posicional como este captura qualquer
    coisa que esteja na posição certa, que foi como "Pernambuco" e um trecho
    de rodapé viraram bairros na base (P-05)."""
    if not texto:
        return None, None, None

    logradouro = None
    m = _RE_LOGRADOURO.search(texto)
    if m:
        logradouro = m.group(1).strip()

    for regex in (_RE_BAIRRO_CIDADE, _RE_BAIRRO_TRACO):
        m = regex.search(texto)
        if not m:
            continue
        candidato = m.group(1).strip()
        canonico = _canonizar_bairro(candidato)
        if canonico:
            cidade = m.group(2).strip()
            if cidade.lower().startswith("jaboat"):
                cidade = "Jaboatão dos Guararapes"
            return logradouro, canonico, cidade
    return logradouro, None, None


def bairro_no_inicio(texto: str, limite: int = 90) -> str | None:
    """Último recurso: bairro canônico citado no começo do texto.

    Alguns sites abrem o título com o bairro e nada mais o marca -- o Camila
    Melo renderiza "Boa Vista Apartamento Semi-mobiliado para locação...".

    Limitado ao início de propósito: procurar no texto inteiro capturaria
    bairro citado como referência ("a 10 min de Boa Viagem") e atribuiria ao
    imóvel errado, que é pior que não ter bairro."""
    if not texto:
        return None
    inicio = _sem_acento(texto[:limite]).lower()
    melhor = None
    for slug, canonico in BAIRROS_CANONICOS.items():
        alvo = slug.replace("-", " ")
        if len(alvo) < 5:
            continue
        for m in re.finditer(rf"(?:^|\W){re.escape(alvo)}(?:\W|$)", inicio):
            # Rejeita menção de proximidade: "a 10 minutos de Boa Viagem"
            # descreve a vizinhança, não onde o imóvel fica. Atribuir o
            # bairro errado é pior que não ter bairro (mesma lógica de P-05).
            antes = inicio[max(0, m.start() - 26):m.start()]
            if re.search(
                r"\b(perto|proxim[oa]s?|vizinh|minutos?|min|km|metros|"
                r"acesso|caminho|rumo|sentido|entre)\b", antes
            ):
                continue
            if melhor is None or len(alvo) > len(melhor[0]):
                melhor = (alvo, canonico)
    return melhor[1] if melhor else None


def _canonizar_bairro(nome: str) -> str | None:
    """Converte um nome de bairro para a forma canônica, ou None.

    Aceita o nome colado a texto anterior porque é assim que ele chega em
    alguns sites: o Moradasol renderiza o card sem separador e o bloco sai
    como "ApartamentoBoa Viagem - Recife - PE". Casar só o nome exato
    perderia todos esses -- eram 2 dos 7 imóveis sem bairro.

    Compara sem acento, caixa nem pontuação, e exige 5+ caracteres para o
    sufixo não casar por acidente dentro de outra palavra."""
    if not nome:
        return None
    limpo = re.sub(r"[^a-z0-9]+", "", _sem_acento(nome).lower())
    if not limpo:
        return None
    melhor = None
    for slug, canonico in BAIRROS_CANONICOS.items():
        alvo = slug.replace("-", "")
        if len(alvo) < 5:
            continue
        if limpo == alvo or limpo.endswith(alvo):
            # o mais longo vence: "casaamarela" antes de "amarela"
            if melhor is None or len(alvo) > len(melhor[0]):
                melhor = (alvo, canonico)
    return melhor[1] if melhor else None


def _sem_acento(s: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def bairro_do_slug(url: str) -> str | None:
    """Extrai o bairro do slug da URL, validado contra BAIRROS_CANONICOS.

    Devolve None quando nada casa -- é melhor não ter bairro do que gravar
    um pedaço aleatório de slug."""
    if not url:
        return None
    alvo = url.lower()
    for slug in _BAIRROS_ORDENADOS:
        # exige separador (ou fim) nas bordas para não casar no meio de
        # outra palavra, ex: "torre" dentro de "torreao"
        if re.search(rf"(?:^|[/\-_]){re.escape(slug)}(?:[/\-_]|$)", alvo):
            return BAIRROS_CANONICOS[slug]
    return None


def cidade_do_slug(url: str) -> str | None:
    """Detecta a cidade no slug da URL (mesmo racional de bairro_do_slug)."""
    if not url:
        return None
    alvo = url.lower()
    for slug, nome in (
        ("jaboatao-dos-guararapes", "Jaboatão dos Guararapes"),
        ("jaboatao", "Jaboatão dos Guararapes"),
        ("olinda", "Olinda"),
        ("recife", "Recife"),
        ("paulista", "Paulista"),
        ("camaragibe", "Camaragibe"),
    ):
        if re.search(rf"(?:^|[/\-_]){re.escape(slug)}(?:[/\-_]|$)", alvo):
            return nome
    return None


# ---------------------------------------------------------------------------
# Parsing de texto
# ---------------------------------------------------------------------------

def parse_preco(texto: str) -> float | None:
    """Extrai um valor monetário em R$ de um texto livre, ex: 'R$: 3.500,00' -> 3500.0
    IMPORTANTE: exige o símbolo R$ explicitamente. Uma versão anterior tinha
    R$ como totalmente opcional, o que fazia a função capturar por engano
    qualquer número do texto (como a contagem de quartos) quando ele
    aparecia antes do preço no bloco de texto."""
    if not texto:
        return None
    match = re.search(r"R\$:?\s*([\d.]+,\d{2}|[\d.]+)", texto.replace("\xa0", " "))
    if not match:
        return None
    valor_str = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(valor_str)
    except ValueError:
        return None


def parse_quartos(texto: str) -> int | None:
    """Extrai número de quartos de um texto livre. Cobre:
    '3 Quarto(s)' (maioria), 'bed 3' (Imobzi), 'Dormitórios\t3' (Tecimob)."""
    if not texto:
        return None
    # número antes do label: "3 quartos", "3 dormitórios"
    match = re.search(r"(\d+)\s*(?:quarto|dormit[oó]rio|dorm)", texto, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # número depois do label: "Dormitórios\t3" (Tecimob)
    match = re.search(r"(?:quarto|dormit[oó]rio|dorm)[s]?\s*[\t:]\s*(\d+)", texto, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # "bed 3" (Imobzi)
    match = re.search(r"\bbed\D{0,6}?(\d+)", texto, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def parse_area(texto: str) -> float | None:
    """Extrai a área útil em m², ex: 'Área Útil: 39.00 m²' -> 39.0
    Lida tanto com sites que usam ponto como separador decimal (39.00)
    quanto com o padrão brasileiro (1.234,00)."""
    if not texto:
        return None
    match = re.search(r"([\d.,]+)\s*m(?:²|2\b)", texto)
    if not match:
        return None
    valor_str = match.group(1)
    if "," in valor_str:
        valor_str = valor_str.replace(".", "").replace(",", ".")
    elif valor_str.count(".") == 1 and len(valor_str.split(".")[-1]) == 2:
        pass  # ponto já é decimal, ex: 39.00
    else:
        valor_str = valor_str.replace(".", "")
    try:
        return float(valor_str)
    except ValueError:
        return None


def parse_preco_aluguel(texto: str) -> float | None:
    """Prioriza o valor de aluguel quando o mesmo bloco de texto também
    mostra condomínio, IPTU ou valor 'total'. Cobre dois padrões:
    'Aluguel R$ X' (Âncora) e 'R$ X /aluguel' (Imobzi).
    IMPORTANTE: o padrão Imobzi é tentado primeiro -- do contrário, um
    texto como 'R$ 2.400 /aluguel R$ 3.004 /total' faria o padrão
    'Aluguel R$' casar por engano com o segundo valor (/total)."""
    if not texto:
        return None
    match = re.search(r"R\$\s*([\d.,]+)\s*/\s*aluguel", texto, re.IGNORECASE)
    if match:
        return parse_preco(match.group(0))
    match = re.search(r"Aluguel\s*R?\$:?\s*([\d.,]+)", texto, re.IGNORECASE)
    if match:
        return parse_preco(match.group(0))
    return parse_preco(texto)


def _parse_valor_br(s: str) -> float | None:
    s = s.strip().replace("\xa0", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


_RE_CONDOMINIO = re.compile(
    r"(?:[Cc]ondom[íi]nio|[Cc]ond\.)\s*:?\s*R\$\s*([\d.,]+)"
)
_RE_IPTU = re.compile(r"IPTU\s*:?\s*R\$\s*([\d.,]+)", re.IGNORECASE)
_RE_PACOTE = re.compile(r"[Pp]acote\s+de\s+loca[çc][aã]o\s*R\$\s*([\d.,]+)")


def decompor_custo(texto: str) -> dict:
    """Separa aluguel, condomínio e IPTU em vez de devolver um número só.

    P-08 da auditoria: o código antigo somava tudo num campo 'preco'. Com
    isso um imóvel de R$ 2.400 de aluguel puro parecia mais caro que um de
    R$ 2.048 que já embutia R$ 200 de condomínio e R$ 145 de IPTU -- quando
    na verdade o segundo custa R$ 2.393 só de aluguel. Você comparava maçã
    com laranja sem ter como saber qual era qual.

    'completo' indica se dá para confiar no total: quando o card não informa
    condomínio, o total é um piso, não o custo real.
    """
    vazio = {"aluguel": None, "condominio": None, "iptu": None,
             "custo_mensal_total": None, "custo_completo": False}
    if not texto:
        return vazio

    condominio = iptu = None
    m = _RE_CONDOMINIO.search(texto)
    if m:
        condominio = _parse_valor_br(m.group(1))
    m = _RE_IPTU.search(texto)
    if m:
        iptu = _parse_valor_br(m.group(1))

    # "Pacote de locação" é o total já somado pelo site. Nesse caso o
    # aluguel isolado é o que sobra depois de tirar os encargos conhecidos.
    m = _RE_PACOTE.search(texto)
    if m:
        total = _parse_valor_br(m.group(1))
        if total:
            aluguel = total - (condominio or 0) - (iptu or 0)
            return {
                "aluguel": aluguel if aluguel > 0 else None,
                "condominio": condominio, "iptu": iptu,
                "custo_mensal_total": total,
                "custo_completo": True,
            }

    aluguel = parse_preco_aluguel(texto)
    if aluguel is None:
        return vazio

    total = aluguel + (condominio or 0) + (iptu or 0)
    return {
        "aluguel": aluguel,
        "condominio": condominio,
        "iptu": iptu,
        "custo_mensal_total": total,
        # só é completo quando o condomínio foi informado; IPTU costuma
        # estar embutido ou ser isento, condomínio praticamente nunca é zero
        "custo_completo": condominio is not None,
    }


def parse_preco_total(texto: str) -> float | None:
    """Custo total de locação = aluguel + condomínio + IPTU + taxas.
    Ordem de tentativa:
    1. 'Pacote de locação R$ X' — site já somou tudo
    2. Aluguel + Condomínio + IPTU somados explicitamente
    3. Fallback: parse_preco_aluguel (só aluguel)"""
    if not texto:
        return None
    m = re.search(r"[Pp]acote\s+de\s+loca[çc][aã]o\s*R\$\s*([\d.,]+)", texto)
    if m:
        v = _parse_valor_br(m.group(1))
        if v:
            return v
    aluguel = parse_preco_aluguel(texto)
    if aluguel:
        total = aluguel
        m_cond = re.search(r"(?:[Cc]ondom[íi]nio|[Cc]ond\.)\s*R\$\s*([\d.,]+)", texto)
        if m_cond:
            v = _parse_valor_br(m_cond.group(1))
            if v:
                total += v
        m_iptu = re.search(r"IPTU\s*R\$\s*([\d.,]+)", texto)
        if m_iptu:
            v = _parse_valor_br(m_iptu.group(1))
            if v:
                total += v
        return total
    return None


def gerar_titulo(item: dict) -> str:
    """Título determinístico a partir dos campos normalizados.

    P-06 da auditoria: o título raspado do card era frequentemente lixo --
    '+6 fotos' (Viva Real e Zap), 'IMÓVEIS' (CTI), string vazia (OLX), ou o
    card inteiro concatenado com \\r\\n (Rede Imóveis). Título é o que se lê
    primeiro na lista; '+6 fotos' não ajuda a decidir nada.

    Gerado a partir dos campos, é sempre legível e comparável entre fontes.
    O texto original vira 'titulo_origem', para auditoria e para o matching
    de descrição da deduplicação."""
    partes = ["Apartamento"]
    if item.get("quartos"):
        q = int(item["quartos"])
        partes.append(f"{q} quarto" + ("s" if q != 1 else ""))
    if item.get("area_m2"):
        partes.append(f"{item['area_m2']:.0f} m²")
    if item.get("vagas"):
        v = int(item["vagas"])
        partes.append(f"{v} vaga" + ("s" if v != 1 else ""))
    local = item.get("bairro") or item.get("cidade")
    if local:
        partes.append(str(local))
    return " · ".join(partes)


_TIPO_NAO_RESIDENCIAL = re.compile(
    r"\bsala\s+comercial\b|\bgalp[aã]o\b|\bterreno\b|\bconsult[oó]rio\b"
    r"|\bestablecimento\s+comercial\b|\bponto\s+comercial\b",
    re.IGNORECASE,
)


def titulo_aceito(titulo: str) -> bool:
    """False para imóveis claramente não-residenciais."""
    return not _TIPO_NAO_RESIDENCIAL.search(titulo or "")


# ---------------------------------------------------------------------------
# Idade do anúncio
# ---------------------------------------------------------------------------
# O Portal CRECI carimba "Atualizado em: dd/mm/aaaa hh:mm:ss" em cada card, e
# boa parte do inventário está parada há meses. Anúncio velho de aluguel é
# quase sempre imóvel já alugado que ninguém baixou -- ocupa a lista e faz
# perder tempo com contato que não vai a lugar nenhum.
_RE_ATUALIZADO_EM = re.compile(
    r"Atualizado\s+em:?\s*(\d{2})/(\d{2})/(\d{4})", re.IGNORECASE
)


def data_atualizacao(texto: str):
    """Devolve a data de atualização declarada no card, ou None."""
    if not texto:
        return None
    m = _RE_ATUALIZADO_EM.search(texto)
    if not m:
        return None
    dia, mes, ano = (int(g) for g in m.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def anuncio_recente(texto: str, dias_max: int | None = None) -> tuple[bool, int | None]:
    """(é_recente, idade_em_dias) conforme a data declarada no card.

    Sem data declarada devolve (True, None): ausência de carimbo não é prova
    de anúncio velho, e a maioria das fontes simplesmente não informa. Só
    descarta quando a própria fonte diz que está desatualizado."""
    if dias_max is None:
        dias_max = config.MAX_DIAS_DESDE_ATUALIZACAO
    data = data_atualizacao(texto)
    if data is None:
        return True, None
    idade = (date.today() - data).days
    return idade <= dias_max, idade


# ---------------------------------------------------------------------------
# Veredito de filtro -- três estados (P-01 da auditoria)
# ---------------------------------------------------------------------------
# A versão anterior devolvia um booleano, e "não sei o preço" era
# indistinguível de "o preço serve": passa_no_filtro(None, None, None, None)
# devolvia True. Resultado medido na base: 56 dos 57 anúncios do OLX entraram
# sem preço, quartos, área, bairro nem cidade -- lixo contado como imóvel
# aprovado, poluindo dashboard, planilha e qualquer estatística.
#
# A intenção original ("melhor mostrar de mais do que perder oportunidade")
# continua valendo -- o que muda é que o incerto agora é rotulado como
# incerto em vez de se disfarçar de aprovado.
APROVADO = "APROVADO"
INDETERMINADO = "INDETERMINADO"
REPROVADO = "REPROVADO"


def avaliar_filtro(preco, quartos, area=None, cidade=None) -> tuple[str, list[str]]:
    """Avalia um anúncio contra os filtros e devolve (veredito, motivos).

    REPROVADO      -- algum campo CONHECIDO viola o filtro. Descarta.
    APROVADO       -- há dado suficiente para afirmar que serve.
    INDETERMINADO  -- nada viola, mas falta dado essencial para decidir.
                      Não é lixo nem aprovado: é candidato a enriquecimento
                      pela página de detalhe (Fase 2 do roadmap).

    O mínimo para APROVADO é preço conhecido e dentro da faixa, mais pelo
    menos um entre quartos e área -- sem nenhum dos dois não dá para aplicar
    o perfil da cidade, e o anúncio não passa de um link com um valor.
    """
    motivos: list[str] = []
    f = config.FILTROS
    perfil = config.FILTROS_POR_CIDADE.get(cidade, config.FILTRO_PADRAO)

    # 1. reprovação: só com dado conhecido na mão
    if preco is not None and not (f["preco_min"] <= preco <= f["preco_max"]):
        return REPROVADO, [f"preço {preco:.0f} fora de {f['preco_min']}-{f['preco_max']}"]
    if quartos is not None and quartos < perfil["quartos_min"]:
        return REPROVADO, [f"quartos {quartos} < {perfil['quartos_min']}"]
    if area is not None and area < perfil["area_min"]:
        return REPROVADO, [f"área {area:.0f}m² < {perfil['area_min']}m²"]

    # 2. dado suficiente para aprovar?
    if preco is None:
        motivos.append("preço ausente")
    if quartos is None and area is None:
        motivos.append("quartos e área ausentes")

    return (APROVADO, []) if not motivos else (INDETERMINADO, motivos)


class ListaComStats(list):
    """Lista de imóveis aprovados que também carrega o diagnóstico da coleta.

    Existe para que o scraper informe quantos anúncios brutos viu, quantos
    ficaram indeterminados e se houve bloqueio -- sem isso main.py só
    enxerga o resultado final e não consegue distinguir 'fonte sem estoque'
    de 'fonte quebrada' (P-04). É list de propósito: todo o código que já
    trata o retorno como lista continua funcionando."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats: dict = {
            "brutos": 0, "indeterminados": 0, "reprovados": 0,
            "desatualizados": 0, "erros": 0, "bloqueado": False, "motivo": None,
        }


def passa_no_filtro(preco, quartos, area=None, cidade=None) -> bool:
    """Compatibilidade: True para tudo que não foi REPROVADO.

    Mantida porque os scrapers e os testes existentes a usam. Código novo
    deve chamar avaliar_filtro() e tratar INDETERMINADO explicitamente --
    misturar INDETERMINADO com APROVADO é exatamente o bug P-01.
    """
    veredito, _ = avaliar_filtro(preco, quartos, area, cidade)
    return veredito != REPROVADO
