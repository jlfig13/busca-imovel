# -*- coding: utf-8 -*-
"""Mapa em SVG: projeção, recorte e a aba no dashboard.

O pedido foi "uma aba de mapa onde a busca e visualização seja pelo mapa",
com a decisão explícita de manter o dashboard offline -- por isso SVG
desenhado no arquivo, e não Leaflet com tiles.
"""
import json
import re

import geo
import mapa

# Quadradinhos com posição de verdade: Olinda ao NORTE de Recife. Sem isso o
# teste de projeção não distingue "certo" de "espelhado".
_R = 0.004


def _quadrado(lon, lat):
    return [[lon - _R, lat - _R], [lon + _R, lat - _R],
            [lon + _R, lat + _R], [lon - _R, lat + _R], [lon - _R, lat - _R]]


CACHE = {
    "Recife|Boa Viagem": {"anel": _quadrado(-34.897, -8.130)},
    "Recife|Boa Vista": {"anel": _quadrado(-34.891, -8.060)},
    "Olinda|Casa Caiada": {"anel": _quadrado(-34.845, -7.995)},
}


def test_sem_geometria_nao_desenha_retangulo_vazio():
    svg, centros = mapa.caminhos({})
    assert svg == mapa.VAZIO and centros == {}


def test_cache_so_com_ausencias_tambem_nao_desenha():
    """Bairro que o OSM não tem fica gravado com anel None, para não ser
    perguntado de novo. Isso não é geometria."""
    svg, centros = mapa.caminhos({"Recife|X": {"anel": None, "centro": None}})
    assert svg == mapa.VAZIO and centros == {}


def test_um_path_por_bairro_com_a_chave_no_dataset():
    svg, centros = mapa.caminhos(CACHE)
    assert svg.count('class="mapa-bairro"') == 3
    assert 'data-b="Olinda|Casa Caiada"' in svg
    assert set(centros) == set(CACHE)


def test_todo_ponto_cai_dentro_do_viewbox():
    """O bug que isto trava: a latitude era medida a partir da MEDIANA, então
    metade dos bairros saía com y negativo -- desenhados fora da tela, sem
    erro nenhum no console."""
    svg, centros = mapa.caminhos(CACHE)
    larg, alt = [float(v) for v in re.search(r'viewBox="0 0 (\S+) (\S+)"', svg).groups()]
    for x, y in centros.values():
        assert 0 <= x <= larg, (x, larg)
        assert 0 <= y <= alt, (y, alt)
    for x, y in re.findall(r"(-?[\d.]+),(-?[\d.]+)", svg[svg.index(' d="'):]):
        assert -0.6 <= float(x) <= larg + 0.6
        assert -0.6 <= float(y) <= alt + 0.6


def test_norte_fica_em_cima():
    """Casa Caiada (Olinda, -7.99) é ao norte de Boa Viagem (-8.13): no SVG,
    y menor. Espelhar o eixo daria um mapa plausível e errado."""
    _, c = mapa.caminhos(CACHE)
    assert c["Olinda|Casa Caiada"][1] < c["Recife|Boa Vista"][1]
    assert c["Recife|Boa Vista"][1] < c["Recife|Boa Viagem"][1]


def test_leste_fica_a_direita():
    """Casa Caiada (-34.845) é a leste de Boa Viagem (-34.897): x maior."""
    _, c = mapa.caminhos(CACHE)
    assert c["Olinda|Casa Caiada"][0] > c["Recife|Boa Viagem"][0]


def test_escala_igual_nos_dois_eixos():
    """Escalas diferentes achatariam a cidade e o bairro deixaria de ser
    reconhecível. Quadrado de lado igual em graus tem de sair quadrado (a
    menos da correção de cosseno na longitude, ~1% nesta latitude)."""
    svg, _ = mapa.caminhos({"Recife|Q": {"anel": _quadrado(-34.9, -8.05)}})
    pts = [(float(a), float(b))
           for a, b in re.findall(r"(-?[\d.]+),(-?[\d.]+)", svg[svg.index(' d="'):])]
    larg = max(p[0] for p in pts) - min(p[0] for p in pts)
    alt = max(p[1] for p in pts) - min(p[1] for p in pts)
    assert abs(larg / alt - 1) < 0.05


def test_aspas_no_nome_nao_quebram_o_atributo():
    svg, _ = mapa.caminhos({'Recife|A"B': {"anel": _quadrado(-34.9, -8.05)}})
    assert 'data-b="Recife|AB"' in svg


# --- guarda geográfica -------------------------------------------------
# Nasceu de um caso medido: o extrato de bairros do rent_finder casa nome sem
# checar município, e "Recife|Boa Vista" lá aponta para uma Boa Vista em
# PETROLINA, 700km adentro. Dos 8 bairros daquele arquivo, 6 estavam fora da
# região. No mapa isso não dá erro: estica a escala e espreme o resto num
# canto.

def test_recife_e_olinda_estao_na_regiao():
    assert geo._na_regiao(_quadrado(-34.897, -8.130))
    assert geo._na_regiao(_quadrado(-34.845, -7.995))


def test_homonimo_no_sertao_e_recusado():
    assert not geo._na_regiao(_quadrado(-40.542, -9.383))   # Petrolina


def test_anel_meio_dentro_meio_fora_e_recusado():
    """Tudo ou nada: polígono que vaza para fora da RMR é sinal de que casou
    a coisa errada, não de bairro grande."""
    anel = _quadrado(-34.9, -8.05) + [[-40.5, -9.3]]
    assert not geo._na_regiao(anel)
