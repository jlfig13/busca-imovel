# -*- coding: utf-8 -*-
"""Testes da extração de dados estruturados (P-02 da auditoria).

Os fixtures reproduzem o formato real medido em 18/08/2026 nas páginas do
Viva Real e do Zap -- inclusive a ausência de preço, que é o motivo de esta
camada enriquecer em vez de substituir a extração por texto.
"""
import extracao_jsonld as ex

HTML_VIVAREAL = """
<html><head>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Viva Real"}</script>
<script type="application/ld+json">[
 {"@context":"https://schema.org","@type":"Apartment","@id":"2900406069",
  "name":"Apartamento para alugar com 70 m2, 2 quartos",
  "url":"https://www.vivareal.com.br/imovel/apto-iputinga-id-2893614874/",
  "image":["https://img/1.webp","https://img/2.webp"],
  "description":"EXCELENTE APARTAMENTO",
  "address":{"@type":"PostalAddress","streetAddress":"Rua Gaspar Perez",
             "addressLocality":"Recife","addressRegion":"PE"},
  "numberOfBedrooms":2,"numberOfBathroomsTotal":2,"floorLevel":3,
  "floorSize":{"@type":"QuantitativeValue","value":70,"unitCode":"M2"}}
]</script>
</head></html>
"""


def test_indexa_anuncio_do_jsonld():
    idx = ex.indexar_por_url(HTML_VIVAREAL)
    assert len(idx) == 1
    campos = next(iter(idx.values()))
    assert campos["quartos"] == 2
    assert campos["banheiros"] == 2
    assert campos["area_m2"] == 70
    assert campos["andar"] == 3
    assert campos["logradouro"] == "Rua Gaspar Perez"
    assert campos["cidade"] == "Recife"
    assert len(campos["fotos"]) == 2


def test_ignora_organization_e_outros_tipos():
    # o bloco Organization não pode virar um "imóvel"
    assert len(ex.indexar_por_url(HTML_VIVAREAL)) == 1


def test_canonizar_url_remove_rastreamento():
    # o href do card traz ?source=ranking%2Crp e o JSON-LD não; sem
    # normalizar, a interseção medida entre os dois foi 0 de 30
    a = ex.canonizar_url("https://www.vivareal.com.br/imovel/x-id-1/?source=ranking%2Crp")
    b = ex.canonizar_url("https://www.vivareal.com.br/imovel/x-id-1/")
    assert a == b


def test_canonizar_url_vazia():
    assert ex.canonizar_url("") == ""
    assert ex.canonizar_url(None) == ""


def test_enriquecer_completa_campos_faltantes():
    idx = ex.indexar_por_url(HTML_VIVAREAL)
    itens = [{"url": "https://www.vivareal.com.br/imovel/apto-iputinga-id-2893614874/?source=ranking",
              "preco": 2068, "quartos": None, "area_m2": None,
              "bairro": "Iputinga", "cidade": "Recife"}]
    n = ex.enriquecer(itens, idx)
    assert n > 0
    assert itens[0]["quartos"] == 2
    assert itens[0]["area_m2"] == 70
    assert itens[0]["logradouro"] == "Rua Gaspar Perez"


def test_enriquecer_nao_sobrescreve_o_que_veio_do_card():
    # o valor visto na tela tem precedência: é o que o usuário veria
    idx = ex.indexar_por_url(HTML_VIVAREAL)
    itens = [{"url": "https://www.vivareal.com.br/imovel/apto-iputinga-id-2893614874/",
              "preco": 2068, "quartos": 3, "area_m2": 99,
              "bairro": "Iputinga", "cidade": "Recife"}]
    ex.enriquecer(itens, idx)
    assert itens[0]["quartos"] == 3
    assert itens[0]["area_m2"] == 99


def test_enriquecer_sem_indice_nao_quebra():
    itens = [{"url": "https://x/y", "quartos": None}]
    assert ex.enriquecer(itens, {}) == 0


def test_json_malformado_nao_derruba_os_demais():
    html = ('<script type="application/ld+json">{quebrado</script>' + HTML_VIVAREAL)
    assert len(ex.indexar_por_url(html)) == 1


def test_area_em_unidade_estrangeira_e_ignorada():
    # floorSize em pés² traria um número plausível e entraria como m²
    html = HTML_VIVAREAL.replace('"unitCode":"M2"', '"unitCode":"FTK"')
    campos = next(iter(ex.indexar_por_url(html).values()))
    assert campos["area_m2"] is None


def test_html_vazio():
    assert ex.indexar_por_url("") == {}
    assert ex.indexar_por_url(None) == {}
