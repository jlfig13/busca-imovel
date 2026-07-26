# -*- coding: utf-8 -*-
import logging
import re
import time
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


def get_html(url: str, timeout: int = 20, retries: int = 2) -> str | None:
    """Busca uma página via requests simples (funciona para sites sem
    proteção anti-bot). Retorna None em caso de falha."""
    for tentativa in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            log.warning(f"HTTP {resp.status_code} em {url}")
        except requests.RequestException as e:
            log.warning(f"Erro ao buscar {url}: {e}")
        time.sleep(1.5)
    return None


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


_TIPO_NAO_RESIDENCIAL = re.compile(
    r"\bsala\s+comercial\b|\bgalp[aã]o\b|\bterreno\b|\bconsult[oó]rio\b"
    r"|\bestablecimento\s+comercial\b|\bponto\s+comercial\b",
    re.IGNORECASE,
)


def titulo_aceito(titulo: str) -> bool:
    """False para imóveis claramente não-residenciais."""
    return not _TIPO_NAO_RESIDENCIAL.search(titulo or "")


def passa_no_filtro(preco, quartos, area=None, cidade=None) -> bool:
    """Aplica os filtros de config.FILTROS (preço, fixo) e
    config.FILTROS_POR_CIDADE (quartos_min/area_min, variam por cidade --
    ver comentário em config.py). Campos ausentes (None) não reprovam o
    imóvel automaticamente -- é melhor mostrar de mais e o usuário
    descartar manualmente do que perder uma oportunidade por falha de
    parsing. Isso vale também pra área: sites como OLX/REMAX não mostram
    m² no card da listagem, então área ausente passa -- só reprova quando
    o valor foi capturado e é menor que o mínimo."""
    f = config.FILTROS
    if preco is not None and not (f["preco_min"] <= preco <= f["preco_max"]):
        return False
    perfil = config.FILTROS_POR_CIDADE.get(cidade, config.FILTRO_PADRAO)
    if quartos is not None and quartos < perfil["quartos_min"]:
        return False
    if area is not None and area < perfil["area_min"]:
        return False
    return True
