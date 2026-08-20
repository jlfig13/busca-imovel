# -*- coding: utf-8 -*-
"""Testes do enriquecimento de custo pela página do anúncio."""
import config
import detalhe_custo
import utils

# Recorte fiel do que a CTI serve na página do imóvel 6882 (Graças).
PAGINA_CTI = """
<html><body>
  <h1>Apartamento para alugar Graças Recife</h1>
  <div class="valores">
    <span>Valor</span><strong>R$ 1.850,00</strong>
    <span>Condomínio</span><strong>R$ 953,00</strong>
    <span>IPTU</span><strong>R$ 194,00</strong>
    <span>Total</span><strong>R$ 2.997,00</strong>
  </div>
</body></html>
"""

PAGINA_SEM_ENCARGOS = "<html><body><p>Valor R$ 1.900,00</p></body></html>"


def _item(**kw):
    base = {"url": "https://ctiimobiliaria.com.br/imovel/x/1", "preco": 1850.0,
            "custo_mensal_total": 1850.0, "custo_completo": False,
            "quartos": 2, "area_m2": 70, "cidade": "Recife"}
    base.update(kw)
    return base


def test_corrige_o_custo_que_o_card_escondia():
    """R$ 1.850 no card, R$ 2.997 na página: é o caso que motivou o módulo."""
    itens = [_item()]
    assert detalhe_custo.enriquecer(itens, buscar=lambda u: PAGINA_CTI) == 1
    i = itens[0]
    assert i["condominio"] == 953.0 and i["iptu"] == 194.0
    assert i["preco"] == 2997.0
    assert i["custo_completo"] is True
    # e, com o custo real, o filtro passa a reprovar
    veredito, _ = utils.avaliar_filtro(i["preco"], i["quartos"], i["area_m2"], i["cidade"])
    assert veredito == utils.REPROVADO


def test_nao_visita_quem_ja_tem_custo_completo():
    """Cada visita é uma requisição: a fonte que já informou não paga isso."""
    visitas = []
    itens = [_item(custo_completo=True, condominio=300.0)]
    detalhe_custo.enriquecer(itens, buscar=lambda u: visitas.append(u) or PAGINA_CTI)
    assert visitas == []


def test_nao_visita_quem_ja_estourou_o_teto():
    """Somar encargos só aumenta o custo -- confirmar reprovação é desperdício."""
    visitas = []
    itens = [_item(preco=config.FILTROS["preco_max"] + 1,
                   custo_mensal_total=config.FILTROS["preco_max"] + 1)]
    detalhe_custo.enriquecer(itens, buscar=lambda u: visitas.append(u) or PAGINA_CTI)
    assert visitas == []


def test_visita_quem_esta_sem_preco():
    """Sem preço o item seria indeterminado; a página costuma resolver."""
    itens = [_item(preco=None, custo_mensal_total=None)]
    assert detalhe_custo.enriquecer(itens, buscar=lambda u: PAGINA_CTI) == 1
    assert itens[0]["preco"] == 2997.0


def test_pagina_sem_encargos_nao_mexe_no_item():
    """Página que também não informa condomínio deixa o item como estava.

    Sobrescrever com 'completo' aqui seria pior que não visitar: marcaria
    como confiável um total que continua sendo só o piso."""
    itens = [_item()]
    assert detalhe_custo.enriquecer(itens, buscar=lambda u: PAGINA_SEM_ENCARGOS) == 0
    assert itens[0]["custo_completo"] is False
    assert itens[0]["preco"] == 1850.0


def test_falha_de_rede_nao_derruba_a_rodada():
    itens = [_item()]
    assert detalhe_custo.enriquecer(itens, buscar=lambda u: None) == 0
    assert itens[0]["preco"] == 1850.0


def test_teto_de_visitas_por_rodada():
    """Portal com 200 cards incompletos não pode consumir a rodada inteira."""
    visitas = []
    itens = [_item(url=f"https://x/{n}") for n in range(10)]
    detalhe_custo.enriquecer(
        itens, buscar=lambda u: visitas.append(u) or PAGINA_SEM_ENCARGOS,
        max_visitas=3,
    )
    assert len(visitas) == 3


# ---------------------------------------------------------------------------
# galeria: catálogo de fotos da página do anúncio
# ---------------------------------------------------------------------------
import galeria

PAGINA_GALERIA = """
<html><head>
  <meta property="og:image" content="https://cdn.x.com/imoveis/99/capa.jpg">
</head><body>
  <img src="https://cdn.x.com/assets/logo.png">
  <img src="https://cdn.x.com/imoveis/99/sala.jpg">
  <img data-src="https://cdn.x.com/imoveis/99/quarto.webp">
  <img srcset="https://cdn.x.com/imoveis/99/cozinha.jpg 320w,
               https://cdn.x.com/imoveis/99/cozinha-g.jpg 1024w">
  <img src="https://outro.com/imoveis/99/vizinho.jpg">
</body></html>
"""


def test_galeria_parte_da_ancora_e_recolhe_a_mesma_pasta():
    fotos = galeria.coletar(PAGINA_GALERIA, "https://x.com/imovel/99")
    assert fotos[0] == "https://cdn.x.com/imoveis/99/capa.jpg"
    assert "https://cdn.x.com/imoveis/99/sala.jpg" in fotos
    assert "https://cdn.x.com/imoveis/99/quarto.webp" in fotos
    # srcset: fica a maior (a última do conjunto)
    assert "https://cdn.x.com/imoveis/99/cozinha-g.jpg" in fotos


def test_galeria_descarta_interface_e_pasta_alheia():
    """Logo do portal e imagem de outro host não são foto do imóvel.

    Recolher todo <img> da página traria logotipo, ícone de WhatsApp e selo
    de CRECI -- medido no Portal CRECI, onde o primeiro <img> é o logo."""
    fotos = galeria.coletar(PAGINA_GALERIA, "https://x.com/imovel/99")
    assert not any("logo" in f for f in fotos)
    assert not any("outro.com" in f for f in fotos)


def test_galeria_sem_ancora_devolve_vazio():
    """Sem og:image nem JSON-LD não há de onde partir; devolver <img> solto
    seria trazer interface em vez de imóvel."""
    assert galeria.coletar("<html><img src='https://x.com/a/b.jpg'></html>", "https://x.com") == []


def test_galeria_desiste_do_host_que_bloqueia():
    """OLX devolve 403: insistir gasta 3 retries por anúncio para nada."""
    tentativas = []

    def buscar(u):
        tentativas.append(u)
        return None

    itens = [{"url": f"https://pe.olx.com.br/a/{n}", "fotos": []} for n in range(6)]
    galeria.enriquecer(itens, buscar=buscar)
    assert len(tentativas) == galeria.FALHAS_ATE_DESISTIR


def test_galeria_nao_visita_quem_ja_tem_fotos():
    visitas = []
    itens = [{"url": "https://x/1", "fotos": ["a", "b", "c"]}]
    galeria.enriquecer(itens, buscar=lambda u: visitas.append(u) or PAGINA_GALERIA)
    assert visitas == []


# ---------------------------------------------------------------------------
# foto do card na listagem
# ---------------------------------------------------------------------------
from bs4 import BeautifulSoup


def _link(html):
    return BeautifulSoup(html, "html.parser").find("a")


def test_foto_do_card_ignora_o_icone_de_favorito():
    """No CTI a primeira <img> do card é o ícone de favorito.

    Pegar "a primeira imagem" deixava TODO card da fonte sem foto."""
    card = """<div><a href="/imovel/x">
        <img src="https://site.com/assets/icons/icon-favorito.svg">
        <img src="https://cdn.site.com/Imoveis/116/sala.jpg">
    </a></div>"""
    assert galeria.foto_de_card(_link(card)) == "https://cdn.site.com/Imoveis/116/sala.jpg"


def test_foto_do_card_em_background_image():
    """A Âncora não usa <img>: a foto está no style do bloco."""
    card = """<div><div style="background-image: url('https://cdn.site.com/ancora/4504/foto.jpg')">
        <a href="/imovel/x">Apartamento</a></div></div>"""
    assert galeria.foto_de_card(_link(card)) == "https://cdn.site.com/ancora/4504/foto.jpg"


def test_foto_do_card_em_atributo_data():
    """O Portal CRECI guarda a foto num data-info com JSON dentro."""
    card = ("""<div data-info='{ "Id": "1", "Imagem": "/file_storage/61/c2/foto.jpg?width=468" }'>"""
            """<a href="/Anuncio/Index/x">Apartamento</a></div>""")
    achada = galeria.foto_de_card(_link(card), "https://www.portalcreci.org.br")
    assert achada == "https://www.portalcreci.org.br/file_storage/61/c2/foto.jpg?width=468"


def test_foto_do_card_sem_imagem_nenhuma():
    assert galeria.foto_de_card(_link("<div><a href='/imovel/x'>só texto</a></div>")) is None
