# -*- coding: utf-8 -*-
"""Geometria de bairro: cache versionado, buscado uma vez e reusado sempre.

POR QUE UM CACHE NO REPOSITÓRIO, E NÃO UMA CONSULTA POR RODADA
---------------------------------------------------------------
Fronteira de bairro não muda. Consultar o Overpass 12 vezes por dia para
receber o mesmo polígono seria carga gratuita num serviço voluntário da
OpenStreetMap -- e o projeto acabou de gastar uma fase inteira sendo
cuidadoso com carga alheia (robots.txt, Crawl-delay). O cache fica em
`geo/bairros.json`, versionado, e cada bairro é buscado UMA vez.

É a mesma forma de `triagem.json`: dado que muda devagar mora no
repositório, não no navegador nem numa requisição por rodada.

POR QUE O ARQUIVO DO rent_finder NÃO SERVIU
--------------------------------------------
O repositório caiooaragao/rent_finder tem um extrato de bairros de PE, e foi
o que motivou este módulo. Mas a consulta dele pede `place=suburb` e
`place=neighbourhood`, e os bairros de Recife e Olinda estão no OSM como
FRONTEIRA ADMINISTRATIVA (`boundary=administrative`, `admin_level=10`).
Resultado medido: 8 dos nossos 61 bairros tinham polígono -- 74 de 476
anúncios. Boa Viagem, Casa Caiada, Madalena, Torre e Pina, todos de fora.
Por isso a consulta aqui aceita as duas formas.

ATRIBUIÇÃO
----------
Os dados vêm da OpenStreetMap, sob ODbL, que EXIGE atribuição de quem
redistribui. O dashboard credita no rodapé. Não é formalidade: é a mesma
postura que fez o projeto respeitar robots.txt.
"""
import json
import os
import time
import urllib.parse
import urllib.request

import config
from utils import log

CAMINHO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "geo", "bairros.json")

OVERPASS = "https://overpass-api.de/api/interpreter"

# Uma consulta por bairro, com pausa. O Overpass é infraestrutura voluntária
# e pede uso comedido; como o cache torna cada bairro uma busca única na vida
# do projeto, a lentidão aqui não custa nada.
PAUSA_S = 2.0
TIMEOUT_S = 60


def carregar() -> dict:
    """Cache lido do repositório. Ausente ou quebrado devolve vazio.

    Igual à triagem: o mapa é conveniência, o catálogo é o produto. Um JSON
    corrompido não pode derrubar a rodada."""
    try:
        with open(CAMINHO, encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"geo/bairros.json ilegível ({e}); mapa fica sem geometria")
        return {}
    return dados if isinstance(dados, dict) else {}


def salvar(cache: dict) -> None:
    os.makedirs(os.path.dirname(CAMINHO), exist_ok=True)
    with open(CAMINHO, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, sort_keys=True, indent=1)


def chave(cidade: str, bairro: str) -> str:
    return f"{cidade}|{bairro}"


def _consulta(cidade: str, bairro: str) -> str:
    """Aceita as duas formas em que bairro aparece no OSM.

    `boundary=administrative` + `admin_level=10` é como Recife e Olinda
    mapeiam bairro oficial; `place=suburb|neighbourhood` é como aparece em
    cidades menores. Pedir só a segunda foi o que deixou 53 dos nossos
    bairros sem polígono no extrato do rent_finder.
    """
    area = bairro.replace('"', '')
    mun = cidade.replace('"', '')
    return f"""
[out:json][timeout:{TIMEOUT_S}];
area["name"="{mun}"]["admin_level"~"8"]->.mun;
(
  relation(area.mun)["name"="{area}"]["boundary"="administrative"];
  relation(area.mun)["name"="{area}"]["place"~"suburb|neighbourhood|quarter"];
  way(area.mun)["name"="{area}"]["place"~"suburb|neighbourhood|quarter"];
);
out geom;
""".strip()


# Caixa da Região Metropolitana do Recife, com folga. Existe por um caso
# concreto: o extrato do rent_finder casa nome de bairro sem checar município,
# e "Recife|Boa Vista" lá aponta para uma Boa Vista em PETROLINA, 700 km
# adentro -- polígono válido, cidade errada, e no mapa vira um bairro de
# Recife jogado no sertão. A consulta daqui já escopa por município, mas
# homônimo dentro do próprio estado é barato de descartar e caro de descobrir
# depois: no mapa isso não dá erro, só entorta a região inteira, porque um
# ponto distante estica a escala e espreme o resto num canto.
CAIXA_RMR = (-35.35, -8.55, -34.75, -7.65)   # lon_min, lat_min, lon_max, lat_max


def _na_regiao(anel: list[list[float]]) -> bool:
    """True quando o anel inteiro cai na caixa da RMR."""
    lo0, la0, lo1, la1 = CAIXA_RMR
    return all(lo0 <= lon <= lo1 and la0 <= lat <= la1 for lon, lat in anel)


def _anel_do_elemento(el: dict) -> list[list[float]] | None:
    """Extrai um anel [[lon,lat], ...] de um elemento do Overpass."""
    if el.get("type") == "way" and el.get("geometry"):
        return [[p["lon"], p["lat"]] for p in el["geometry"]]
    if el.get("type") == "relation":
        # Relação vira o maior anel externo. Buraco (inner) é ignorado de
        # propósito: num mapa de 360px de largura ele não aparece, e tratar
        # multipolígono aqui dobraria a complexidade sem efeito visível.
        melhor = None
        for m in el.get("members", []):
            if m.get("role") != "outer" or not m.get("geometry"):
                continue
            anel = [[p["lon"], p["lat"]] for p in m["geometry"]]
            if melhor is None or len(anel) > len(melhor):
                melhor = anel
        return melhor
    return None


def buscar(cidade: str, bairro: str, abrir=None) -> list[list[float]] | None:
    """Busca o polígono de um bairro. Devolve anel [[lon,lat], ...] ou None.

    `abrir` existe para o teste injetar a resposta sem rede."""
    corpo = urllib.parse.urlencode({"data": _consulta(cidade, bairro)}).encode()
    try:
        if abrir:
            bruto = abrir(corpo)
        else:
            req = urllib.request.Request(
                OVERPASS, data=corpo,
                headers={"User-Agent": "monitor-apartamentos (uso pessoal)"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S + 10) as r:
                bruto = r.read().decode("utf-8")
        dados = json.loads(bruto)
    except Exception as e:
        log.warning(f"[geo] {cidade}/{bairro}: {str(e)[:120]}")
        return None

    melhor = None
    for el in dados.get("elements", []):
        anel = _anel_do_elemento(el)
        if not anel or not _na_regiao(anel):
            continue
        if melhor is None or len(anel) > len(melhor):
            melhor = anel
    return melhor


def simplificar(anel: list[list[float]], tol: float = 0.0004) -> list[list[float]]:
    """Douglas-Peucker. Um bairro de Recife tem centenas de pontos no OSM e
    o mapa cabe em 360px: guardar a precisão de rua seria pagar KB por
    detalhe que nenhum pixel mostra.

    tol em graus: 0.0004 ~ 40 m, abaixo de um pixel nessa escala."""
    if len(anel) < 3:
        return anel

    def dist(p, a, b):
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        px, py = x1 + t * dx, y1 + t * dy
        return ((x - px) ** 2 + (y - py) ** 2) ** 0.5

    def dp(pts):
        if len(pts) < 3:
            return pts
        i, dmax = 0, 0.0
        for k in range(1, len(pts) - 1):
            d = dist(pts[k], pts[0], pts[-1])
            if d > dmax:
                i, dmax = k, d
        if dmax <= tol:
            return [pts[0], pts[-1]]
        return dp(pts[:i + 1])[:-1] + dp(pts[i:])

    return [[round(x, 5), round(y, 5)] for x, y in dp(anel)]


def centroide(anel: list[list[float]]) -> list[float]:
    """Centro do polígono, para posicionar rótulo e ponto."""
    if not anel:
        return [0.0, 0.0]
    xs = [p[0] for p in anel]
    ys = [p[1] for p in anel]
    return [round(sum(xs) / len(xs), 5), round(sum(ys) / len(ys), 5)]


def atualizar(pares: list[tuple[str, str]], abrir=None, teto: int = 25) -> dict:
    """Busca só os bairros que faltam no cache e devolve o cache atualizado.

    O teto por execução existe pelo mesmo motivo do teto de visitas ao
    detalhe: a rodada tem tempo, e o cache ACUMULA -- o que não couber hoje
    entra amanhã, e depois de alguns dias não falta mais nada."""
    cache = carregar()
    faltam = [(c, b) for c, b in pares if chave(c, b) not in cache]
    if not faltam:
        return cache

    buscados = 0
    for cidade, bairro in faltam[:teto]:
        anel = buscar(cidade, bairro, abrir=abrir)
        # Grava a AUSÊNCIA também: bairro que o OSM não tem não pode ser
        # perguntado de novo a cada rodada.
        cache[chave(cidade, bairro)] = (
            {"anel": simplificar(anel), "centro": centroide(anel)} if anel
            else {"anel": None, "centro": None}
        )
        buscados += 1
        if abrir is None:
            time.sleep(PAUSA_S)

    achados = sum(1 for c, b in faltam[:teto]
                  if cache[chave(c, b)].get("anel"))
    log.info(f"[geo] {buscados} bairro(s) consultado(s), {achados} com "
             f"polígono; faltam {max(0, len(faltam) - teto)} para a próxima")
    salvar(cache)
    return cache
