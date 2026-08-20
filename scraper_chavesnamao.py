# -*- coding: utf-8 -*-
"""
Coletor do Chaves na Mão.

Ganha módulo próprio porque a fonte tem uma característica que nenhuma outra
tem: a LISTAGEM já vem com os dados estruturados embutidos no HTML (o objeto
`listingPreview` do payload do Next.js), com rua, área, quartos, banheiros,
vagas, bairro, cidade, foto e preço. Não é preciso adivinhar nada do texto
do card -- é o coletor mais confiável do projeto.

O custo é a exceção: `price` ali é só o ALUGUEL. Condomínio e IPTU existem
apenas na página do imóvel, que é renderizada por JavaScript (a requisição
simples devolve 146 KB sem nenhum valor). Como o teto de R$ 2.500 é sobre o
custo TOTAL, essa segunda visita não é opcional -- sem ela um apartamento de
R$ 2.900 de aluguel e R$ 1.100 de condomínio entraria na lista como se
coubesse no orçamento.

A visita usa Playwright e acontece só para quem ainda pode caber: quem já
estoura o teto só de aluguel é reprovado sem gastar página.

Paginação: `?pg=2` a `?pg=5`. O robots.txt do site bloqueia query string
(`Disallow: /*?*`) e ABRE exatamente esses cinco valores -- por isso o teto
de 5 páginas não é arbitrário.
"""
import json
import re
import time
from urllib.parse import urljoin

import config
import utils
from utils import log

# Tamanho do lote de páginas de detalhe. Cada uma é um Playwright goto com
# espera de render; 25 mantém a fonte na casa dos dois minutos, em linha com
# as outras que usam browser.
MAX_DETALHES = 25

# O payload do Next.js chega escapado dentro de uma string JS, então as
# aspas vêm como \". Casar os dois formatos evita depender de qual página
# (server-rendered ou hidratada) estamos lendo.
_RE_PREVIEW = re.compile(r'\\?"listingPreview\\?"\s*:\s*(\{.*?\})\s*,\s*\\?"singleProperty', re.S)


def _desescapar(bruto: str) -> str:
    return bruto.replace('\\"', '"').replace("\\\\", "\\")


def _cards(html: str) -> list[dict]:
    """Objetos de anúncio embutidos na listagem."""
    achados = []
    for bruto in _RE_PREVIEW.findall(html or ""):
        try:
            achados.append(json.loads(_desescapar(bruto)))
        except (ValueError, TypeError):
            continue
    return achados


def _item(card: dict, site: dict) -> dict | None:
    url = card.get("url")
    if not url:
        return None

    # "Boa Viagem, Recife/PE" -- bairro antes da vírgula, cidade depois.
    local = card.get("location") or ""
    bairro = cidade = None
    if "," in local:
        bairro, resto = local.split(",", 1)
        cidade = resto.split("/")[0].strip()
        bairro = bairro.strip()
    cidade = utils.cidade_do_bairro(bairro) or cidade or site.get("cidade")

    aluguel = utils._parse_valor_br(str(card.get("price"))) if card.get("price") else None
    area = utils._parse_valor_br(str(card.get("area"))) if card.get("area") else None

    foto = card.get("image")
    # O campo vem como caminho relativo do CDN de imagens da fonte.
    fotos = [f"https://images.chavesnamao.com.br/{foto}"] if foto else []

    item = {
        "url": urljoin(site["base_url"], url),
        "site": site["nome"],
        "titulo_origem": card.get("title"),
        "bairro": bairro,
        "cidade": cidade,
        "logradouro": card.get("street"),
        "quartos": card.get("bedrooms"),
        "banheiros": card.get("bathrooms"),
        "vagas": card.get("garages"),
        "area_m2": area,
        "aluguel": aluguel,
        "preco": aluguel,
        "custo_mensal_total": aluguel,
        # o card NÃO informa condomínio; quem completa é _completar_custos
        "custo_completo": False,
        "fotos": fotos,
    }
    item["titulo"] = utils.gerar_titulo(item)
    return item


# A página escreve os valores em rótulos fixos:
#
#   Aluguel R$ 1.800/mês · Condomínio R$ - · IPTU R$ -- ·
#   Aluguel + Condomínio R$ 1.801/mês
#
# "R$ -" e "R$ --" são valor AUSENTE, não zero. E o rótulo "Aluguel +
# Condomínio" contém a palavra "Condomínio": o utils.decompor_custo genérico
# lia o total como se fosse a taxa e somava tudo de novo -- medido, um
# apartamento de R$ 1.800 saiu como R$ 3.601. Daí o leitor próprio.
_RE_CNM_TOTAL = re.compile(r"Aluguel\s*\+\s*Condom[íi]nio\s*R\$\s*([\d.,]+)", re.I)
_RE_CNM_ALUGUEL = re.compile(r"Aluguel\s*R\$\s*([\d.,]+)", re.I)
_RE_CNM_COND = re.compile(r"Condom[íi]nio\s*R\$\s*([\d.,]+)", re.I)
_RE_CNM_IPTU = re.compile(r"IPTU\s*R\$\s*([\d.,]+)", re.I)


def _custo_do_texto(texto: str) -> dict:
    """Aluguel, condomínio, IPTU e total a partir da página do imóvel."""
    vazio = {"aluguel": None, "condominio": None, "iptu": None,
             "custo_mensal_total": None, "custo_completo": False}
    if not texto:
        return vazio

    total_declarado = None
    m = _RE_CNM_TOTAL.search(texto)
    if m:
        total_declarado = utils._parse_valor_br(m.group(1))
        # tira o rótulo composto do caminho antes de procurar a taxa isolada
        texto = texto[:m.start()] + texto[m.end():]

    aluguel = condominio = iptu = None
    m = _RE_CNM_ALUGUEL.search(texto)
    if m:
        aluguel = utils._parse_valor_br(m.group(1))
    m = _RE_CNM_COND.search(texto)
    if m:
        condominio = utils._parse_valor_br(m.group(1))
    m = _RE_CNM_IPTU.search(texto)
    if m:
        iptu = utils._parse_valor_br(m.group(1))

    if aluguel is None and total_declarado is None:
        return vazio

    total = (aluguel or 0) + (condominio or 0) + (iptu or 0)
    # O total declarado manda quando é maior: cobre o caso do aluguel com
    # centavos ("R$ 1.800,01" exibido como 1.800 no card).
    if total_declarado and total_declarado > total:
        total = total_declarado

    return {
        "aluguel": aluguel,
        "condominio": condominio,
        "iptu": iptu,
        "custo_mensal_total": total,
        # Sem taxa informada o total é PISO, não custo: o anúncio mostra
        # "Condomínio R$ -", que é ausência e não isenção.
        "custo_completo": condominio is not None,
    }


def _completar_custos(itens: list[dict], max_detalhes: int = MAX_DETALHES) -> int:
    """Lê condomínio e IPTU na página do imóvel, via browser.

    A página é renderizada por JavaScript: requisição simples devolve o HTML
    sem nenhum valor. Um browser só, várias páginas -- abrir e fechar o
    Chromium por anúncio custaria mais que a coleta inteira.
    """
    alvos = [i for i in itens
             if (i.get("preco") or 0) <= config.FILTROS["preco_max"]][:max_detalhes]
    if not alvos:
        return 0

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("[Chaves na Mão] Playwright ausente: custo fica só com o aluguel")
        return 0

    completados = 0
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch(headless=True)
            pagina = navegador.new_page(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"),
                locale="pt-BR",
            )
            for item in alvos:
                try:
                    pagina.goto(item["url"], wait_until="load", timeout=45000)
                    pagina.wait_for_timeout(2500)
                    texto = pagina.inner_text("body")
                except Exception:
                    continue

                custo = _custo_do_texto(texto)
                if not custo["custo_mensal_total"]:
                    continue
                item.update(custo)
                item["preco"] = custo["custo_mensal_total"]
                if custo["custo_completo"]:
                    completados += 1
            navegador.close()
    except Exception as e:
        log.warning(f"[Chaves na Mão] detalhe de custo falhou: {e}")

    log.info(f"[Chaves na Mão] custo completo em {completados} de {len(alvos)} anúncios")
    return completados


def scrape(site: dict) -> list[dict]:
    resultados = utils.ListaComStats()
    vistos: set[str] = set()
    brutos: list[dict] = []
    max_paginas = site.get("max_paginas", 5)

    for pagina in range(1, max_paginas + 1):
        url = site["url_listagem"] if pagina == 1 else f"{site['url_listagem']}?pg={pagina}"
        html = utils.fetch(url)
        if not html:
            resultados.stats["erros"] += 1
            break

        cards = _cards(html)
        if not cards and utils.detectar_bloqueio(html):
            resultados.stats["bloqueado"] = True
            resultados.stats["motivo"] = utils.FALHA_BLOQUEIO
            log.warning(f"[{site['nome']}] p{pagina}: bloqueio detectado")
            break

        novos = 0
        for card in cards:
            item = _item(card, site)
            if not item or item["url"] in vistos:
                continue
            vistos.add(item["url"])
            novos += 1
            brutos.append(item)

        log.info(f"[{site['nome']}] p{pagina}: {novos} anúncios novos")
        if not novos:
            break
        time.sleep(1)

    resultados.stats["brutos"] = len(brutos)

    # Só então o custo real -- e só para quem ainda pode caber no teto.
    _completar_custos(brutos)

    for item in brutos:
        veredito, motivos = utils.avaliar_filtro(
            item["preco"], item["quartos"], item["area_m2"], item["cidade"]
        )
        if veredito == utils.APROVADO:
            resultados.append(item)
        elif veredito == utils.INDETERMINADO:
            resultados.stats["indeterminados"] += 1
        else:
            resultados.stats["reprovados"] += 1

    return resultados
