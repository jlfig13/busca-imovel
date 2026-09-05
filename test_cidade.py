# -*- coding: utf-8 -*-
"""Cidade: reconhecer, nunca inventar.

Relato de uso: "você tá colocando lugares como Recife e quando acesso é
Garanhuns, Gravatá". Três causas, todas aqui:

1. Toda URL do OLX contém "grande-recife" (o nome da REGIÃO no caminho), então
   cidade_do_slug devolvia "Recife" para o catálogo inteiro do portal.
2. Quando nada era detectado, _parse_card completava com cidade_padrao, que é
   "Recife" -- inventar cidade é pior que não saber, porque passa no filtro.
3. avaliar_filtro não tinha recorte geográfico: cidade sem perfil caía no
   FILTRO_PADRAO (o de Recife) e podia ser APROVADA.
"""
import scraper_playwright as sp
import utils


def test_grande_recife_no_caminho_nao_e_a_cidade():
    """Era o mecanismo principal: 'grande-recife' está em toda URL do OLX."""
    caruaru = ("https://pe.olx.com.br/grande-recife/imoveis/"
               "alugo-apartamento-3-quartos-bairro-mauricio-de-nassau-caruaru")
    assert utils.cidade_do_slug(caruaru) == "Caruaru"
    sem_cidade = "https://pe.olx.com.br/grande-recife/imoveis/apto-1532718092"
    assert utils.cidade_do_slug(sem_cidade) is None


def test_cidade_no_slug_de_outros_portais_continua_valendo():
    """A correção não pode cegar o Zap, que traz a cidade no slug de verdade."""
    zap = "https://www.zapimoveis.com.br/imovel/aluguel-apto-tamarineira-recife-pe-82m2"
    assert utils.cidade_do_slug(zap) == "Recife"


def test_reconhece_cidade_de_fora_no_texto_do_card():
    assert utils.cidade_de_fora("Garanhuns, Heliópolis") == "Garanhuns"
    assert utils.cidade_de_fora("Gravatá, Centro") == "Gravatá"
    assert utils.cidade_de_fora("Recife, Boa Viagem") is None


def _card(texto, href="https://pe.olx.com.br/grande-recife/imoveis/apto-123456"):
    return {"text": texto, "href": href}


def test_fonte_multi_cidade_nao_inventa_recife():
    item = sp._parse_card(
        _card("Apartamento para alugar\nR$ 2.000\n90m² / 3 / 2 / 1"),
        "OLX Imóveis", cidade_padrao="Recife", multi_cidade=True)
    assert item is not None
    assert item["cidade"] is None, "sem detectar, a cidade tem de ficar vazia"


def test_fonte_de_cidade_unica_ainda_usa_o_padrao():
    """Zap Recife é uma busca de cidade só: ali o padrão é fato, não palpite."""
    item = sp._parse_card(
        _card("Apartamento para alugar\nR$ 2.000\n90m² / 3 / 2 / 1",
              href="https://www.zapimoveis.com.br/imovel/aluguel-apto-123"),
        "Zap Imóveis", cidade_padrao="Recife", multi_cidade=False)
    assert item["cidade"] == "Recife"


def test_anuncio_de_fora_e_rotulado_com_a_cidade_certa():
    item = sp._parse_card(
        _card("Garanhuns, Heliópolis\nApartamento\nR$ 2.000\n90m² / 3 / 2 / 1"),
        "OLX Imóveis", cidade_padrao="Recife", multi_cidade=True)
    assert item["cidade"] == "Garanhuns"
    veredito, motivos = utils.avaliar_filtro(
        item["preco"], item["quartos"], item["area_m2"], item["cidade"])
    assert veredito == utils.REPROVADO
    assert "Garanhuns" in motivos[0]
