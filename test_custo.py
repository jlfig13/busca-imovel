# -*- coding: utf-8 -*-
"""Custo total: aluguel + condomínio + taxas, sem perder a soma entre rodadas.

Relato: "a fonte da chave da mão não tá somando aluguel + condomínio e taxas".

A causa não estava no parser, que soma certo. Estava na gravação: o UPSERT
preserva as PARTES com COALESCE (condomínio e IPTU de uma visita anterior à
página do anúncio) mas sobrescrevia o TOTAL com o valor da rodada atual --
que, sem revisitar o detalhe, é só o aluguel do card.

Medido no banco de produção em 05/09/2026: um anúncio com partes
1500+170+171 gravado como 1500, e um evento "1841 -> 1500" no histórico: uma
queda de R$ 341 que nunca aconteceu, na mesma série que alimenta o selo
"Baixou" do dashboard.
"""
import db


def test_taxa_conhecida_de_rodada_anterior_volta_para_a_soma():
    """O caso exato do relato: card só com aluguel, taxas já conhecidas."""
    item = {"aluguel": 1500.0, "condominio": None, "iptu": None,
            "custo_mensal_total": 1500.0, "preco": 1500.0, "custo_completo": False}
    db._consolidar_custo(item, (1500.0, 170.0, 171.0))
    assert item["custo_mensal_total"] == 1841.0
    assert item["preco"] == 1841.0
    assert item["custo_completo"] is True
    assert (item["condominio"], item["iptu"]) == (170.0, 171.0)


def test_taxa_nova_vence_a_guardada():
    """Condomínio reajustou: o valor desta rodada manda."""
    item = {"aluguel": 1500.0, "condominio": 200.0, "iptu": 171.0,
            "custo_mensal_total": 1871.0, "preco": 1871.0, "custo_completo": True}
    db._consolidar_custo(item, (1500.0, 170.0, 171.0))
    assert item["custo_mensal_total"] == 1871.0
    assert item["condominio"] == 200.0


def test_sem_taxa_conhecida_o_total_do_card_fica_como_esta():
    """Sem condomínio o total é PISO, não custo -- e o card avisa isso com o
    selo "Custo parcial". Inventar uma taxa seria pior que admitir a falta."""
    item = {"aluguel": 1500.0, "condominio": None, "iptu": None,
            "custo_mensal_total": 1500.0, "preco": 1500.0, "custo_completo": False}
    db._consolidar_custo(item, (1500.0, None, None))
    assert item["custo_mensal_total"] == 1500.0
    assert item["custo_completo"] is False


def test_anuncio_novo_nao_tem_o_que_consolidar():
    item = {"aluguel": 1500.0, "condominio": None, "iptu": None,
            "custo_mensal_total": 1500.0, "preco": 1500.0, "custo_completo": False}
    db._consolidar_custo(item, None)
    assert item["custo_mensal_total"] == 1500.0


def test_total_declarado_maior_que_a_soma_vence():
    """Anúncio que informa um total com taxa extra não decomposta."""
    item = {"aluguel": 1500.0, "condominio": 170.0, "iptu": None,
            "custo_mensal_total": 1900.0, "preco": 1900.0, "custo_completo": True}
    db._consolidar_custo(item, (1500.0, 170.0, None))
    assert item["custo_mensal_total"] == 1900.0


def test_iptu_ausente_nao_vira_zero_indevido():
    item = {"aluguel": 1200.0, "condominio": 120.0, "iptu": None,
            "custo_mensal_total": 1320.0, "preco": 1320.0, "custo_completo": True}
    db._consolidar_custo(item, (1200.0, 120.0, None))
    assert item["custo_mensal_total"] == 1320.0
    assert item["iptu"] is None


# ---------------------------------------------------------------------------
# Ponta a ponta: o cenário que produziu o evento falso
# ---------------------------------------------------------------------------
import os
import tempfile

import pytest

import config


@pytest.fixture
def banco(monkeypatch):
    fd, caminho = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "ARQUIVO_DB", caminho)
    import db as _db
    yield _db
    try:
        os.unlink(caminho)
    except OSError:
        pass


def _anuncio(**kw):
    base = {"url": "u1", "site": "Chaves na Mão Olinda", "titulo": "t",
            "bairro": "Bairro Novo", "cidade": "Olinda", "quartos": 3,
            "area_m2": 80, "aluguel": 1500.0, "condominio": None, "iptu": None,
            "preco": 1500.0, "custo_mensal_total": 1500.0, "custo_completo": False}
    base.update(kw)
    return base


def test_rodada_sem_detalhe_nao_apaga_a_soma_nem_inventa_queda(banco):
    """Reproduz o defeito relatado, de ponta a ponta.

    Rodada 1 visita a página e descobre condomínio 170 e IPTU 171 -> 1841.
    Rodada 2 não revisita (o detalhe tem teto por rodada) e o card traz 1500.
    Antes: o total virava 1500 e nascia um evento de queda de R$ 341.
    """
    fontes = {"Chaves na Mão Olinda"}
    banco.salvar_execucao([_anuncio(condominio=170.0, iptu=171.0,
                                    preco=1841.0, custo_mensal_total=1841.0,
                                    custo_completo=True)], fontes_confiaveis=fontes)
    banco.salvar_execucao([_anuncio()], fontes_confiaveis=fontes)

    conn = banco.conectar()
    aluguel, cond, iptu, total, completo = conn.execute(
        """SELECT aluguel, condominio, iptu, custo_mensal_total, custo_completo
           FROM imoveis WHERE url='u1'""").fetchone()
    quedas = conn.execute(
        "SELECT COUNT(*) FROM evento WHERE url='u1' AND tipo='PRECO_ALTERADO'"
    ).fetchone()[0]
    conn.close()

    assert (aluguel, cond, iptu) == (1500.0, 170.0, 171.0)
    assert total == 1841.0, "o total tem de continuar sendo a soma das partes"
    assert completo == 1
    assert quedas == 0, "não houve mudança de preço: não pode haver evento"


def test_queda_real_continua_sendo_registrada(banco):
    """A correção não pode calar a série: aluguel que cai de verdade conta."""
    fontes = {"Chaves na Mão Olinda"}
    banco.salvar_execucao([_anuncio(condominio=170.0, iptu=171.0,
                                    preco=1841.0, custo_mensal_total=1841.0,
                                    custo_completo=True)], fontes_confiaveis=fontes)
    banco.salvar_execucao([_anuncio(aluguel=1300.0, condominio=170.0, iptu=171.0,
                                    preco=1641.0, custo_mensal_total=1641.0,
                                    custo_completo=True)], fontes_confiaveis=fontes)
    conn = banco.conectar()
    ev = conn.execute(
        """SELECT valor_antes, valor_depois FROM evento
           WHERE url='u1' AND tipo='PRECO_ALTERADO'""").fetchall()
    conn.close()
    # valor_antes/valor_depois são TEXT no schema (o evento é genérico e
    # também guarda mudança de bairro e de anunciante)
    assert [(float(a), float(d)) for a, d in ev] == [(1841.0, 1641.0)]


# ---------------------------------------------------------------------------
# Fonte de card incompleto (cards_inline)
# ---------------------------------------------------------------------------

def test_cards_inline_visita_o_detalhe_quando_configurado(monkeypatch):
    """Relatado na Cristina Mirele: R$ 1.500 na lista, R$ 3.000 ao abrir.

    `cards_inline` nunca visitava a página do anúncio -- o preço era o que o
    card dissesse. O enriquecimento roda ANTES do filtro, como no
    scraper_playwright: é justamente o veredito que muda.
    """
    import scraper_cards_inline as sci
    chamadas = []
    monkeypatch.setattr(sci.detalhe_custo, "enriquecer",
                        lambda itens: chamadas.append(len(itens)) or 0)

    html = '''<div><a href="/imovel/1/apartamento-locacao-olinda-pe-x">
      Apartamento para locação</a> R$ 1.500 3 quartos 80 m²</div>'''
    site = {"nome": "Cristina Mirele Imóveis", "base_url": "https://x.com",
            "padrao_link_imovel": "-locacao-", "cidade": "Olinda",
            "custo_no_detalhe": True}
    sci._extrair_pagina(html, site, set(), sci.utils.ListaComStats())
    assert chamadas, "a fonte configurada tem de passar pelo detalhe"


def test_cards_inline_sem_a_marca_nao_visita_nada(monkeypatch):
    """Visita é requisição: fonte cujo card já traz o custo não paga isso."""
    import scraper_cards_inline as sci
    chamadas = []
    monkeypatch.setattr(sci.detalhe_custo, "enriquecer",
                        lambda itens: chamadas.append(len(itens)) or 0)
    html = '''<div><a href="/imovel/1/apartamento-locacao-olinda-pe-x">
      Apartamento para locação</a> R$ 1.500 3 quartos 80 m²</div>'''
    site = {"nome": "Outra", "base_url": "https://x.com",
            "padrao_link_imovel": "-locacao-", "cidade": "Olinda"}
    sci._extrair_pagina(html, site, set(), sci.utils.ListaComStats())
    assert not chamadas
