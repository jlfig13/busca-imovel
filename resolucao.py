# -*- coding: utf-8 -*-
"""
Entity resolution: descobre quando anúncios de portais diferentes são o
mesmo apartamento.

P-03 da auditoria. Medido na base real: 41 grupos com (preço, quartos, área)
idênticos entre portais distintos, envolvendo 101 dos 185 anúncios -- 55% da
base era duplicata. O usuário avaliava o mesmo imóvel três vezes, e qualquer
mediana de preço por bairro saía enviesada pelos imóveis das imobiliárias
grandes, que anunciam em mais lugares.

Estratégia em três etapas:

  1. BLOCKING     -- só compara pares que já compartilham algo forte.
                     Comparar todos contra todos é quadrático; com 6 chaves
                     em união, cada uma cobrindo a falha das outras, o custo
                     cai sem perder par legítimo.
  2. COMPARADORES -- cada sinal devolve 0..1 ou None (dado ausente dos dois
                     lados). O score é a média ponderada APENAS sobre quem
                     pôde opinar, para que par com poucos campos não seja
                     penalizado por ausência -- mas também não ganhe
                     confiança que não tem (ver regra dos 3 comparadores).
  3. CLUSTERIZAÇÃO -- componentes conexos com trava de transitividade.

Princípio que orienta os limiares: neste domínio, agrupar errado é MUITO
pior que não agrupar. Juntar dois apartamentos distintos faz perder um
candidato real sem deixar rastro; falhar em juntar só repete uma linha.
"""
import json
import math
import re
import unicodedata

from utils import log

# ---------------------------------------------------------------------------
# Classificações
# ---------------------------------------------------------------------------
MESMO_IMOVEL = "MESMO_IMOVEL"
PROVAVELMENTE_MESMO = "PROVAVELMENTE_MESMO"
PROVAVELMENTE_DIFERENTE = "PROVAVELMENTE_DIFERENTE"
DIFERENTE = "DIFERENTE"

LIMIAR_MESMO = 0.88
LIMIAR_PROVAVEL = 0.72
LIMIAR_IMPROVAVEL = 0.55

# Mínimo de comparadores com dado nos dois lados para permitir MESMO_IMOVEL.
# Sem isso, "mesmo bairro + mesmo preço" -- dois sinais fracos -- bastaria
# para colapsar apartamentos diferentes do mesmo prédio.
MIN_COMPARADORES = 3

PESOS = {
    "geo": 0.20,
    "endereco": 0.18,
    "area": 0.15,
    "custo": 0.12,
    "fotos": 0.12,
    "comodos": 0.08,
    "condominio": 0.06,
    "descricao": 0.05,
    "contato": 0.04,
}


# ---------------------------------------------------------------------------
# Normalização de texto
# ---------------------------------------------------------------------------

_ABREV_LOGRADOURO = {
    "r": "rua", "av": "avenida", "trav": "travessa", "tv": "travessa",
    "pc": "praca", "pca": "praca", "al": "alameda", "rod": "rodovia",
    "estr": "estrada", "ed": "edificio", "edf": "edificio", "res": "residencial",
    "cond": "condominio", "apto": "apartamento", "ap": "apartamento",
}


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, sem pontuação, com abreviação expandida.

    Expandir abreviação é o que faz 'Ed. Maria Luiza' casar com
    'Edf Maria Luiza' e 'R. Gaspar Perez' com 'Rua Gaspar Perez' -- as duas
    grafias aparecem para o mesmo imóvel em portais diferentes."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFD", str(texto))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    palavras = [_ABREV_LOGRADOURO.get(p, p) for p in t.split()]
    return " ".join(palavras)


def _tokens(texto: str) -> set:
    return set(normalizar(texto).split())


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def similaridade_texto(a: str, b: str) -> float:
    """Jaccard sobre tokens. Suficiente e previsível para nomes de rua e
    de condomínio, que são curtos e têm ordem instável entre portais."""
    return jaccard(_tokens(a), _tokens(b))


# ---------------------------------------------------------------------------
# Comparadores -- cada um devolve 0..1 ou None ("não sei opinar")
# ---------------------------------------------------------------------------

def _decaimento(diferenca: float, tolerancia: float, limite: float) -> float:
    """1.0 dentro da tolerância, decai linear até 0 no limite."""
    if diferenca <= tolerancia:
        return 1.0
    if diferenca >= limite:
        return 0.0
    return 1.0 - (diferenca - tolerancia) / (limite - tolerancia)


def comp_geo(a: dict, b: dict):
    la, lo = a.get("latitude"), a.get("longitude")
    lb, lob = b.get("latitude"), b.get("longitude")
    if None in (la, lo, lb, lob):
        return None
    # equirretangular: sobra precisão de folga na escala de um bairro
    dx = (float(lo) - float(lob)) * 111320 * math.cos(math.radians(float(la)))
    dy = (float(la) - float(lb)) * 110540
    metros = math.hypot(dx, dy)
    if metros < 50:
        return 1.0
    if metros < 150:
        return 0.7
    if metros < 400:
        return 0.3
    return 0.0


def comp_endereco(a: dict, b: dict):
    ra, rb = a.get("logradouro"), b.get("logradouro")
    if not ra or not rb:
        return None
    score = similaridade_texto(ra, rb)
    na, nb = a.get("numero"), b.get("numero")
    if na and nb:
        score = min(1.0, score + 0.3) if str(na) == str(nb) else score * 0.5
    return score


def comp_area(a: dict, b: dict):
    aa, ab = a.get("area_m2"), b.get("area_m2")
    if not aa or not ab:
        return None
    # tolerância de 2% cobre área útil x área total e arredondamento
    return _decaimento(abs(aa - ab) / max(aa, ab), 0.02, 0.12)


def comp_custo(a: dict, b: dict):
    ca = a.get("custo_mensal_total") or a.get("preco")
    cb = b.get("custo_mensal_total") or b.get("preco")
    if not ca or not cb:
        return None
    return _decaimento(abs(ca - cb) / max(ca, cb), 0.01, 0.15)


def comp_fotos(a: dict, b: dict):
    """Jaccard sobre o conjunto de URLs de foto.

    Os portais reprocessam a imagem e trocam o domínio do CDN, então a URL
    inteira raramente bate. Compara-se o nome do arquivo, que costuma ser um
    hash do original e sobrevive ao reprocessamento."""
    fa, fb = _hashes_foto(a.get("fotos")), _hashes_foto(b.get("fotos"))
    if not fa or not fb:
        return None
    return jaccard(fa, fb)


def _hashes_foto(fotos) -> set:
    if not fotos:
        return set()
    if isinstance(fotos, str):
        try:
            fotos = json.loads(fotos)
        except (json.JSONDecodeError, TypeError):
            return set()
    nomes = set()
    for url in fotos or []:
        if not isinstance(url, str):
            continue
        m = re.search(r"/([0-9a-f]{16,})[/.]", url)
        if m:
            nomes.add(m.group(1))
        else:
            m = re.search(r"/([^/?]+)\.(?:jpe?g|webp|png)", url, re.IGNORECASE)
            if m:
                nomes.add(m.group(1).lower())
    return nomes


def comp_comodos(a: dict, b: dict):
    """Quartos, suítes, banheiros e vagas. Quartos diferentes é sinal forte
    de imóveis distintos, mesmo com tudo o mais parecido."""
    pares = []
    for campo in ("quartos", "suites", "banheiros", "vagas"):
        va, vb = a.get(campo), b.get(campo)
        if va is not None and vb is not None:
            pares.append(1.0 if int(va) == int(vb) else 0.0)
    if not pares:
        return None
    return sum(pares) / len(pares)


def comp_condominio(a: dict, b: dict):
    na, nb = a.get("condominio_nome"), b.get("condominio_nome")
    if not na or not nb:
        return None
    return similaridade_texto(na, nb)


def comp_descricao(a: dict, b: dict):
    da, db = a.get("descricao"), b.get("descricao")
    if not da or not db or len(da) < 60 or len(db) < 60:
        return None
    return jaccard(_tokens(da), _tokens(db))


def comp_contato(a: dict, b: dict):
    ta, tb = _so_digitos(a.get("telefone")), _so_digitos(b.get("telefone"))
    if ta and tb:
        return 1.0 if ta[-8:] == tb[-8:] else 0.0
    ia, ib = a.get("imobiliaria"), b.get("imobiliaria")
    if ia and ib:
        return similaridade_texto(ia, ib)
    return None


def _so_digitos(v):
    return re.sub(r"\D", "", str(v)) if v else ""


COMPARADORES = {
    "geo": comp_geo, "endereco": comp_endereco, "area": comp_area,
    "custo": comp_custo, "fotos": comp_fotos, "comodos": comp_comodos,
    "condominio": comp_condominio, "descricao": comp_descricao,
    "contato": comp_contato,
}


# ---------------------------------------------------------------------------
# Vetos -- sobrepõem qualquer score
# ---------------------------------------------------------------------------

def _vetar(a: dict, b: dict) -> str | None:
    """Devolve o motivo do veto, ou None."""
    ca, cb = a.get("cidade"), b.get("cidade")
    if ca and cb and normalizar(ca) != normalizar(cb):
        return "cidades diferentes"

    qa, qb = a.get("quartos"), b.get("quartos")
    if qa is not None and qb is not None and abs(int(qa) - int(qb)) >= 2:
        return "diferença de 2+ quartos"

    aa, ab = a.get("area_m2"), b.get("area_m2")
    if aa and ab and abs(aa - ab) / max(aa, ab) > 0.25:
        return "área diverge mais de 25%"

    # Portal sério não duplica o próprio anúncio: dois anúncios da mesma
    # fonte quase sempre são unidades distintas do mesmo prédio.
    if a.get("site") and a.get("site") == b.get("site"):
        return "mesma fonte"
    return None


# ---------------------------------------------------------------------------
# Comparação de um par
# ---------------------------------------------------------------------------

def comparar(a: dict, b: dict) -> dict:
    """Score e classificação de um par. Devolve também a contribuição de
    cada sinal, para que a decisão seja auditável (e revisável a mão)."""
    veto = _vetar(a, b)
    if veto:
        return {"score": 0.0, "classificacao": DIFERENTE,
                "sinais": {}, "veto": veto, "n_comparadores": 0}

    sinais, soma, peso_total = {}, 0.0, 0.0
    for nome, func in COMPARADORES.items():
        valor = func(a, b)
        if valor is None:
            continue
        sinais[nome] = round(valor, 3)
        soma += valor * PESOS[nome]
        peso_total += PESOS[nome]

    if peso_total == 0:
        return {"score": 0.0, "classificacao": DIFERENTE,
                "sinais": {}, "veto": "nenhum campo comparável",
                "n_comparadores": 0}

    score = soma / peso_total
    n = len(sinais)

    if score >= LIMIAR_MESMO:
        # Teto quando há pouca evidência: dois sinais fracos coincidindo não
        # é o mesmo que três independentes concordando.
        classificacao = MESMO_IMOVEL if n >= MIN_COMPARADORES else PROVAVELMENTE_MESMO
    elif score >= LIMIAR_PROVAVEL:
        classificacao = PROVAVELMENTE_MESMO
    elif score >= LIMIAR_IMPROVAVEL:
        classificacao = PROVAVELMENTE_DIFERENTE
    else:
        classificacao = DIFERENTE

    # Custo muito discrepante rebaixa mesmo com score alto
    if sinais.get("custo") == 0.0 and classificacao == MESMO_IMOVEL:
        classificacao = PROVAVELMENTE_MESMO

    return {"score": round(score, 4), "classificacao": classificacao,
            "sinais": sinais, "veto": None, "n_comparadores": n}


# ---------------------------------------------------------------------------
# Blocking
# ---------------------------------------------------------------------------

def _chaves_bloco(item: dict) -> set:
    """Chaves de bloco de um anúncio. União: cada chave cobre a falha das
    outras, e basta compartilhar uma para o par ser comparado."""
    chaves = set()
    q = item.get("quartos")

    # B1 geo: célula de ~150 m
    lat, lon = item.get("latitude"), item.get("longitude")
    if lat is not None and lon is not None:
        chaves.add(f"geo:{round(float(lat), 3)}:{round(float(lon), 3)}:{q}")

    # B2 endereço
    if item.get("logradouro"):
        chaves.add(f"end:{normalizar(item['logradouro'])}:{item.get('numero') or ''}")

    # B3 bairro + forma (a que revelou os 41 grupos da auditoria)
    #
    # Emite a faixa de área E as vizinhas. Sem isso a chave vira uma
    # fronteira dura: o caso clássico do Viva Real dizer 72 m² e o Zap 75 m²
    # cairia em faixas diferentes (70 e 75) e os dois anúncios do MESMO
    # apartamento nunca chegariam a ser comparados. O comparador de área já
    # sabe rejeitar o que for realmente diferente -- o bloco só precisa
    # garantir que o par seja examinado.
    if item.get("bairro") and item.get("area_m2"):
        faixa = round(item["area_m2"] / 5) * 5
        bairro_norm = normalizar(item["bairro"])
        for delta in (-5, 0, 5):
            chaves.add(f"forma:{bairro_norm}:{q}:{faixa + delta}")

    # B4 condomínio
    if item.get("condominio_nome"):
        chaves.add(f"cond:{normalizar(item['condominio_nome'])}:{q}")

    # B5 fotos
    for h in _hashes_foto(item.get("fotos")):
        chaves.add(f"foto:{h}")

    # B6 contato
    tel = _so_digitos(item.get("telefone"))
    if tel and item.get("custo_mensal_total"):
        faixa_preco = round(item["custo_mensal_total"] / 100) * 100
        chaves.add(f"tel:{tel[-8:]}:{q}:{faixa_preco}")

    return chaves


def gerar_pares(itens: list[dict]) -> set:
    """Pares de índices a comparar, a partir das chaves de bloco."""
    blocos: dict[str, list[int]] = {}
    for i, item in enumerate(itens):
        for chave in _chaves_bloco(item):
            blocos.setdefault(chave, []).append(i)

    pares = set()
    for indices in blocos.values():
        # bloco gigante indica chave mal escolhida; ignorar evita explosão
        if len(indices) > 60:
            continue
        for x in range(len(indices)):
            for y in range(x + 1, len(indices)):
                pares.add((min(indices[x], indices[y]), max(indices[x], indices[y])))
    return pares


# ---------------------------------------------------------------------------
# Clusterização
# ---------------------------------------------------------------------------

def agrupar(itens: list[dict]) -> tuple[list[list[int]], list[dict]]:
    """Agrupa anúncios em imóveis. Devolve (grupos, decisões).

    Componentes conexos com trava de transitividade: um cluster só se forma
    se TODOS os pares internos tiverem score >= LIMIAR_PROVAVEL. Sem isso,
    A~B e B~C arrastariam A e C para o mesmo imóvel mesmo sendo claramente
    diferentes -- e é assim que uma dedupe ingênua começa a perder imóveis."""
    pares = gerar_pares(itens)
    log.info(f"  dedupe: {len(itens)} anúncios, {len(pares)} pares no bloco")

    decisoes, arestas = [], {}
    for i, j in pares:
        r = comparar(itens[i], itens[j])
        if r["classificacao"] in (MESMO_IMOVEL, PROVAVELMENTE_MESMO):
            arestas[(i, j)] = r["score"]
        if r["classificacao"] != DIFERENTE:
            decisoes.append({"i": i, "j": j, **r})

    # união-busca sobre as arestas aceitas
    pai = list(range(len(itens)))

    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    for (i, j) in sorted(arestas, key=lambda p: -arestas[p]):
        ri, rj = raiz(i), raiz(j)
        if ri == rj:
            continue
        # trava: só une se todo par entre os dois grupos for aceitável
        grupo_i = [k for k in range(len(itens)) if raiz(k) == ri]
        grupo_j = [k for k in range(len(itens)) if raiz(k) == rj]
        if _coesos(itens, grupo_i, grupo_j):
            pai[ri] = rj

    grupos: dict[int, list[int]] = {}
    for k in range(len(itens)):
        grupos.setdefault(raiz(k), []).append(k)
    return list(grupos.values()), decisoes


def _coesos(itens, grupo_a, grupo_b) -> bool:
    """True se todo par entre os grupos alcança o limiar de provável."""
    for i in grupo_a:
        for j in grupo_b:
            if comparar(itens[i], itens[j])["score"] < LIMIAR_PROVAVEL:
                return False
    return True


# ---------------------------------------------------------------------------
# Consolidação
# ---------------------------------------------------------------------------

# Peso de confiança por fonte, usado para desempatar conflito. Portais
# grandes publicam a partir do cadastro estruturado da imobiliária; sites
# pequenos digitam a mão e erram mais.
PESO_FONTE = {
    "Viva Real": 1.0, "Zap Imóveis": 1.0, "Viva Real Olinda": 1.0,
    "Zap Imóveis Olinda": 1.0, "Imovelweb": 0.9, "Imovelweb Olinda": 0.9,
    "Portal CRECI Brasil": 0.95,
}
PESO_PADRAO = 0.8

_CAMPOS_NUMERICOS = ("preco", "area_m2", "quartos", "suites", "banheiros",
                     "vagas", "andar", "aluguel", "condominio", "iptu",
                     "custo_mensal_total", "latitude", "longitude")
_CAMPOS_TEXTO = ("bairro", "cidade", "logradouro", "numero", "cep",
                 "condominio_nome", "descricao")


def consolidar(anuncios: list[dict]) -> tuple[dict, list[dict]]:
    """Funde os anúncios de um imóvel num registro só.

    Devolve (imovel, conflitos). Divergência entre fontes é REGISTRADA, nunca
    resolvida em silêncio: se o Viva Real diz 72 m² e o Zap diz 75, o card
    mostra o valor escolhido com a ressalva -- escolher calado é como o
    usuário perde a chance de conferir."""
    imovel, conflitos = {}, []

    for campo in _CAMPOS_NUMERICOS + _CAMPOS_TEXTO:
        valores = [(a.get(campo), a.get("site")) for a in anuncios
                   if a.get(campo) not in (None, "")]
        if not valores:
            continue
        distintos = {_chave_valor(v): v for v, _ in valores}
        if len(distintos) == 1:
            imovel[campo] = valores[0][0]
            continue

        escolhido, criterio = _resolver_conflito(campo, valores)
        imovel[campo] = escolhido
        conflitos.append({
            "campo": campo,
            "valores": {s: v for v, s in valores},
            "escolhido": escolhido,
            "criterio": criterio,
        })

    imovel["qtd_fontes"] = len({a.get("site") for a in anuncios})
    imovel["urls"] = [a.get("url") for a in anuncios]
    imovel["sites"] = sorted({a.get("site") for a in anuncios if a.get("site")})
    imovel["custo_completo"] = any(a.get("custo_completo") for a in anuncios)
    return imovel, conflitos


def _chave_valor(v):
    """Números próximos contam como o mesmo valor (72.0 == 72)."""
    if isinstance(v, float):
        return round(v, 2)
    return v


def _resolver_conflito(campo: str, valores: list) -> tuple:
    """1) maioria simples; 2) mediana, se numérico; 3) fonte mais confiável."""
    contagem: dict = {}
    for v, _ in valores:
        contagem[_chave_valor(v)] = contagem.get(_chave_valor(v), 0) + 1
    topo = max(contagem.values())
    empatados = [k for k, n in contagem.items() if n == topo]
    if len(empatados) == 1 and topo > 1:
        return next(v for v, _ in valores if _chave_valor(v) == empatados[0]), "maioria"

    if campo in _CAMPOS_NUMERICOS:
        nums = sorted(float(v) for v, _ in valores)
        meio = len(nums) // 2
        mediana = nums[meio] if len(nums) % 2 else (nums[meio - 1] + nums[meio]) / 2
        return mediana, "mediana"

    melhor = max(valores, key=lambda x: PESO_FONTE.get(x[1], PESO_PADRAO))
    return melhor[0], "fonte_mais_confiavel"
