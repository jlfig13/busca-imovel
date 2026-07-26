# -*- coding: utf-8 -*-
"""
Scraper baseado em Playwright (headless Chromium) para sites que carregam
listagens via JavaScript e/ou têm proteção anti-bot (Viva Real, Zap Imóveis,
OLX, REMAX, CTI).

Requer: pip install playwright && python -m playwright install chromium
"""
import re
import time
from urllib.parse import urljoin

import utils
from utils import log

_ANTI_BOT_ARGS = ["--disable-blink-features=AutomationControlled"]
_ANTI_BOT_SCRIPT = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# padrão REMAX: card não usa rótulo "quarto"/"m²" -- são 5 números nus entre
# "Mensal" e "Apartamento" (quartos, banheiros, andar, área, vagas), ex:
# "R$ 2.500 Mensal\n\n2\n\n2\n\n9\n\n60\n\n1\n\nApartamento". Confirmado
# rodando contra o HTML real do site (5 anúncios distintos, mesmo padrão).
_RE_REMAX_NUMEROS = re.compile(
    r"Mensal\s*\n+(\d+)\s*\n+(\d+)\s*\n+(\d+)\s*\n+([\d.,]+)\s*\n+(\d+)\s*\n+Apartamento"
)


def _extrair_cards(page_obj, seletor_href: str) -> list[dict]:
    """Extrai cards de imóvel do DOM já carregado.
    seletor_href: substring do href que identifica links de imóvel individual.

    Sobe pela árvore a partir do link até achar um texto que contenha "R$"
    (mesma técnica do scraper_cards_inline.py). Sites com CSS modules/classes
    hasheadas (OLX, REMAX) não casam com seletores de classe fixos como
    '[class*="card"]' -- um closest() baseado nisso falha silenciosamente e
    cai num fallback cego (2 níveis acima), que tanto pode cortar o card
    antes do preço/área quanto ultrapassar para um container com vários
    anúncios misturados. Subir nível a nível até achar "R$" (com teto de
    tamanho) é mais confiável e é a causa raiz de cards do OLX aparecerem
    sem preço/área.

    Teto de 4000 chars (era 2000): no Imovelweb a descrição do imóvel é
    irmã do link (não ancestral) e sozinha já passa de 2000 chars, então
    o corte antigo parava um nível ANTES de alcançar o container que junta
    descrição + preço/quartos/área -- todo card do Imovelweb ficava sem
    dado nenhum. Confirmado medindo o tamanho real de cada nível no DOM
    ao vivo."""
    js = """els => {
        const MAX_SUBIDA = 6;
        const MAX_LEN = 4000;
        const seen = new Set();
        return els.map(e => {
            const href = e.href;
            if (seen.has(href)) return null;
            seen.add(href);
            let el = e;
            let melhorTexto = e.innerText || "";
            for (let i = 0; i < MAX_SUBIDA; i++) {
                if (!el.parentElement) break;
                el = el.parentElement;
                const texto = el.innerText || "";
                if (texto.length > MAX_LEN) break;
                melhorTexto = texto;
                if (texto.includes("R$")) break;
            }
            return {href, text: melhorTexto};
        }).filter(Boolean);
    }"""
    return page_obj.eval_on_selector_all(
        f'a[href*="{seletor_href}"]', js
    )


def _parse_card(card: dict, site_nome: str, cidade_padrao: str = "Recife") -> dict | None:
    texto = card.get("text", "")
    url = card.get("href", "")

    # Título: linha com "Apartamento" ou primeira linha substancial
    m = re.search(r"(Apartamento[^\n]{0,120})", texto)
    titulo = m.group(1).strip() if m else re.split(r"\n", texto.strip())[0][:120]

    if not utils.titulo_aceito(titulo):
        return None

    # cidade_padrao vem do site em config.SITES (cada portal aqui já é uma
    # busca de cidade única, exceto OLX: busca a região metropolitana
    # inteira, então o padrão "Cidade, Bairro" abaixo detecta a cidade
    # real por item em vez de usar o padrão do site.
    cidade = cidade_padrao

    # Bairro: múltiplos padrões em ordem de prioridade
    bairro = None
    # padrão Viva Real / Zap: "em\nBairro, Cidade"
    # \b é essencial: sem ele "em" casava dentro de qualquer palavra terminada
    # em "em" (ex: "Boa Viagem"), roubando a linha errada como bairro.
    m = re.search(r"\bem\b\s*\n([A-Za-zÀ-ú ]+),\s*\w", texto)
    if m:
        bairro = m.group(1).strip()
    # padrão REMAX: endereço termina "...Bairro, Recife, Pernambuco, CEP"
    # (confirmado ao vivo). Tem que vir ANTES do padrão OLX abaixo: senão
    # "Recife, Pernambuco" (cidade+ESTADO) casa por engano com o padrão
    # "Cidade, Bairro" e rouba "Pernambuco" como se fosse bairro.
    if not bairro:
        m = re.search(r"([A-Za-zÀ-ú][A-Za-zÀ-ú ]{2,28}),\s*Recife", texto)
        if m:
            bairro = m.group(1).strip()
    # padrão OLX: "Cidade, Bairro" em linha própria, ex: "Recife, Iputinga",
    # "Jaboatão dos Guararapes, Piedade" -- ordem CIDADE-primeiro, o
    # inverso do que se supunha antes (confirmado rodando contra o HTML
    # real do OLX, não só suposição).
    if not bairro:
        m = re.search(
            r"(Recife|Jaboat[aã]o dos Guararapes|Olinda|Paulista|Camaragibe|"
            r"S[aã]o Louren[çc]o da Mata|Cabo de Santo Agostinho|Ipojuca|"
            r"Igarassu|Abreu e Lima|Moreno)\s*,\s*([A-Za-zÀ-ú][A-Za-zÀ-ú ]{1,29})",
            texto,
        )
        if m:
            cidade = m.group(1).strip()
            bairro = m.group(2).strip()
    # padrão CTI: título "Apartamento para alugar no/na Bairro no condomínio X"
    if not bairro:
        m = re.search(
            r"para alugar n[ao]\s+(.+?)(?:\s+no condom[íi]nio|\n|$)",
            texto,
            re.IGNORECASE,
        )
        if m:
            bairro = m.group(1).strip()
    # padrão genérico: "Bairro: X"
    if not bairro:
        m = re.search(r"[Bb]airro[:\s]+([A-Za-zÀ-ú][A-Za-zÀ-ú ]{1,29})", texto)
        if m:
            bairro = m.group(1).strip()

    quartos = utils.parse_quartos(texto)
    area = utils.parse_area(texto)
    preco = utils.parse_preco_total(texto)

    if quartos is None or area is None:
        m_remax = _RE_REMAX_NUMEROS.search(texto)
        if m_remax:
            if quartos is None:
                quartos = int(m_remax.group(1))
            if area is None:
                area = utils._parse_valor_br(m_remax.group(4))

    return {
        "titulo": titulo,
        "bairro": bairro,
        "cidade": cidade,
        "preco": preco,
        "quartos": quartos,
        "area_m2": area,
        "url": url,
        "site": site_nome,
    }


def scrape(site: dict) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning(f"[{site['nome']}] Playwright não instalado. Pulando.")
        return []

    resultados = []
    vistos = set()
    max_paginas = site.get("max_paginas", 5)
    seletor_href = site.get("seletor_href", "/imovel/")
    wait_until = site.get("wait_until", "networkidle")
    cidade_padrao = site.get("cidade", "Recife")
    base_url = site["url_listagem"]
    sep = "&" if "?" in base_url else "?"
    # padrao_url_pagina: alguns sites (ex: Imovelweb) paginam por sufixo no
    # path ("-pagina-2.html"), não por query string ("?pagina=2"). Quando
    # presente, "{n}" é substituído pelo número da página.
    padrao_url_pagina = site.get("padrao_url_pagina")
    log.info(f"[{site['nome']}] abrindo Playwright (Chromium headless, max {max_paginas} páginas)...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=_ANTI_BOT_ARGS)
            ctx = browser.new_context(
                user_agent=_UA,
                locale="pt-BR",
                viewport={"width": 1366, "height": 768},
            )
            page = ctx.new_page()
            page.add_init_script(_ANTI_BOT_SCRIPT)

            for pagina in range(1, max_paginas + 1):
                if pagina == 1:
                    url = base_url
                elif padrao_url_pagina:
                    url = padrao_url_pagina.format(n=pagina)
                else:
                    url = f"{base_url}{sep}pagina={pagina}"
                try:
                    page.goto(url, wait_until=wait_until, timeout=45000)
                except Exception:
                    page.wait_for_timeout(3000)

                # Aguarda até o primeiro link de imóvel aparecer (máx 15s)
                try:
                    page.wait_for_selector(
                        f'a[href*="{seletor_href}"]',
                        timeout=15000,
                        state="attached",
                    )
                except Exception:
                    pass  # se não aparecer, tentamos mesmo assim

                time.sleep(1)
                cards = _extrair_cards(page, seletor_href)

                novos = 0
                for c in cards:
                    href = c.get("href", "")
                    if href in vistos:
                        continue
                    vistos.add(href)
                    novos += 1
                    item = _parse_card(c, site["nome"], cidade_padrao)
                    if item and utils.passa_no_filtro(
                        item["preco"], item["quartos"], item["area_m2"], item["cidade"]
                    ):
                        resultados.append(item)

                log.info(f"[{site['nome']}] p{pagina}: {novos} links novos")
                if novos == 0:
                    break

            browser.close()
    except Exception as e:
        log.warning(f"[{site['nome']}] Playwright falhou: {e}")
        return []

    log.info(f"[{site['nome']}] {len(resultados)} imóveis dentro do filtro (de {len(vistos)} anúncios)")
    return resultados
