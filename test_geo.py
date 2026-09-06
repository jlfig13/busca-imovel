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


# --- falha de rede não vira veredito -----------------------------------
# O cache grava AUSÊNCIA para não reperguntar todo dia. Sem separar "o OSM não
# tem" de "não consegui perguntar", um Overpass fora do ar por cinco minutos
# gravaria "este bairro não existe" para sempre e apagaria o mapa em
# definitivo, sem erro visível. É o mesmo princípio que o projeto já aplica às
# fontes: ausência só conta se quem responde estava saudável.

def _explode(_corpo):
    raise OSError("Overpass fora do ar")


def test_falha_de_rede_nao_grava_ausencia(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "CAMINHO", str(tmp_path / "b.json"))
    cache = geo.atualizar([("Recife", "Pina")], abrir=_explode)
    assert cache == {}, "falha de rede não pode virar 'bairro não existe'"


def test_falha_de_rede_deixa_o_bairro_para_a_proxima(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "CAMINHO", str(tmp_path / "b.json"))
    geo.atualizar([("Recife", "Pina")], abrir=_explode)
    cache = geo.atualizar([("Recife", "Pina")], abrir=lambda c: '{"elements": []}')
    assert geo.chave("Recife", "Pina") in cache


def test_ausencia_confirmada_e_gravada(tmp_path, monkeypatch):
    """O outro lado: bairro que o OSM realmente não tem NÃO pode ser
    perguntado de novo a cada rodada."""
    monkeypatch.setattr(geo, "CAMINHO", str(tmp_path / "b.json"))
    cache = geo.atualizar([("Recife", "Pina")], abrir=lambda c: '{"elements": []}')
    assert cache[geo.chave("Recife", "Pina")]["anel"] is None


def test_para_apos_tres_recusas_seguidas(tmp_path, monkeypatch):
    """Insistir depois de um 429 é a carga alheia que o cache existe para
    evitar -- e, medido na rodada 64, também é inútil: depois do primeiro
    429 vieram mais sete."""
    monkeypatch.setattr(geo, "CAMINHO", str(tmp_path / "b.json"))
    tentativas = []

    def recusa(_corpo):
        tentativas.append(1)
        raise OSError("HTTP Error 429: Too Many Requests")

    pares = [("Recife", f"B{i}") for i in range(10)]
    geo.atualizar(pares, abrir=recusa)
    assert len(tentativas) == 3, f"parou em {len(tentativas)}, devia parar em 3"


def test_uma_resposta_boa_zera_a_contagem_de_recusas(tmp_path, monkeypatch):
    """Falha isolada não pode encerrar a rodada: só a sequência é sinal."""
    monkeypatch.setattr(geo, "CAMINHO", str(tmp_path / "b.json"))
    n = {"i": 0}

    def alterna(_corpo):
        n["i"] += 1
        if n["i"] % 2:
            raise OSError("504")
        return '{"elements": []}'

    pares = [("Recife", f"B{i}") for i in range(8)]
    geo.atualizar(pares, abrir=alterna)
    assert n["i"] == 8, "alternando falha e sucesso, nunca há 3 seguidas"
