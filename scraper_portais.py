# -*- coding: utf-8 -*-
"""
Scraper para os grandes portais de classificados (OLX, Viva Real, Zap Imóveis).

IMPORTANTE: esses 3 sites têm proteção anti-bot forte (Cloudflare/DataDome) e
carregam a listagem via JavaScript (Next.js). Requests simples costumam:
  - ser bloqueados após poucas tentativas, ou
  - retornar uma página "casca" sem os dados (que só aparecem depois do JS rodar).

Por isso este scraper tenta, nesta ordem:
  1. Bright Data Web Unlocker (se configurado em config.py) - resolve bloqueio,
     mas pode não bastar se o conteúdo só existe pós-JS.
  2. Requests simples como fallback (funciona esporadicamente).

Se nenhuma das duas trouxer dados, o site é pulado e um aviso é logado --
não fazemos scraping "às cegas" gerando dados inventados.

Os dois portais (Viva Real e Zap) pertencem ao mesmo grupo (Grupo OLX) e usam
Next.js, então geralmente expõem os dados da página em um bloco
<script id="__next_data__" ...> ou <script type="application/ld+json">.
"""
import json
import re
from bs4 import BeautifulSoup

import utils
from utils import log


def _extrair_json_next_data(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def _extrair_json_ld(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    resultados = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
            resultados.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    return resultados


def _buscar_listagens_em_estrutura(obj, encontrados=None):
    """Percorre recursivamente o JSON do Next.js procurando objetos que
    pareçam anúncios de imóveis (têm price/address/bedrooms nalgum formato).
    Isso é necessariamente heurístico, pois a estrutura do __NEXT_DATA__
    muda conforme a versão do site."""
    if encontrados is None:
        encontrados = []
    if isinstance(obj, dict):
        chaves = set(k.lower() for k in obj.keys())
        if {"price", "address"}.issubset(chaves) or {"listing", "link"}.issubset(chaves):
            encontrados.append(obj)
        for v in obj.values():
            _buscar_listagens_em_estrutura(v, encontrados)
    elif isinstance(obj, list):
        for item in obj:
            _buscar_listagens_em_estrutura(item, encontrados)
    return encontrados


def scrape(site: dict) -> list[dict]:
    resultados = []
    usar_brightdata = bool(utils.config.BRIGHTDATA_API_KEY)
    html = utils.fetch(site["url_listagem"], prefer_brightdata=usar_brightdata)

    if not html:
        log.warning(
            f"[{site['nome']}] não foi possível buscar a página. "
            f"Este portal costuma exigir Bright Data configurado. Pulando."
        )
        return resultados

    next_data = _extrair_json_next_data(html)
    candidatos = []
    if next_data:
        candidatos = _buscar_listagens_em_estrutura(next_data)

    if not candidatos:
        log.warning(
            f"[{site['nome']}] página retornada não contém os dados esperados "
            f"(provavelmente carregada via JS sem execução). "
            f"Recomenda-se usar Bright Data Browser API para este site. Pulando."
        )
        return resultados

    for c in candidatos:
        try:
            preco = utils.parse_preco(str(c.get("price", "")))
            quartos = c.get("bedrooms") or c.get("rooms")
            if isinstance(quartos, list):
                quartos = quartos[0] if quartos else None
            endereco = c.get("address") or {}
            bairro = endereco.get("neighborhood") if isinstance(endereco, dict) else None
            link = c.get("link") or c.get("url") or site["url_listagem"]

            item = {
                "titulo": c.get("title", "Apartamento"),
                "bairro": bairro,
                "cidade": (endereco.get("city") if isinstance(endereco, dict) else None)
                or site.get("cidade", "Recife"),
                "preco": preco,
                "quartos": quartos,
                "area_m2": c.get("usableAreas", [None])[0] if isinstance(c.get("usableAreas"), list) else None,
                "url": link,
                "site": site["nome"],
            }
            if utils.passa_no_filtro(item["preco"], item["quartos"], item["area_m2"], item["cidade"]):
                resultados.append(item)
        except Exception as e:
            log.debug(f"[{site['nome']}] item ignorado por erro de parsing: {e}")
            continue

    log.info(f"[{site['nome']}] {len(resultados)} imóveis dentro do filtro")
    return resultados
