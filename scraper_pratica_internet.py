# -*- coding: utf-8 -*-
"""
Scraper para sites construídos pela agência "Prática Internet" (padrão
identificado no rodapé como 'Site desenvolvido pela Pratica Internet').
Confirmado funcionando em: Luiza Parizi Imóveis.

Estrutura:
  - Página de listagem: cards com link para /imovel/<slug>
  - Página de detalhe: contém "Preços:" com R$, lista de características
    com "N Quarto(s)", e "Área Útil: N.NN m²"
"""
import re
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup

import utils
from utils import log


def extrair_links_imoveis(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(base_url, href)
        if "/imovel/" in href and full_url.startswith(base_url):
            links.add(full_url)
        elif "api.whatsapp.com" in href or "wa.me" in href:
            # site embute a URL do apt no parâmetro text= do WhatsApp
            try:
                params = parse_qs(urlparse(href).query)
                text = params.get("text", [""])[0]
                m = re.search(r"(https?://\S+/imovel/\S+)", text)
                if m:
                    links.add(m.group(1))
            except Exception:
                pass
    return list(links)


def extrair_detalhes(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    texto_completo = soup.get_text(separator="\n")

    # Estratégia 1: template "Prática Internet" -- bloco "Preços:\nR$: X,XX"
    preco = None
    match_preco = re.search(r"Pre[çc]os?:\s*\n*\s*\**R\$:?\s*([\d.,]+)", texto_completo, re.IGNORECASE)
    if match_preco:
        preco = utils.parse_preco(match_preco.group(0))
    else:
        # Estratégia 2: template "Tecimob" e outros -- palavra "aluguel" perto do R$
        preco = utils.parse_preco_aluguel(texto_completo)

    quartos = utils.parse_quartos(texto_completo)
    area = utils.parse_area(texto_completo)

    # Bairro
    bairro = None
    match_bairro = re.search(r"Bairro:\**\s*([^\n]+)", texto_completo)
    if match_bairro:
        bairro = match_bairro.group(1).strip()

    # Título / código
    titulo_tag = soup.find(["h1", "h2"])
    titulo = titulo_tag.get_text(strip=True) if titulo_tag else url

    return {
        "titulo": titulo,
        "bairro": bairro,
        "preco": preco,
        "quartos": quartos,
        "area_m2": area,
        "url": url,
    }


def scrape(site: dict) -> list[dict]:
    """site = uma entrada de config.SITES com tipo 'html_estatico' e
    template 'pratica_internet'."""
    resultados = []
    html_listagem = utils.fetch(site["url_listagem"])
    if not html_listagem:
        log.error(f"[{site['nome']}] não foi possível buscar a listagem")
        return resultados

    links = extrair_links_imoveis(html_listagem, site["base_url"])
    log.info(f"[{site['nome']}] {len(links)} imóveis encontrados na listagem")

    for link in links:
        html_detalhe = utils.fetch(link)
        if not html_detalhe:
            continue
        item = extrair_detalhes(html_detalhe, link)
        if not item:
            continue
        item["site"] = site["nome"]
        item["cidade"] = site.get("cidade", "Recife")
        if utils.titulo_aceito(item.get("titulo", "")) and utils.passa_no_filtro(
            item["preco"], item["quartos"], item["area_m2"], item["cidade"]
        ):
            resultados.append(item)

    log.info(f"[{site['nome']}] {len(resultados)} imóveis dentro do filtro")
    return resultados
