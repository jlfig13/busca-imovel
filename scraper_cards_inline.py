# -*- coding: utf-8 -*-
"""
Scraper genérico para sites onde a LISTAGEM já mostra preço, quartos e
área perto do link de cada imóvel (não precisa abrir a página de detalhe).
Confirmado funcionando em 3 plataformas diferentes nesta sessão:
  - RocketImob   (Âncora Imobiliária)
  - Kenlo        (Abasol Imóveis)
  - IMOPRO       (Camila Melo Imóveis)

Estratégia: acha todos os links que apontam para uma página de imóvel
(padrão configurável por site) e sobe pelos elementos pai até achar um
bloco de texto que contenha "R$" -- esse bloco é o "card" do anúncio.
Depois aplica os mesmos regexes de preço/quartos/área do utils.py.

Isso evita depender de nomes de classes CSS específicos, que mudam de
site para site e quebram fácil.
"""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

import utils
from utils import log


def _achar_bloco_do_card(link_tag, max_subida=6):
    """Sobe pela árvore HTML a partir do link até achar um elemento cujo
    texto contenha 'R$' (indício de que já inclui o preço) -- esse é o
    card completo do anúncio. Para de subir depois de max_subida níveis
    ou 1500 caracteres de texto (para não pegar a página inteira)."""
    elemento = link_tag
    for _ in range(max_subida):
        if elemento.parent is None:
            break
        elemento = elemento.parent
        texto = elemento.get_text(separator=" ", strip=True)
        if "R$" in texto and len(texto) < 1500:
            return texto
    return link_tag.get_text(separator=" ", strip=True)


def _extrair_pagina(html: str, site: dict, links_vistos: set, resultados: list) -> int:
    """Processa uma página HTML e retorna quantos links novos foram encontrados."""
    soup = BeautifulSoup(html, "html.parser")
    padrao_link = site.get("padrao_link_imovel", "/imovel/")
    novos = 0

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if padrao_link not in href:
            continue
        url_completa = urljoin(site["base_url"], href)
        if url_completa in links_vistos:
            continue
        links_vistos.add(url_completa)
        novos += 1

        bloco = _achar_bloco_do_card(a)
        titulo = a.get_text(strip=True) or bloco[:80]

        if not utils.titulo_aceito(titulo):
            continue

        preco = utils.parse_preco_total(bloco)
        quartos = utils.parse_quartos(bloco)
        area = utils.parse_area(bloco)

        bairro = None
        m = re.search(r"[Bb]airro[:\s]+([A-Za-zÀ-ú][A-Za-zÀ-ú ]{1,29})", bloco)
        if m:
            bairro = m.group(1).strip()
        if not bairro:
            m = re.search(r"[Qq]uartos?\s+([A-Za-zÀ-ú][A-Za-zÀ-ú ]{1,28}?)\s+\d+\s*m[²2]", titulo)
            if m:
                bairro = m.group(1).strip()
        if not bairro:
            m = re.search(r"m[eê]s([A-ZÀ-Ú][A-Za-zÀ-ú ]+?)Apartamento", titulo)
            if m:
                bairro = m.group(1).strip()

        item = {
            "titulo": titulo,
            "bairro": bairro,
            "cidade": site.get("cidade", "Recife"),
            "preco": preco,
            "quartos": quartos,
            "area_m2": area,
            "url": url_completa,
            "site": site["nome"],
        }
        if utils.passa_no_filtro(item["preco"], item["quartos"], item["area_m2"], item["cidade"]):
            resultados.append(item)

    return novos


def scrape(site: dict) -> list[dict]:
    resultados = []
    links_vistos = set()
    max_paginas = site.get("max_paginas", 10)
    padrao_paginacao = site.get("padrao_paginacao", "?pagina={n}")

    for pagina in range(1, max_paginas + 1):
        if pagina == 1:
            url = site["url_listagem"]
        else:
            sep = "&" if "?" in site["url_listagem"] else "?"
            url = site["url_listagem"] + sep + padrao_paginacao.format(n=pagina).lstrip("?")

        html = utils.fetch(url)
        if not html:
            if pagina == 1:
                log.error(f"[{site['nome']}] não foi possível buscar a listagem")
            break

        novos = _extrair_pagina(html, site, links_vistos, resultados)
        if novos == 0:
            break  # sem links novos = fim da paginação

    log.info(f"[{site['nome']}] {len(resultados)} imóveis dentro do filtro (de {len(links_vistos)} anúncios em {pagina} página(s))")
    return resultados
