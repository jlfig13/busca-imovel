# -*- coding: utf-8 -*-
"""
Extração de dados estruturados (JSON-LD / schema.org) das páginas de listagem.

Por que existe (P-02 da auditoria): os portais grandes publicam cada anúncio
como schema.org/Apartment num bloco <script type="application/ld+json">, com
os campos já separados e tipados. Enquanto isso, o scraper lia o texto
renderizado do card e tentava adivinhar os valores com regex -- o que
funcionou por um tempo no Viva Real e no Zap e colapsou por completo no OLX
(56 dos 57 registros entraram sem preço, quartos, área nem bairro).

Decisão de projeto: isto ENRIQUECE, não substitui.

A tentação era trocar a extração de texto por esta. Não dá: medido ao vivo
em 18/08/2026, o JSON-LD do Viva Real e do Zap traz name, url, image[],
description, address, numberOfBedrooms, numberOfBathroomsTotal, floorLevel e
floorSize -- mas NÃO traz preço. Preço só existe no texto do card.

Então cada fonte entrega o que tem de melhor: o card dá o preço, o JSON-LD dá
tudo o mais com precisão de cadastro (inclusive o logradouro, que a extração
por texto nunca capturou e que é o sinal mais forte de deduplicação).
"""
import json
import re

from utils import log

# Tipos schema.org que representam um imóvel anunciado.
_TIPOS_IMOVEL = {
    "Apartment", "House", "Residence", "SingleFamilyResidence",
    "RealEstateListing", "Accommodation", "Product",
}

_RE_BLOCO_LD = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)


def canonizar_url(url: str) -> str:
    """Forma canônica da URL, para casar card com JSON-LD.

    Necessário porque os dois lados escrevem a mesma URL de formas
    diferentes: o href do card carrega parâmetros de rastreamento
    (?source=ranking%2Crp) que o JSON-LD não tem. Sem normalizar, a
    interseção entre os dois conjuntos é zero -- medido: 0 de 30.

    Também serve de chave estável de anúncio: hoje a mesma página com dois
    parâmetros diferentes conta como dois imóveis distintos na base."""
    if not url:
        return ""
    return re.sub(r"[?#].*$", "", url).rstrip("/").lower()


def _num(valor):
    """Converte para número o que vier como int, float ou string."""
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        m = re.search(r"[\d.,]+", valor)
        if m:
            try:
                return float(m.group(0).replace(".", "").replace(",", "."))
            except ValueError:
                return None
    return None


def _area(floor_size):
    """floorSize vem como {'value': 70, 'unitCode': 'M2'} ou como número solto."""
    if isinstance(floor_size, dict):
        # Só aceita metro quadrado: unitCode FTK (pés²) apareceria com um
        # número plausível e entraria como se fosse m².
        if floor_size.get("unitCode") in (None, "M2", "MTK"):
            return _num(floor_size.get("value"))
        return None
    return _num(floor_size)


def _achar_objetos_imovel(obj, encontrados=None):
    """Percorre a estrutura procurando objetos que sejam um imóvel.

    Recursivo porque o JSON-LD dos portais aninha de formas diferentes:
    às vezes é uma lista solta no topo, às vezes vem dentro de
    ItemList.itemListElement, às vezes dentro de um @graph."""
    if encontrados is None:
        encontrados = []
    if isinstance(obj, dict):
        tipo = obj.get("@type")
        tipos = {tipo} if isinstance(tipo, str) else set(tipo or [])
        # exige url ou @id: sem identificador não há como casar com o card
        if tipos & _TIPOS_IMOVEL and (obj.get("url") or obj.get("@id")):
            encontrados.append(obj)
        for v in obj.values():
            _achar_objetos_imovel(v, encontrados)
    elif isinstance(obj, list):
        for item in obj:
            _achar_objetos_imovel(item, encontrados)
    return encontrados


def _normalizar(obj: dict) -> dict:
    """Traduz um objeto schema.org para o formato interno do projeto."""
    endereco = obj.get("address") or {}
    if not isinstance(endereco, dict):
        endereco = {}
    imagens = obj.get("image") or []
    if isinstance(imagens, str):
        imagens = [imagens]

    return {
        "titulo_origem": obj.get("name"),
        "quartos": _num(obj.get("numberOfBedrooms") or obj.get("numberOfRooms")),
        "banheiros": _num(obj.get("numberOfBathroomsTotal")),
        "area_m2": _area(obj.get("floorSize")),
        "andar": _num(obj.get("floorLevel")),
        "logradouro": endereco.get("streetAddress"),
        "cidade": endereco.get("addressLocality"),
        "cep": endereco.get("postalCode"),
        "descricao": obj.get("description"),
        "fotos": [i for i in imagens if isinstance(i, str)],
    }


def indexar_por_url(html: str) -> dict[str, dict]:
    """Devolve {url_do_anúncio: campos_normalizados} a partir do HTML.

    Indexado por URL porque é a única chave que o card e o JSON-LD
    compartilham -- é assim que o scraper casa os dois."""
    if not html:
        return {}

    indice: dict[str, dict] = {}
    for bruto in _RE_BLOCO_LD.findall(html):
        try:
            dados = json.loads(bruto.strip())
        except (json.JSONDecodeError, ValueError):
            continue  # bloco malformado não invalida os outros
        for obj in _achar_objetos_imovel(dados):
            url = obj.get("url") or obj.get("@id")
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            campos = _normalizar(obj)
            # Descarta o objeto que não acrescenta nada (ex: @type Product
            # de banner promocional, que casa o tipo mas vem vazio).
            if any(campos[k] is not None for k in ("quartos", "area_m2", "logradouro")):
                indice[canonizar_url(url)] = campos
    return indice


def enriquecer(itens: list[dict], indice: dict[str, dict]) -> int:
    """Completa os itens com o que o JSON-LD souber. Devolve quantos campos
    foram preenchidos.

    Só preenche o que está faltando: valor já extraído do card tem
    precedência, porque foi visto na tela do jeito que o usuário veria."""
    if not indice:
        return 0
    preenchidos = 0
    for item in itens:
        extra = indice.get(canonizar_url(item.get("url", "")))
        if not extra:
            continue
        for campo in ("quartos", "area_m2", "banheiros", "andar",
                      "logradouro", "cep", "descricao", "fotos"):
            valor = extra.get(campo)
            if valor in (None, [], "") or item.get(campo) not in (None, [], ""):
                continue
            item[campo] = int(valor) if campo in ("quartos", "banheiros", "andar") else valor
            preenchidos += 1
        # cidade só entra se o card não tiver detectado nada
        if not item.get("cidade") and extra.get("cidade"):
            item["cidade"] = extra["cidade"]
            preenchidos += 1
    if preenchidos:
        log.info(f"  JSON-LD completou {preenchidos} campo(s) em {len(itens)} imóveis")
    return preenchidos
