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

import galeria
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
        # Foto do card: sai de graça do HTML que já baixamos. Sem isto, a
        # fonte só teria imagem se a página do anúncio entregasse galeria.
        foto = galeria.foto_de_card(a, site["base_url"])

        if not utils.titulo_aceito(titulo):
            continue

        custo = utils.decompor_custo(bloco)
        preco = custo["custo_mensal_total"]
        quartos = utils.parse_quartos(bloco)
        area = utils.parse_area(bloco)

        # Descarta anúncio que a própria fonte declara desatualizado.
        # O Portal CRECI carimba "Atualizado em: dd/mm/aaaa" no card e boa
        # parte do inventário está parada há meses.
        recente, idade = utils.anuncio_recente(bloco)
        if not recente:
            resultados.stats["desatualizados"] += 1
            log.debug(f"[{site['nome']}] desatualizado ({idade} dias): {url_completa}")
            continue

        # Endereço: slug da URL primeiro (gerado pelo portal a partir do
        # cadastro), depois o texto do card, depois os regexes antigos.
        # Ambos validados contra a lista canônica de bairros -- foi regex
        # sem validação que gravou "Pernambuco" como bairro (P-05/P-18).
        logradouro, bairro, cidade_txt = utils.endereco_do_texto(bloco)
        if not bairro:
            bairro = utils.bairro_do_slug(url_completa)
        if not bairro:
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
        if not bairro:
            # último recurso: bairro canônico citado no começo do título
            bairro = utils.bairro_no_inicio(titulo)

        item = {
            # titulo definitivo é gerado abaixo, a partir dos campos
            # normalizados; o raspado vira titulo_origem (P-06)
            "titulo_origem": titulo,
            "fotos": [foto] if foto else [],
            "bairro": bairro,
            "logradouro": logradouro,
            "idade_dias": idade,
            "cidade": utils.cidade_do_bairro(bairro) or cidade_txt
                      or utils.cidade_do_slug(url_completa)
                      or site.get("cidade", "Recife"),
            "preco": preco,
            "quartos": quartos,
            "area_m2": area,
            "url": url_completa,
            "site": site["nome"],
            **custo,
        }
        item["titulo"] = utils.gerar_titulo(item)
        veredito, motivos = utils.avaliar_filtro(
            item["preco"], item["quartos"], item["area_m2"], item["cidade"]
        )
        if veredito == utils.APROVADO:
            resultados.append(item)
        elif veredito == utils.INDETERMINADO:
            # Não entra na lista principal: sem preço nem forma, é um link
            # com um título. Contabilizado para virar fila de enriquecimento.
            resultados.stats["indeterminados"] += 1
            log.debug(f"[{site['nome']}] indeterminado ({', '.join(motivos)}): {url_completa}")
        else:
            resultados.stats["reprovados"] += 1

    return novos


def scrape(site: dict) -> list[dict]:
    resultados = utils.ListaComStats()
    links_vistos = set()
    max_paginas = site.get("max_paginas", 10)
    padrao_paginacao = site.get("padrao_paginacao", "?pagina={n}")
    pagina = 1

    for pagina in range(1, max_paginas + 1):
        if pagina == 1:
            url = site["url_listagem"]
        else:
            sep = "&" if "?" in site["url_listagem"] else "?"
            url = site["url_listagem"] + sep + padrao_paginacao.format(n=pagina).lstrip("?")

        html, motivo = utils.get_html_diag(url)
        if not html:
            if pagina == 1:
                # Distinguir "falhei ao consultar" de "não há imóveis" é o
                # que impede main.py de concluir que a fonte ficou vazia.
                resultados.stats["motivo"] = motivo
                resultados.stats["bloqueado"] = motivo == utils.FALHA_BLOQUEIO
                resultados.stats["erros"] = 1
                log.error(f"[{site['nome']}] não foi possível buscar a listagem ({motivo})")
            break

        novos = _extrair_pagina(html, site, links_vistos, resultados)
        if novos == 0:
            break  # sem links novos = fim da paginação

    resultados.stats["brutos"] = len(links_vistos)
    log.info(
        f"[{site['nome']}] {len(resultados)} imóveis dentro do filtro "
        f"(de {len(links_vistos)} anúncios em {pagina} página(s); "
        f"{resultados.stats['indeterminados']} indeterminados, "
        f"{resultados.stats['desatualizados']} desatualizados)"
    )
    return resultados
