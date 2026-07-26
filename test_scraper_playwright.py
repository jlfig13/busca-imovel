# -*- coding: utf-8 -*-
"""Testes de _parse_card usando texto real capturado rodando o Playwright
contra OLX e REMAX ao vivo (não são exemplos inventados). Fixam os bugs de
bairro corrigidos nesta sessão: 'em' sem \\b roubava bairro de qualquer
palavra terminada em 'em' (ex: Boa Viagem), e a regra 'Cidade, Bairro' do
OLX colidia com o formato 'Bairro, Cidade, Estado' do REMAX, capturando o
estado (Pernambuco) como se fosse bairro."""
import scraper_playwright as sp


def test_olx_card_com_titulo_mencionando_quartos():
    texto = (
        "Apartamento Exclusivo para Aluguel em Recife/PE (Iputinga) 2 Quartos "
        "c/ Suíte, 50m² e 1 V\n50m²\n2\n2\n1\nR$ 3.500\n\nRecife, Iputinga\n\n"
        "Hoje, 08:52\n\nChat"
    )
    item = sp._parse_card({"text": texto, "href": "https://x/1"}, "OLX Imóveis")
    assert item["bairro"] == "Iputinga"
    assert item["cidade"] == "Recife"
    assert item["preco"] == 3500.0
    assert item["quartos"] == 2
    assert item["area_m2"] == 50.0


def test_olx_card_detecta_cidade_diferente_do_padrao():
    # OLX busca a região metropolitana inteira (não só Recife) -- um card
    # de Jaboatão dos Guararapes tem que ficar marcado com essa cidade,
    # não cair no padrão "Recife" do site, senão o filtro de Olinda/outras
    # cidades usaria o perfil errado (quartos_min/area_min de Recife).
    texto = (
        "Flat Mobiliado Beira Mar luxo Lazer 2600 c Txs\n36m²\n1\n1\n1\n"
        "Direto com o proprietário\nR$ 2.600\n\nJaboatão dos Guararapes, "
        "Piedade\n\nHoje, 08:49\n\nChat"
    )
    item = sp._parse_card({"text": texto, "href": "https://x/1b"}, "OLX Imóveis", cidade_padrao="Recife")
    assert item["cidade"] == "Jaboatão dos Guararapes"
    assert item["bairro"] == "Piedade"


def test_parse_card_usa_cidade_padrao_quando_nao_detecta():
    texto = "Apartamento para alugar no Iputinga\n78m²\n3 quartos\nR$ 1.700"
    item = sp._parse_card({"text": texto, "href": "https://x/1c"}, "CTI Imobiliária", cidade_padrao="Recife")
    assert item["cidade"] == "Recife"


def test_olx_card_bairro_nao_rouba_de_palavra_terminada_em_em():
    # "Boa Viagem" contém "em" no final -- sem \b na regex "em\n" antiga,
    # isso casava e devolvia "Hoje" (linha da data) como bairro.
    texto = (
        "Imóvel para aluguel com 25 metros quadrados com 1 quarto em Boa "
        "Viagem - Recife - PE\n25m²\n1\n1\n1\nR$ 3.000\n\nRecife, Boa Viagem\n\n"
        "Hoje, 08:48\n\nChat"
    )
    item = sp._parse_card({"text": texto, "href": "https://x/2"}, "OLX Imóveis")
    assert item["bairro"] == "Boa Viagem"


def test_olx_card_bairro_jaboatao():
    texto = (
        "Flat Mobiliado Beira Mar luxo Lazer 2600 c Txs\n36m²\n1\n1\n1\n"
        "Direto com o proprietário\nR$ 2.600\n\nJaboatão dos Guararapes, "
        "Piedade\n\nHoje, 08:49\n\nChat"
    )
    item = sp._parse_card({"text": texto, "href": "https://x/3"}, "OLX Imóveis")
    assert item["bairro"] == "Piedade"
    assert item["area_m2"] == 36.0


def test_remax_card_bairro_nao_pega_estado():
    # "...Boa Viagem, Recife, Pernambuco, CEP" -- bairro é "Boa Viagem",
    # não "Pernambuco" (estado, capturado por engano quando a regra OLX
    # "Cidade, Bairro" rodava antes da regra REMAX "Bairro, Cidade").
    texto = (
        "1/36\n\nR$ 2.500 Mensal\n\n2\n\n2\n\n9\n\n60\n\n1\n\nApartamento\n\n"
        "Av Fernando Simões Barbosa, 1222 - Ao lado do restaurante "
        "PARRAXAXÁ - Boa Viagem, Recife, Pernambuco, 52021060"
    )
    item = sp._parse_card({"text": texto, "href": "https://x/4"}, "REMAX Recife")
    assert item["bairro"] == "Boa Viagem"
    assert item["preco"] == 2500.0
    assert item["quartos"] == 2
    assert item["area_m2"] == 60.0


def test_remax_card_area_com_decimal_br():
    texto = (
        "1/12\n\nR$ 3.900 Mensal\n\n3\n\n3\n\n2\n\n83,15\n\n1\n\nApartamento\n\n"
        "Aflitos, Recife, Pernambuco, 52050-020"
    )
    item = sp._parse_card({"text": texto, "href": "https://x/5"}, "REMAX Recife")
    assert item["bairro"] == "Aflitos"
    assert item["quartos"] == 3
    assert item["area_m2"] == 83.15


def test_cti_card_bairro_seguido_de_condominio():
    texto = (
        "Apartamento para alugar no Iputinga no condomínio Conj. Res. Rio "
        "Guaporé\n70m²\n3 quartos\nR$ 1.600"
    )
    item = sp._parse_card({"text": texto, "href": "https://x/6"}, "CTI Imobiliária")
    assert item["bairro"] == "Iputinga"


def test_cti_card_bairro_sem_condominio_no_titulo():
    # regressão: capturar bairro quando "no condomínio" não vem em seguida
    # -- o boundary "\s*$" antigo só casava se o título fosse o FIM
    # absoluto do texto do card; como sempre há mais linhas depois (preço,
    # área), nunca casava e devolvia bairro None.
    texto = "Apartamento para alugar no Iputinga\n78m²\n3 quartos\nR$ 1.700"
    item = sp._parse_card({"text": texto, "href": "https://x/7"}, "CTI Imobiliária")
    assert item["bairro"] == "Iputinga"
