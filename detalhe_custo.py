# -*- coding: utf-8 -*-
"""
Completa o custo mensal abrindo a página do anúncio.

Existe por um caso concreto: a CTI Imobiliária mostra "R$ 1.850" no card da
listagem e só na página do imóvel revela

    Valor R$ 1.850,00 · Condomínio R$ 953,00 · IPTU R$ 194,00 · Total R$ 2.997,00

Com o card sozinho, esse apartamento entrava como R$ 1.850 -- passava no
teto de R$ 2.500 e aparecia no dashboard como se coubesse no orçamento,
quando custa R$ 2.997. É o pior tipo de erro que este projeto pode cometer:
não é um imóvel a menos, é um imóvel errado ocupando a lista.

Por que não fazer isso em toda fonte: cada anúncio vira uma requisição a
mais. Aqui o passo é opt-in por fonte (`"custo_no_detalhe": True` em
config.SITES) e ainda assim só visita o que pode mudar de veredito -- ver
`_vale_visitar`.
"""
import config
import utils
from utils import log

# Teto de visitas por rodada e por fonte. Um portal que devolva 200 cards
# incompletos não pode transformar a rodada inteira em varredura de detalhe:
# o runner tem tempo limitado e o resto das fontes espera.
MAX_VISITAS = 40


def _vale_visitar(item: dict) -> bool:
    """Só a página que pode mudar o veredito do filtro merece a requisição.

    Dois cortes:

      - custo já completo: a fonte informou condomínio, não há o que buscar;
      - preço já acima do teto: visitar só confirmaria a reprovação, e o
        custo real só sobe quando se somam encargos.

    Item sem preço nenhum vale a visita: hoje ele seria indeterminado, e a
    página costuma resolver."""
    if item.get("custo_completo"):
        return False
    preco = item.get("custo_mensal_total") or item.get("preco")
    if preco is not None and preco > config.FILTROS["preco_max"]:
        return False
    return True


def _texto_da_pagina(html: str) -> str:
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def enriquecer(itens: list[dict], buscar=None, max_visitas: int = MAX_VISITAS) -> int:
    """Completa condomínio/IPTU/total dos itens que valem a visita.

    Devolve quantos itens foram corrigidos. `buscar` existe para o teste
    injetar o HTML sem rede.
    """
    buscar = buscar or utils.fetch
    corrigidos = 0
    visitas = 0

    for item in itens:
        if visitas >= max_visitas:
            break
        if not _vale_visitar(item) or not item.get("url"):
            continue

        visitas += 1
        html = buscar(item["url"])
        if not html:
            continue

        custo = utils.decompor_custo(_texto_da_pagina(html))
        if not custo.get("custo_completo"):
            continue  # a página também não informa: nada a corrigir

        antes = item.get("custo_mensal_total") or item.get("preco")
        item.update(custo)
        item["preco"] = custo["custo_mensal_total"]
        corrigidos += 1

        depois = item["preco"]
        if antes and depois and depois > antes:
            log.debug(
                f"custo real de {item['url']}: {antes:.0f} -> {depois:.0f} "
                f"(condomínio {custo.get('condominio') or 0:.0f}, "
                f"IPTU {custo.get('iptu') or 0:.0f})"
            )

    if corrigidos:
        log.info(f"detalhe de custo: {corrigidos} de {visitas} anúncio(s) corrigidos")
    return corrigidos
