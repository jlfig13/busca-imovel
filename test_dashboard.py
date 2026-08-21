# -*- coding: utf-8 -*-
"""Testes do dashboard: triagem (favoritos/lixeira) e destaque do que mudou.

Banco e arquivo de saída temporários: gerar_dashboard escreve em
config.ARQUIVO_DASHBOARD e lê a série de preços do banco, e nenhum dos dois
pode ser o versionado.
"""
import os
import tempfile

import pytest

import config


@pytest.fixture
def ambiente(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setattr(config, "ARQUIVO_DB", os.path.join(tmp, "t.db"))
    monkeypatch.setattr(config, "ARQUIVO_DASHBOARD", os.path.join(tmp, "d.html"))
    monkeypatch.setattr(config, "PASTA_SAIDA", tmp)
    import db as _db
    _db.conectar().close()  # cria o schema
    import dashboard as _dash
    return _dash


def _imovel(**extra):
    base = {
        "cidade": "Recife", "bairro": "Pina", "preco": 2000, "quartos": 2,
        "area_m2": 70, "titulo": "Apartamento no Pina", "noRecorte": True,
        "qtd_fontes": 1, "dias_anunciado": 5,
        "anuncios": [{"site": "Fonte A", "url": "https://a.com/1", "preco": 2000,
                      "custo_completo": True}],
    }
    base.update(extra)
    return base


def _html(dash, itens):
    dash.gerar_dashboard(itens, [], [])
    with open(config.ARQUIVO_DASHBOARD, encoding="utf-8") as f:
        return f.read()


def test_queda_traz_valor_e_percentual(ambiente, monkeypatch):
    """R$ 100 em 1.500 é outra conversa que R$ 100 em 2.500: o selo mostra os dois."""
    monkeypatch.setattr(ambiente.db, "obter_serie_precos",
                        lambda urls: {"https://a.com/1": [("2026-08-01", 2500.0),
                                                          ("2026-08-20", 2000.0)]})
    html = _html(ambiente, [_imovel()])
    assert '"queda": 500.0' in html
    assert '"quedaPct": 20' in html


def test_sem_historico_nao_inventa_queda(ambiente, monkeypatch):
    monkeypatch.setattr(ambiente.db, "obter_serie_precos", lambda urls: {})
    html = _html(ambiente, [_imovel()])
    assert '"queda": null' in html
    assert '"quedaPct": null' in html


def test_contagem_dos_chips_nao_vem_fixa_do_python(ambiente):
    """Era interpolada sobre a lista inteira e nunca mudava: com "Minhas
    preferências" ligado, o chip dizia "Novos 4" numa tela com 1."""
    html = _html(ambiente, [_imovel(novo=True), _imovel(noRecorte=False, novo=True)])
    assert 'id="cn-novos"></span>' in html
    assert 'id="cn-quedas"></span>' in html
    assert 'id="cn-multi"></span>' in html


def test_escopos_de_triagem_existem(ambiente):
    html = _html(ambiente, [_imovel()])
    for alvo in ('id="e-favoritos"', 'id="e-lixeira"',
                 'id="n-favoritos"', 'id="n-lixeira"'):
        assert alvo in html


def test_triagem_e_chaveada_por_url_de_anuncio(ambiente):
    """O id do imóvel é reconstruído a cada rodada (db.consolidar_imoveis apaga
    e recria a tabela), então a lista precisa guardar a URL do anúncio."""
    html = _html(ambiente, [_imovel()])
    assert "chavesDe = d => (d.anuncios || []).map(a => a.url)" in html
    assert "lerLista('descartados')" in html
    assert "lerLista('favoritos')" in html


def test_acesso_a_localStorage_e_protegido(ambiente):
    """Em file:// o acesso pode levantar exceção -- e a triagem não pode
    derrubar o render, como já aconteceu com replaceState."""
    html = _html(ambiente, [_imovel()])
    trecho = html[html.index("function lerLista"):html.index("let DESCARTADOS")]
    assert "catch" in trecho
    trecho2 = html[html.index("function gravarLista"):html.index("let DESCARTADOS")]
    assert "catch" in trecho2


def test_pulso_liga_o_filtro(ambiente):
    """O contador dizia "3 baixaram" e não havia como chegar nos três."""
    html = _html(ambiente, [_imovel()])
    assert "acao('Novos hoje', novos, 'novos')" in html
    assert "acao('Baixaram', quedas, 'quedas')" in html
    assert "function ligarChip(nome)" in html
