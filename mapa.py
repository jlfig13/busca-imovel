# -*- coding: utf-8 -*-
"""Mapa de bairros em SVG, desenhado no arquivo, sem tiles.

POR QUE NÃO LEAFLET
-------------------
A referência (caiooaragao/rent_finder) usa Leaflet com tiles do OSM, e fica
ótimo -- mas é um app Next.js com servidor. Aqui o dashboard é UM arquivo que
abre por duplo clique e funciona offline; tile é requisição em tempo de
execução, e cairia junto com a rede. Decisão do usuário em 06/09/2026: manter
o offline.

O que se perde: mapa de rua por baixo, zoom contínuo, pan. O que se ganha: o
mapa continua desenhado num avião, e não há terceiro observando quem olha o
quê.

DIVISÃO DE TRABALHO
-------------------
Python emite só a GEOMETRIA (um <path> por bairro, sem cor). Cor, clique e
rótulo ficam no JS, porque precisam responder ao filtro e à preferência --
um mapa que não reage ao recorte seria decoração, e o pedido era "a busca e
visualização pelo mapa".

PROJEÇÃO
--------
Equiretangular com correção de cosseno na latitude. Numa área do tamanho da
Região Metropolitana o erro contra uma projeção de verdade é de fração de
pixel; usar Mercator aqui seria precisão que ninguém enxerga.
"""
import math

# Sem geometria não há mapa: melhor dizer isso do que desenhar um retângulo
# vazio e deixar a pessoa achar que não há imóveis.
VAZIO = ""


def _projetar(anel, lon_min, lat_max, k, escala):
    """[[lon,lat], ...] -> ["x,y", ...] em coordenadas do SVG.

    A origem é o CANTO superior-esquerdo da caixa (lon mínima, lat máxima),
    não o centro: medir a latitude a partir da mediana punha metade dos
    bairros com y negativo, fora do viewBox -- meia região desenhada fora
    da tela, sem erro nenhum no console.
    """
    pts = []
    for lon, lat in anel:
        x = (lon - lon_min) * k * escala
        y = (lat_max - lat) * escala   # y cresce para baixo, latitude para cima
        pts.append(f"{x:.1f},{y:.1f}")
    return pts


def caminhos(cache: dict, largura: int = 360, altura: int = 300,
             margem: int = 8) -> tuple[str, dict]:
    """Devolve (svg_interno, centros) para os bairros com polígono.

    `centros` mapeia "Cidade|Bairro" -> [x, y] em coordenadas do SVG, para o
    JS pousar o ponto e o rótulo sem repetir a projeção em JavaScript.
    """
    aneis = {k: v["anel"] for k, v in cache.items()
             if isinstance(v, dict) and v.get("anel")}
    if not aneis:
        return VAZIO, {}

    todos = [p for anel in aneis.values() for p in anel]
    lons = [p[0] for p in todos]
    lats = [p[1] for p in todos]
    lon_min, lon_max = min(lons), max(lons)
    lat_min, lat_max = min(lats), max(lats)
    k = math.cos(math.radians((lat_min + lat_max) / 2)) or 1.0

    dlon = (lon_max - lon_min) * k or 1e-9
    dlat = (lat_max - lat_min) or 1e-9
    # uma escala só para os dois eixos: escalas diferentes achatariam a
    # cidade, e bairro achatado deixa de ser reconhecível
    escala = min((largura - 2 * margem) / dlon, (altura - 2 * margem) / dlat)
    larg_util = dlon * escala
    alt_util = dlat * escala

    partes = []
    centros = {}
    for chave, anel in sorted(aneis.items()):
        pts = _projetar(anel, lon_min, lat_max, k, escala)
        if len(pts) < 3:
            continue
        d = "M" + "L".join(pts) + "Z"
        seguro = chave.replace('"', "")
        partes.append(f'<path class="mapa-bairro" data-b="{seguro}" d="{d}"/>')
        xs = [float(p.split(",")[0]) for p in pts]
        ys = [float(p.split(",")[1]) for p in pts]
        centros[chave] = [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)]

    if not partes:
        return VAZIO, {}

    vb = f"0 0 {larg_util:.0f} {alt_util:.0f}"
    svg = (f'<svg class="mapa-svg" viewBox="{vb}" '
           f'preserveAspectRatio="xMidYMid meet" role="img" '
           f'aria-label="Mapa de bairros">{"".join(partes)}</svg>')
    return svg, centros
