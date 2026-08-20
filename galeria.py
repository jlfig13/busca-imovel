# -*- coding: utf-8 -*-
"""
Catálogo de fotos de um anúncio, extraído da página do imóvel.

Por que existe: só Viva Real e Zap publicam JSON-LD com imagem na LISTAGEM,
e mesmo assim expõem cinco fotos por anúncio. As outras dezesseis fontes
chegavam ao dashboard sem foto nenhuma -- e card de imóvel sem foto é um
card que ninguém clica.

A página do anúncio tem a galeria inteira, mas não de um jeito padronizado:
cada portal usa um CDN e uma estrutura. O que funciona em todos é partir de
uma âncora confiável (JSON-LD `image` ou `og:image`, que a página declara
como SUA imagem principal) e recolher o resto do mesmo diretório do CDN.

Recolher todo `<img>` da página seria mais simples e traria logo, ícone de
WhatsApp, selo de CRECI e banner de campanha -- foi o que a primeira
medição mostrou: no Portal CRECI, o primeiro `<img>` da página é o logotipo.
"""
import re
from urllib.parse import urljoin, urlparse

from utils import log

# Máximo de fotos guardadas por anúncio. O banco é commitado a cada rodada e
# SQLite é binário: cada foto a mais é texto que volta para o git todo dia.
# Doze cobre um apartamento inteiro (sala, quartos, cozinha, banheiro, área)
# sem virar arquivo de mídia.
MAX_FOTOS = 12

# Pedaços de URL que denunciam imagem de interface, não do imóvel.
_LIXO = re.compile(
    r"(logo|icone|icon|sprite|avatar|placeholder|whatsapp|facebook|instagram"
    r"|banner|selo|marca|bandeira|flag|pixel|blank|spacer|loader|watermark)",
    re.IGNORECASE,
)
_EXTENSAO = re.compile(r"\.(jpe?g|png|webp|avif)(\?|$)", re.IGNORECASE)

_RE_OG = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)',
    re.IGNORECASE,
)
_RE_LD_IMAGE = re.compile(r'"image"\s*:\s*(\[[^\]]{0,6000}\]|"[^"]{5,600}")')
_RE_IMG = re.compile(
    r'<(?:img|source)[^>]+(?:data-src|data-lazy|data-original|srcset|src)='
    r'["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def _limpar(url: str, base: str) -> str | None:
    if not url or url.startswith("data:"):
        return None
    # srcset vem como "url 320w, url 1024w": fica a ÚLTIMA, que é a maior.
    # Pegar a primeira renderia miniatura de listagem no card grande.
    url = url.strip().split(",")[-1].strip().split(" ")[0]
    url = urljoin(base, url)
    if not url.startswith("http") or _LIXO.search(url) or not _EXTENSAO.search(url):
        return None
    return url


def _ancoras(html: str, base: str) -> list[str]:
    """Imagens que a própria página declara como principais do imóvel."""
    achadas = []
    for bruto in _RE_LD_IMAGE.findall(html):
        achadas += re.findall(r'"(https?://[^"]+)"', bruto)
    achadas += _RE_OG.findall(html)
    return [u for u in (_limpar(x, base) for x in achadas) if u]


def _prefixo(url: str) -> str:
    """Host + diretório da foto, sem o nome do arquivo.

    É o que separa a galeria do imóvel do resto do site: as fotos de um
    anúncio moram todas na mesma pasta do CDN."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path.rsplit('/', 1)[0]}/"


def coletar(html: str, url_pagina: str = "", limite: int = MAX_FOTOS) -> list[str]:
    """Fotos do imóvel, da mais provável para a menos, sem repetição."""
    if not html:
        return []

    ancoras = _ancoras(html, url_pagina)
    fotos = list(dict.fromkeys(ancoras))

    # Sem âncora não há de onde partir: devolver `<img>` solto aqui traria
    # interface em vez de imóvel, que é pior que não ter foto.
    if not fotos:
        return []

    pastas = {_prefixo(u) for u in fotos}
    for bruto in _RE_IMG.findall(html):
        candidata = _limpar(bruto, url_pagina)
        if not candidata or candidata in fotos:
            continue
        if any(candidata.startswith(p) for p in pastas):
            fotos.append(candidata)
        if len(fotos) >= limite:
            break

    return fotos[:limite]


# Card sem <img>: a Âncora põe a foto em background-image no style inline, e
# o Portal CRECI a esconde num atributo data-info='{"Imagem": "/file_..."}'.
# Sem ler esses dois esconderijos, as duas fontes chegavam ao dashboard sem
# imagem nenhuma, embora a foto estivesse no HTML que já tínhamos baixado.
_RE_BG = re.compile(r"background-image:\s*url\(\s*['\"]?([^)'\"]+)", re.I)
_RE_CAMINHO_IMG = re.compile(
    r"""["']((?:https?:)?/[^"']{5,300}?\.(?:jpe?g|png|webp|avif)[^"']{0,90})["']""",
    re.I,
)


def foto_de_card(tag, base: str = "", subidas: int = 4) -> str | None:
    """Foto de um card da listagem, subindo a partir do link do anúncio.

    Sobe nível a nível e devolve o primeiro achado, nesta ordem: <img>,
    background-image, caminho de imagem em atributo. Subir pouco é de
    propósito -- alguns níveis acima está a LISTA, e ali a "primeira foto"
    seria a do card vizinho. Quatro níveis porque é onde mora a foto do
    Portal CRECI (medido); no quinto já se alcança a lista inteira.
    """
    no = tag
    for _ in range(subidas + 1):
        if no is None or not hasattr(no, "find_all"):
            break

        for img in no.find_all("img"):
            bruto = img.get("srcset") or img.get("data-srcset") or ""
            cand = (bruto or img.get("src") or img.get("data-src")
                    or img.get("data-lazy") or "")
            limpa = _limpar(cand, base)
            if limpa:
                return limpa

        bloco = str(no)
        for m in _RE_BG.finditer(bloco):
            limpa = _limpar(m.group(1), base)
            if limpa:
                return limpa
        for m in _RE_CAMINHO_IMG.finditer(bloco):
            limpa = _limpar(m.group(1).replace("&amp;", "&"), base)
            if limpa:
                return limpa

        no = getattr(no, "parent", None)
    return None


# Portais com proteção anti-bot (OLX, Viva Real, Zap) devolvem 403 para
# requisição direta. Depois de tantas falhas seguidas no mesmo host, o
# resultado das próximas é conhecido -- e cada tentativa ainda custa os
# retries do utils.get_html. Medido: 3 anúncios do OLX gastaram 9
# requisições para nenhuma foto.
FALHAS_ATE_DESISTIR = 2


def _host(url: str) -> str:
    return urlparse(url).netloc.lower()


def enriquecer(itens: list[dict], buscar=None, minimo: int = 3,
               max_visitas: int = 60) -> int:
    """Completa o campo `fotos` dos itens que têm menos que `minimo`.

    Chamado só para o que vai ser EXIBIDO: visitar a cidade inteira gastaria
    uma requisição por anúncio para encher de foto imóvel que ninguém vai
    ver. Devolve quantos itens ganharam fotos.
    """
    import utils
    buscar = buscar or utils.fetch

    ganharam = visitas = 0
    falhas: dict[str, int] = {}

    for item in itens:
        if visitas >= max_visitas:
            break
        url = item.get("url")
        if not url or len(item.get("fotos") or []) >= minimo:
            continue
        host = _host(url)
        if falhas.get(host, 0) >= FALHAS_ATE_DESISTIR:
            continue

        visitas += 1
        html = buscar(url)
        if not html:
            falhas[host] = falhas.get(host, 0) + 1
            continue

        fotos = coletar(html, url)
        if len(fotos) > len(item.get("fotos") or []):
            item["fotos"] = fotos
            ganharam += 1
        else:
            # página que não entrega galeria (render por JS, por exemplo)
            # conta como falha do host: as irmãs não entregarão também
            falhas[host] = falhas.get(host, 0) + 1

    if visitas:
        desistidos = [h for h, n in falhas.items() if n >= FALHAS_ATE_DESISTIR]
        extra = f" · sem galeria: {', '.join(desistidos)}" if desistidos else ""
        log.info(f"galeria: {ganharam} de {visitas} anúncio(s) ganharam fotos{extra}")
    return ganharam
