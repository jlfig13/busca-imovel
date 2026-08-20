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
