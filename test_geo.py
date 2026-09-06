# -*- coding: utf-8 -*-
"""Cache de geometria de bairro.

Motivado por caiooaragao/rent_finder, que tem um extrato de bairros de PE.
O extrato dele não serviu: a consulta pede `place=suburb|neighbourhood`, e os
bairros de Recife e Olinda estão no OSM como fronteira administrativa. Medido:
8 dos nossos 61 bairros tinham polígono, 74 de 476 anúncios.
"""
import json

import geo


def _resposta(elements):
    return lambda corpo: json.dumps({"elements": elements})


def test_le_way_com_geometria():
    el = [{"type": "way", "geometry": [{"lon": -34.9, "lat": -8.1},
                                       {"lon": -34.8, "lat": -8.1},
                                       {"lon": -34.8, "lat": -8.0}]}]
    anel = geo.buscar("Recife", "Pina", abrir=_resposta(el))
    assert anel == [[-34.9, -8.1], [-34.8, -8.1], [-34.8, -8.0]]


def test_le_relacao_pegando_o_maior_anel_externo():
    el = [{"type": "relation", "members": [
        {"role": "outer", "geometry": [{"lon": -34.9, "lat": -8.1},
                                       {"lon": -34.8, "lat": -8.1}]},
        {"role": "outer", "geometry": [{"lon": -34.9, "lat": -8.1},
                                       {"lon": -34.8, "lat": -8.1},
                                       {"lon": -34.8, "lat": -8.0},
                                       {"lon": -34.9, "lat": -8.0}]},
        {"role": "inner", "geometry": [{"lon": -34.85, "lat": -8.05}]},
    ]}]
    anel = geo.buscar("Recife", "Boa Viagem", abrir=_resposta(el))
    assert len(anel) == 4, "o maior anel externo vence; inner é ignorado"


def test_consulta_aceita_fronteira_administrativa():
    """É a forma que faltava no extrato do rent_finder, e é justamente como
    Recife e Olinda mapeiam bairro oficial."""
    q = geo._consulta("Recife", "Boa Viagem")
    assert '"boundary"="administrative"' in q
    assert "suburb|neighbourhood|quarter" in q
    assert '"name"="Boa Viagem"' in q


def test_resposta_vazia_nao_quebra():
    assert geo.buscar("Recife", "Inexistente", abrir=_resposta([])) is None


def test_erro_de_rede_nao_quebra():
    def explode(corpo):
        raise OSError("sem rede")
    assert geo.buscar("Recife", "Pina", abrir=explode) is None


def test_simplificar_reduz_mantendo_extremos():
    # linha quase reta com muitos pontos: sobram só as pontas
    anel = [[0, 0], [1, 0.00001], [2, 0.00002], [3, 0.00001], [4, 0]]
    r = geo.simplificar(anel)
    assert r[0] == [0, 0] and r[-1] == [4, 0]
    assert len(r) < len(anel)


def test_simplificar_preserva_curva_de_verdade():
    anel = [[0, 0], [1, 1], [2, 0]]
    assert len(geo.simplificar(anel)) == 3


def test_centroide():
    assert geo.centroide([[0, 0], [2, 0], [2, 2], [0, 2]]) == [1.0, 1.0]


def test_atualizar_so_busca_o_que_falta(monkeypatch, tmp_path):
    monkeypatch.setattr(geo, "CAMINHO", str(tmp_path / "b.json"))
    pedidos = []

    def abrir(corpo):
        pedidos.append(corpo)
        return json.dumps({"elements": [
            {"type": "way", "geometry": [{"lon": -34.9, "lat": -8.1},
                                         {"lon": -34.8, "lat": -8.0}]}]})

    geo.atualizar([("Recife", "Pina")], abrir=abrir)
    assert len(pedidos) == 1
    geo.atualizar([("Recife", "Pina")], abrir=abrir)
    assert len(pedidos) == 1, "bairro já no cache não é perguntado de novo"


def test_atualizar_grava_a_ausencia(monkeypatch, tmp_path):
    """Bairro que o OSM não tem não pode ser perguntado a cada rodada."""
    monkeypatch.setattr(geo, "CAMINHO", str(tmp_path / "b.json"))
    pedidos = []

    def vazio(corpo):
        pedidos.append(corpo)
        return json.dumps({"elements": []})

    geo.atualizar([("Recife", "Fantasma")], abrir=vazio)
    geo.atualizar([("Recife", "Fantasma")], abrir=vazio)
    assert len(pedidos) == 1
    assert geo.carregar()["Recife|Fantasma"]["anel"] is None


def test_atualizar_respeita_o_teto(monkeypatch, tmp_path):
    """A rodada tem tempo; o cache acumula."""
    monkeypatch.setattr(geo, "CAMINHO", str(tmp_path / "b.json"))
    pedidos = []
    abrir = lambda corpo: pedidos.append(corpo) or json.dumps({"elements": []})
    geo.atualizar([("Recife", f"B{i}") for i in range(10)], abrir=abrir, teto=3)
    assert len(pedidos) == 3


def test_cache_quebrado_nao_derruba(monkeypatch, tmp_path):
    p = tmp_path / "b.json"
    p.write_text("{isto não é json", encoding="utf-8")
    monkeypatch.setattr(geo, "CAMINHO", str(p))
    assert geo.carregar() == {}
