# -*- coding: utf-8 -*-
"""A foto do card tem de ser a do anúncio que o card abre.

Relato: "algumas fotos não são a do anúncio, eu clico e aparece outras fotos e
não a que tá no meu portal".

A escolha era "a maior lista entre os anúncios do imóvel", mas o botão "Ver
anúncio" abre o mais BARATO. Quando as duas coisas caíam em portais
diferentes, a pessoa clicava e via outro conjunto de fotos. Medido em
06/09/2026: 9 dos 53 imóveis multi-fonte. Em dois deles o anúncio linkado até
tinha fotos -- perdia por empate, porque o desempate seguia a ordem interna
da lista.
"""
import json

import db


def _anuncio(url, fotos):
    return {"url": url, "fotos": json.dumps(fotos) if fotos else None}


def test_usa_as_fotos_do_anuncio_linkado():
    anuncios = [
        _anuncio("https://portal-a/1", ["https://cdn-a/1.jpg", "https://cdn-a/2.jpg", "https://cdn-a/3.jpg", "https://cdn-a/4.jpg"]),
        _anuncio("https://portal-b/1", ["https://cdn-b/1.jpg"]),
    ]
    # o card abre o portal-b (o mais barato), então a foto tem de ser dele
    assert db._fotos_do_imovel(anuncios, "https://portal-b/1") == ["https://cdn-b/1.jpg"]


def test_empate_nao_pode_dar_a_vitoria_ao_outro_portal():
    """Dois dos nove casos medidos eram empate: mesma quantidade de fotos, e
    vencia quem estava antes na lista interna."""
    anuncios = [
        _anuncio("https://portal-a/1", ["https://cdn-a/1.jpg"]),
        _anuncio("https://portal-b/1", ["https://cdn-b/1.jpg"]),
    ]
    assert db._fotos_do_imovel(anuncios, "https://portal-b/1") == ["https://cdn-b/1.jpg"]


def test_sem_foto_no_linkado_cai_para_a_maior_lista():
    """Foto do MESMO apartamento noutro portal é melhor que marcador cinza --
    e o card continua abrindo o anúncio certo."""
    anuncios = [
        _anuncio("https://portal-a/1", ["https://cdn-a/1.jpg", "https://cdn-a/2.jpg"]),
        _anuncio("https://portal-b/1", None),
    ]
    assert db._fotos_do_imovel(anuncios, "https://portal-b/1") == ["https://cdn-a/1.jpg", "https://cdn-a/2.jpg"]


def test_sem_link_conhecido_mantem_o_comportamento_antigo():
    anuncios = [
        _anuncio("https://portal-a/1", ["https://cdn-a/1.jpg", "https://cdn-a/2.jpg"]),
        _anuncio("https://portal-b/1", ["https://cdn-b/1.jpg"]),
    ]
    assert db._fotos_do_imovel(anuncios) == ["https://cdn-a/1.jpg", "https://cdn-a/2.jpg"]


def test_nao_junta_listas_de_portais_diferentes():
    """Unir produziria a mesma sala duas vezes, com URLs diferentes."""
    anuncios = [
        _anuncio("https://portal-a/1", ["https://cdn-a/1.jpg", "https://cdn-a/2.jpg"]),
        _anuncio("https://portal-b/1", ["https://cdn-b/1.jpg", "https://cdn-b/2.jpg"]),
    ]
    fotos = db._fotos_do_imovel(anuncios, "https://portal-a/1")
    assert fotos == ["https://cdn-a/1.jpg", "https://cdn-a/2.jpg"]
    assert "https://cdn-b/1.jpg" not in fotos


def test_respeita_o_limite():
    anuncios = [_anuncio("https://a/1", [f"https://cdn/{i}.jpg" for i in range(30)])]
    assert len(db._fotos_do_imovel(anuncios, "https://a/1", limite=12)) == 12
