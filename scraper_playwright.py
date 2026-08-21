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

import extracao_jsonld
import detalhe_custo
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

# padrão OLX: mesma ideia do REMAX -- números sem rótulo. O card sai como
# "Parque das Rosas Condomínio\n42m²\n2\n1\n1\n...\nR$ 1.300\nRecife, Torre",
# ou seja área com unidade e, logo depois, quartos / banheiros / vagas nus.
# Era a causa de todo anúncio do OLX entrar sem quartos: parse_quartos
# procura a palavra "quarto", que não existe no card.
# Confirmado contra o HTML ao vivo em 18/08/2026.
_RE_OLX_NUMEROS = re.compile(
    r"([\d.,]+)\s*m²\s*\n+(\d+)\s*\n+(\d+)\s*\n+(\d+)\b"
)


# Imagem de interface que aparece dentro do card (selo do portal, ícone de
# favorito, bandeira de "destaque") -- não é foto do imóvel.
_RE_FOTO_LIXO = re.compile(
    r"(logo|icone?|sprite|avatar|placeholder|whats|banner|selo|favorit"
    r"|marca|flag|blank|spacer|\.svg)",
    re.IGNORECASE,
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
    # raw string: o JS abaixo usa \. e \? nos regex, que o Python leria
    # como escapes inválidos
    js = r"""(els, seletor) => {
        const MAX_SUBIDA = 6;
        const MAX_LEN = 4000;
        const MAX_EXTRA = 600;
        const seen = new Set();

        // Um elemento que aponta para mais de um anúncio DISTINTO é a LISTA,
        // não um card.
        //
        // Contar "R$" não serve: um card legítimo tem vários -- "R$ 2.386 /
        // IPTU R$ 214 / Condomínio R$ 930" são três num anúncio só, e card
        // com queda de preço mostra o valor antigo e o novo.
        //
        // Contar <a> também não serve: o card do OLX tem dois links para o
        // MESMO anúncio (a foto e o título), o que marcaria todo card como
        // lista e deixaria 44 de 49 anúncios indeterminados.
        const ehLista = el => {
            const hrefs = new Set();
            for (const a of el.querySelectorAll(seletor)) hrefs.add(a.href);
            return hrefs.size > 1;
        };

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
                // Subir até o container da lista faz todo anúncio herdar
                // preço, área e quartos do vizinho -- medido no OLX: 20
                // apartamentos distintos saíram com valores idênticos.
                if (texto.length > MAX_LEN || ehLista(el)) break;
                melhorTexto = texto;
                if (texto.includes("R$")) {
                    // Sobe UM nível a mais quando ele ainda é o mesmo card.
                    // No OLX o nível com o preço tem 103 chars e termina
                    // antes do endereço; o pai (SECTION, 185) é que traz
                    // "Recife, Torre" -- parar no primeiro "R$" era a razão
                    // de todo card do OLX vir sem bairro.
                    const pai = el.parentElement;
                    if (pai && !ehLista(pai)) {
                        const textoPai = pai.innerText || "";
                        if (textoPai.length > texto.length &&
                            textoPai.length <= MAX_EXTRA) {
                            melhorTexto = textoPai;
                        }
                    }
                    break;
                }
            }
            // Foto do card. Vale por dois motivos: fonte que renderiza
            // por JS (REMAX) ou bloqueia requisição direta (OLX 403) não
            // entrega galeria nenhuma pela página do anúncio, e aqui a
            // imagem já está no DOM que o Playwright abriu -- custo zero.
            // srcset vem como "url 320w, url 640w": fica a última, que é a
            // maior.
            // Foto do card: a MAIOR imagem de verdade dentro dele.
            //
            // Pegar a primeira <img> não serve: no CTI a primeira é o
            // ícone de favorito (assets/icons/icon-favorito.svg), e todo
            // card chegava ao dashboard "sem foto". Ícone é pequeno e
            // costuma ser SVG; foto de imóvel é raster e grande -- por isso
            // o critério é tipo de arquivo mais área renderizada.
            const LIXO = /(logo|icone?|sprite|avatar|placeholder|whats|banner|selo|favorit|marca|flag|blank|spacer)/i;
            let foto = null, melhorArea = 0;
            for (const img of el.querySelectorAll("img")) {
                const bruto = img.getAttribute("srcset") ||
                              img.getAttribute("data-srcset");
                const cand = bruto
                    ? bruto.split(",").pop().trim().split(" ")[0]
                    : (img.currentSrc || img.src ||
                       img.getAttribute("data-src") ||
                       img.getAttribute("data-lazy") || "");
                if (!cand || !cand.startsWith("http") || LIXO.test(cand)) continue;
                if (/\.svg(\?|$)/i.test(cand)) continue;
                const area = (img.naturalWidth || img.width || 0) *
                             (img.naturalHeight || img.height || 0);
                if (area >= melhorArea) { melhorArea = area; foto = cand; }
            }
            return {href, text: melhorTexto, foto};
        }).filter(Boolean);
    }"""
    return page_obj.eval_on_selector_all(
        f'a[href*="{seletor_href}"]', js, f'a[href*="{seletor_href}"]'
    )


def _coletar_rolando(page_obj, seletor_href: str, passo: int = 700,
                     max_passos: int = 30) -> list[dict]:
    """Extrai os cards rolando a página, acumulando o que aparece.

    Extrair uma vez só não basta nos portais que virtualizam a lista: o OLX
    mantém o link no DOM desde o início mas deixa o innerText VAZIO enquanto
    o card não entra na viewport, e descarta o conteúdo de novo quando ele
    sai. Medido: 44 dos 49 anúncios chegavam sem texto nenhum, e o sintoma
    enganava porque os poucos cards acima da dobra funcionavam bem.

    Rolar e extrair a cada passo resolve os dois casos -- lazy-load simples
    e virtualização com descarte. Fica com o texto mais completo já visto
    para cada href, então um card que aparece parcialmente num passo não
    sobrescreve a versão boa de outro."""
    # Guarda texto E foto por href. A primeira versão acumulava só o texto e
    # remontava o card no fim -- a foto que _extrair_cards colhia era jogada
    # fora aqui, em silêncio, e o CTI (que traz 9 imagens dentro do próprio
    # link do card) chegava ao dashboard sem nenhuma.
    acumulado: dict[str, dict] = {}
    for _ in range(max_passos):
        for c in _extrair_cards(page_obj, seletor_href):
            href, texto = c.get("href", ""), c.get("text", "")
            if not href:
                continue
            atual = acumulado.setdefault(href, {"text": "", "foto": None})
            if len(texto) > len(atual["text"]):
                atual["text"] = texto
            # a foto aparece quando o card entra na viewport: fica a
            # primeira que vier, e passos seguintes não a apagam
            if not atual["foto"] and c.get("foto"):
                atual["foto"] = c["foto"]
        try:
            fim = page_obj.evaluate(
                "() => window.innerHeight + window.scrollY >= document.body.scrollHeight - 40"
            )
            if fim:
                break
            page_obj.mouse.wheel(0, passo)
            page_obj.wait_for_timeout(220)
        except Exception:
            break  # rolagem é otimização; falhar aqui não perde o que já veio
    return [{"href": h, **dados} for h, dados in acumulado.items()]


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
    # Endereço estruturado do card. No Imovelweb ele vem como
    # "Av. Min. Marcos Freire\nCasa Caiada, Olinda" -- era a fonte dos
    # imóveis sem bairro que sobravam, e ainda entrega o logradouro.
    logradouro, bairro_txt, cidade_txt = utils.endereco_do_texto(texto)

    cidade = cidade_txt or utils.cidade_do_slug(url) or cidade_padrao

    # Bairro: texto estruturado, depois slug da URL (ambos validados contra
    # a lista canônica), e só então os padrões por portal. Ver P-18: regex
    # sobre texto renderizado sem validação gravou "Pernambuco" como bairro.
    bairro = bairro_txt or utils.bairro_do_slug(url)
    # padrão Viva Real / Zap: "em\nBairro, Cidade"
    # \b é essencial: sem ele "em" casava dentro de qualquer palavra terminada
    # em "em" (ex: "Boa Viagem"), roubando a linha errada como bairro.
    if not bairro:
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

    # bairro conhecido manda na cidade: o padrão do site diz "Recife" mesmo
    # quando o anúncio é de Casa Caiada (Olinda) ou Candeias (Jaboatão)
    cidade = utils.cidade_do_bairro(bairro) or cidade

    quartos = utils.parse_quartos(texto)
    area = utils.parse_area(texto)
    custo = utils.decompor_custo(texto)
    preco = custo["custo_mensal_total"]

    vagas = None
    if quartos is None or area is None:
        m_remax = _RE_REMAX_NUMEROS.search(texto)
        if m_remax:
            if quartos is None:
                quartos = int(m_remax.group(1))
            if area is None:
                area = utils._parse_valor_br(m_remax.group(4))
        m_olx = _RE_OLX_NUMEROS.search(texto)
        if m_olx:
            if area is None:
                area = utils._parse_valor_br(m_olx.group(1))
            if quartos is None:
                quartos = int(m_olx.group(2))
            vagas = int(m_olx.group(4))

    # banheiros no card ("4 ban." / "2 banheiros"); o JSON-LD completa depois
    banheiros = None
    m_ban = re.search(r"(\d+)\s*(?:ban\.|banheiro)", texto, re.IGNORECASE)
    if m_ban:
        banheiros = int(m_ban.group(1))

    # Uma foto só, e é a do card: a galeria completa vem depois, da página
    # do anúncio, e só para os imóveis que serão exibidos.
    fotos = []
    foto_card = (card.get("foto") or "").strip()
    if foto_card.startswith("http") and not _RE_FOTO_LIXO.search(foto_card):
        fotos = [foto_card]

    item = {
        "titulo_origem": titulo,
        "fotos": fotos,
        "bairro": bairro,
        "logradouro": logradouro,
        "cidade": cidade,
        "preco": preco,
        "quartos": quartos,
        "banheiros": banheiros,
        "vagas": vagas,
        "area_m2": area,
        "url": url,
        "site": site_nome,
        **custo,
    }
    item["titulo"] = utils.gerar_titulo(item)
    return item


def scrape(site: dict) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning(f"[{site['nome']}] Playwright não instalado. Pulando.")
        indisponivel = utils.ListaComStats()
        indisponivel.stats["motivo"] = "playwright não instalado"
        indisponivel.stats["erros"] = 1
        return indisponivel

    resultados = utils.ListaComStats()
    vistos = set()
    max_paginas = site.get("max_paginas", 5)
    seletor_href = site.get("seletor_href", "/imovel/")
    wait_until = site.get("wait_until", "networkidle")
    cidade_padrao = site.get("cidade", "Recife")
    espera_ms = site.get("espera_ms", 2500)
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
                # O Playwright não passa por utils.get_html, então o
                # Crawl-delay precisa ser respeitado aqui também -- senão a
                # diretiva valeria só para as fontes de requests.
                utils.aguardar_vez(url)
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

                # Espera de acomodação. O seletor acima só garante que o
                # PRIMEIRO link existe -- preço, área e endereço chegam
                # depois, em outro passe de render.
                #
                # 1 s era pouco para o OLX: os links apareciam, o preço não,
                # e a subida na árvore terminava num nível sem "R$" -- 44 de
                # 49 anúncios saíam indeterminados. Com 4 s, os mesmos cards
                # trazem preço, quartos, área e bairro.
                time.sleep(espera_ms / 1000)

                cards = _coletar_rolando(page, seletor_href)

                # Uma página de desafio anti-bot devolve HTTP 200 e nenhum
                # card -- idêntico, para o código antigo, a "acabaram os
                # imóveis". Detectar aqui é o que evita que bloqueio vire
                # "a fonte esvaziou" lá na frente.
                if not cards and utils.detectar_bloqueio(page.content()):
                    resultados.stats["bloqueado"] = True
                    resultados.stats["motivo"] = utils.FALHA_BLOQUEIO
                    log.warning(f"[{site['nome']}] p{pagina}: bloqueio anti-bot detectado")
                    break

                novos = 0
                candidatos = []
                for c in cards:
                    href = c.get("href", "")
                    if href in vistos:
                        continue
                    vistos.add(href)
                    novos += 1
                    item = _parse_card(c, site["nome"], cidade_padrao)
                    if not item:
                        resultados.stats["reprovados"] += 1
                        continue
                    candidatos.append(item)

                # Enriquece ANTES de filtrar: quartos e área vindos do
                # JSON-LD podem resgatar um item que o texto do card deixaria
                # indeterminado. Filtrar primeiro jogaria fora exatamente os
                # anúncios que os dados estruturados salvariam.
                indice = extracao_jsonld.indexar_por_url(page.content())
                if indice:
                    extracao_jsonld.enriquecer(candidatos, indice)

                # Fonte que só mostra o aluguel no card (CTI) precisa da
                # página do anúncio para o custo real -- sem isso um imóvel
                # de R$ 2.997 entra como R$ 1.850 e ocupa a lista fingindo
                # caber no orçamento. Também vai ANTES do filtro: é
                # justamente o veredito que muda.
                if site.get("custo_no_detalhe"):
                    detalhe_custo.enriquecer(candidatos)

                for item in candidatos:
                    veredito, motivos = utils.avaliar_filtro(
                        item["preco"], item["quartos"], item["area_m2"], item["cidade"]
                    )
                    if veredito == utils.APROVADO:
                        resultados.append(item)
                    elif veredito == utils.INDETERMINADO:
                        resultados.stats["indeterminados"] += 1
                        log.debug(
                            f"[{site['nome']}] indeterminado ({', '.join(motivos)}): {item['url']}"
                        )
                    else:
                        resultados.stats["reprovados"] += 1

                log.info(f"[{site['nome']}] p{pagina}: {novos} links novos")
                if novos == 0:
                    break

            browser.close()
    except Exception as e:
        log.warning(f"[{site['nome']}] Playwright falhou: {e}")
        resultados.stats["erros"] += 1
        resultados.stats["motivo"] = str(e)[:180]
        resultados.stats["brutos"] = len(vistos)
        return resultados

    resultados.stats["brutos"] = len(vistos)
    log.info(
        f"[{site['nome']}] {len(resultados)} imóveis dentro do filtro "
        f"(de {len(vistos)} anúncios; {resultados.stats['indeterminados']} indeterminados)"
    )
    return resultados
