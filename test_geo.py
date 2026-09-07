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


def test_le_relacao_montando_a_divisa_e_ignorando_inner():
    """A divisa vem fatiada em ways `outer`; o bairro é a costura deles.

    Este teste já existiu afirmando que "o maior anel externo vence", medindo
    o maior por número de PONTOS. Era a regra errada -- e foi ela que encheu
    o cache de lascas de fronteira de 3 pontos."""
    el = [{"type": "relation", "members": [
        # o quadrado do bairro, partido em dois trechos
        {"role": "outer", "geometry": [{"lon": -34.9, "lat": -8.1},
                                       {"lon": -34.8, "lat": -8.1},
                                       {"lon": -34.8, "lat": -8.0}]},
        {"role": "outer", "geometry": [{"lon": -34.8, "lat": -8.0},
                                       {"lon": -34.9, "lat": -8.0},
                                       {"lon": -34.9, "lat": -8.1}]},
        {"role": "inner", "geometry": [{"lon": -34.85, "lat": -8.05}]},
    ]}]
    anel = geo.buscar("Recife", "Boa Viagem", abrir=_resposta(el))
    assert geo._mesma_ponta(anel[0], anel[-1]), "a divisa costurada fecha"
    assert abs(geo._area_aprox(anel) - 0.01) < 1e-9, "sai o quadrado inteiro"


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


# --- costura da fronteira ----------------------------------------------
# O mapa saiu como pontinhos na tela porque um bairro em
# boundary=administrative NÃO é um way só: a relação lista vários ways
# `outer`, cada um um TRECHO da divisa, em ordem e orientação quaisquer.
# Pegar o trecho mais longo dava uma lasca de fronteira. Medido no cache da
# rodada 66: Casa Caiada com 3 pontos e 0,24 x 0,85 km, Pina com 3, Madalena
# com 3 -- bairro típico de 0,5 km num mapa de 42 km, ou seja, 3 pixels.

def _quadrado_em_trechos():
    """O mesmo quadrado, partido em 4 trechos fora de ordem e com duas
    orientações invertidas -- que é como o OSM entrega."""
    return [
        [[0, 0], [1, 0]],
        [[1, 1], [0, 1]],
        [[1, 0], [1, 1]],
        [[0, 0], [0, 1]],
    ]


def test_trechos_soltos_viram_um_anel_fechado():
    aneis = geo._montar_aneis(_quadrado_em_trechos())
    assert len(aneis) == 1
    assert geo._mesma_ponta(aneis[0][0], aneis[0][-1]), "o anel tem de fechar"
    assert abs(geo._area_aprox(aneis[0]) - 1.0) < 1e-9


def test_relacao_com_divisa_em_pedacos_vira_o_bairro_inteiro():
    """O caso real: a relação do bairro, com a divisa fatiada em ways."""
    el = {"type": "relation", "members": [
        {"role": "outer", "geometry": [{"lon": x, "lat": y} for x, y in t]}
        for t in _quadrado_em_trechos()
    ]}
    anel = geo._anel_do_elemento(el)
    assert abs(geo._area_aprox(anel) - 1.0) < 1e-9, (
        "pegar o trecho mais longo daria uma lasca de área zero")


def test_escolhe_por_area_e_nao_por_numero_de_pontos():
    """Um trecho de divisa cheio de detalhe tem mais PONTOS que o contorno
    de um bairro pequeno. Foi contando ponto que o código escolheu lascas."""
    detalhado = [[0.5 + i * 0.001, 0.5] for i in range(50)]   # linha, área ~0
    el = {"type": "relation", "members": (
        [{"role": "outer", "geometry": [{"lon": x, "lat": y} for x, y in t]}
         for t in _quadrado_em_trechos()]
        + [{"role": "outer",
            "geometry": [{"lon": x, "lat": y} for x, y in detalhado]}]
    )}
    anel = geo._anel_do_elemento(el)
    assert geo._area_aprox(anel) > 0.9, "o quadrado tem de vencer a linha"


def test_membro_inner_e_ignorado():
    el = {"type": "relation", "members": (
        [{"role": "outer", "geometry": [{"lon": x, "lat": y} for x, y in t]}
         for t in _quadrado_em_trechos()]
        + [{"role": "inner",
            "geometry": [{"lon": 0.4, "lat": 0.4}, {"lon": 0.6, "lat": 0.6}]}]
    )}
    assert abs(geo._area_aprox(geo._anel_do_elemento(el)) - 1.0) < 1e-9


def test_trecho_que_nao_emenda_nao_derruba_o_resto():
    """Divisa com um pedaço faltando não pode custar o bairro inteiro: sai um
    anel aberto, que ainda desenha melhor que nada."""
    trechos = _quadrado_em_trechos()[:3] + [[[9, 9], [9, 10]]]
    aneis = geo._montar_aneis(trechos)
    assert len(aneis) == 2
    assert max(len(a) for a in aneis) >= 4


def test_cache_de_versao_anterior_e_descartado(tmp_path, monkeypatch):
    """A v1 gravou lascas de divisa em vez do contorno. Sem carimbo de
    versão, dado errado que já entrou no cache seria permanente -- o cache
    existe justamente para nunca mais perguntar."""
    caminho = tmp_path / "b.json"
    monkeypatch.setattr(geo, "CAMINHO", str(caminho))
    caminho.write_text(json.dumps({
        "_versao": 1,
        "Recife|Pina": {"anel": [[0, 0], [1, 0], [0, 1]], "centro": [0, 0]},
    }), encoding="utf-8")
    assert geo.carregar() == {}


def test_cache_da_versao_atual_e_lido(tmp_path, monkeypatch):
    caminho = tmp_path / "b.json"
    monkeypatch.setattr(geo, "CAMINHO", str(caminho))
    geo.salvar({"Recife|Pina": {"anel": [[0, 0], [1, 0], [0, 1]], "centro": [0, 0]}})
    lido = geo.carregar()
    assert list(lido) == ["Recife|Pina"], "a chave de versão não vira bairro"
