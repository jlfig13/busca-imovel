# -*- coding: utf-8 -*-
"""Testes do coletor do Chaves na Mão."""
import config
import scraper_chavesnamao as cnm

SITE = {"nome": "Chaves na Mão Recife", "cidade": "Recife",
        "base_url": "https://www.chavesnamao.com.br"}

# Recorte fiel do payload que a listagem embute (aspas escapadas, como no
# HTML real).
LISTAGEM = r'''
<script>self.__next_f.push([1,"...\"listingPreview\":{\"street\":\"Rua Dos Navegantes, 106\",
\"area\":\"87\",\"bathrooms\":1,\"bedrooms\":3,\"garages\":2,\"id\":42072444,
\"image\":\"1258072/42072444/foto.jpg\",\"location\":\"Boa Viagem, Recife/PE\",
\"price\":4576,\"title\":\"Apartamento para Locação em Boa Viagem\",
\"transaction\":\"rent\",\"url\":\"/imovel/apto-boa-viagem-RS4576/id-42072444/\"},\"singleProperty\":{}..."])</script>
'''

# Os dois formatos de página de imóvel que a fonte serve.
PAGINA_COM_TAXA = ("Aluguel R$ 2.900/mês Solicitar Visita Condomínio R$ 1.100/mês "
                   "IPTU R$ 104 Aluguel + Condomínio R$ 4.000/mês")
PAGINA_SEM_TAXA = ("Aluguel R$ 1.800/mês Solicitar Visita Condomínio R$ - "
                   "IPTU R$ -- Aluguel + Condomínio R$ 1.801/mês")


def test_le_o_card_estruturado_da_listagem():
    cards = cnm._cards(LISTAGEM)
    assert len(cards) == 1
    item = cnm._item(cards[0], SITE)
    assert item["bairro"] == "Boa Viagem"
    assert item["cidade"] == "Recife"
    assert item["quartos"] == 3 and item["banheiros"] == 1 and item["vagas"] == 2
    assert item["area_m2"] == 87
    assert item["preco"] == 4576
    assert item["url"].startswith("https://www.chavesnamao.com.br/imovel/")
    assert item["fotos"] == ["https://images.chavesnamao.com.br/1258072/42072444/foto.jpg"]
    # o card não informa taxa: o total ainda é piso
    assert item["custo_completo"] is False


def test_total_nao_pode_virar_condominio():
    """O rótulo "Aluguel + Condomínio" contém a palavra "Condomínio".

    O parser genérico lia esse total como se fosse a taxa e somava de novo:
    um apartamento de R$ 1.800 saiu como R$ 3.601."""
    custo = cnm._custo_do_texto(PAGINA_SEM_TAXA)
    assert custo["condominio"] is None
    assert custo["custo_mensal_total"] == 1801.0     # e não 3601
    assert custo["custo_completo"] is False          # "R$ -" é ausência


def test_soma_aluguel_condominio_e_iptu():
    custo = cnm._custo_do_texto(PAGINA_COM_TAXA)
    assert (custo["aluguel"], custo["condominio"], custo["iptu"]) == (2900.0, 1100.0, 104.0)
    assert custo["custo_mensal_total"] == 4104.0
    assert custo["custo_completo"] is True


def test_apartamento_caro_com_taxa_custa_muito_mais_que_o_anunciado():
    """É o motivo da segunda visita: o card anuncia 2.900 e o custo é 4.104.

    Antes este teste comparava com o teto de 2.500 do filtro de coleta. Com o
    envelope largo (05/09/2026) o teto virou 6.000 e a comparação perdeu o
    sentido -- mas o que o teste protege continua igual: quem manda no
    veredito é o custo TOTAL, não o aluguel da vitrine."""
    custo = cnm._custo_do_texto(PAGINA_COM_TAXA)
    assert custo["custo_mensal_total"] == 4104.0
    assert custo["custo_mensal_total"] > custo["aluguel"] * 1.4


def test_pagina_sem_valores_nao_inventa_custo():
    assert cnm._custo_do_texto("Apartamento bonito, sem valores")["custo_mensal_total"] is None
    assert cnm._custo_do_texto("")["custo_mensal_total"] is None
