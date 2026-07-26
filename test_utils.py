# -*- coding: utf-8 -*-
"""Testes das funções de parsing em utils.py (regex sobre texto livre de
cards de anúncio). Rodar com: pytest test_utils.py"""
import utils


# ---------------------------------------------------------------------------
# parse_preco
# ---------------------------------------------------------------------------

def test_parse_preco_simples():
    assert utils.parse_preco("R$ 1.700") == 1700.0


def test_parse_preco_com_centavos():
    assert utils.parse_preco("R$: 3.500,00") == 3500.0


def test_parse_preco_sem_simbolo_retorna_none():
    # regressão do bug descrito no README: "3 quartos" não pode virar preço 3
    assert utils.parse_preco("3 quartos") is None


def test_parse_preco_ignora_numero_antes_do_simbolo():
    assert utils.parse_preco("3 quartos R$ 4.300") == 4300.0


def test_parse_preco_texto_vazio():
    assert utils.parse_preco("") is None
    assert utils.parse_preco(None) is None


# ---------------------------------------------------------------------------
# parse_area
# ---------------------------------------------------------------------------

def test_parse_area_padrao_br():
    assert utils.parse_area("Área Útil: 1.234,00 m²") == 1234.0


def test_parse_area_padrao_ponto_decimal():
    assert utils.parse_area("Área Útil: 39.00 m²") == 39.0


def test_parse_area_sem_pontuacao():
    assert utils.parse_area("70m²") == 70.0


def test_parse_area_m2_ascii():
    assert utils.parse_area("70 m2") == 70.0


def test_parse_area_ausente():
    assert utils.parse_area("Apartamento 3 quartos R$ 1.700") is None


# ---------------------------------------------------------------------------
# parse_quartos
# ---------------------------------------------------------------------------

def test_parse_quartos_antes_do_label():
    assert utils.parse_quartos("3 quartos") == 3


def test_parse_quartos_depois_do_label_tecimob():
    assert utils.parse_quartos("Dormitórios\t3") == 3


def test_parse_quartos_imobzi():
    assert utils.parse_quartos("bed 3") == 3


# ---------------------------------------------------------------------------
# parse_preco_aluguel
# ---------------------------------------------------------------------------

def test_parse_preco_aluguel_label_ancora():
    assert utils.parse_preco_aluguel("Aluguel R$ 2.400") == 2400.0


def test_parse_preco_aluguel_sufixo_imobzi():
    # padrão Imobzi tem que ganhar do valor de /total que vem depois
    texto = "R$ 2.400 /aluguel R$ 3.004 /total"
    assert utils.parse_preco_aluguel(texto) == 2400.0


def test_parse_preco_aluguel_fallback_plain():
    assert utils.parse_preco_aluguel("R$ 1.700") == 1700.0


# ---------------------------------------------------------------------------
# parse_preco_total (o que motivou a checagem: soma Remax
# aluguel + condomínio + IPTU)
# ---------------------------------------------------------------------------

def test_parse_preco_total_soma_remax():
    texto = (
        "R$ 1.700 Preço de Condomínio R$ 100 Valor do IPTU R$ 400"
    )
    assert utils.parse_preco_total(texto) == 2200.0


def test_parse_preco_total_pacote_locacao():
    texto = "Pacote de locação R$ 2.200"
    assert utils.parse_preco_total(texto) == 2200.0


def test_parse_preco_total_so_aluguel_sem_extras():
    assert utils.parse_preco_total("R$ 1.700") == 1700.0


def test_parse_preco_total_texto_vazio():
    assert utils.parse_preco_total("") is None


# ---------------------------------------------------------------------------
# titulo_aceito / passa_no_filtro
# ---------------------------------------------------------------------------

def test_titulo_aceito_residencial():
    assert utils.titulo_aceito("Apartamento 3 quartos") is True


def test_titulo_aceito_rejeita_comercial():
    assert utils.titulo_aceito("Sala Comercial no centro") is False


def test_passa_no_filtro_dentro_da_faixa():
    assert utils.passa_no_filtro(2000, 3) is True


def test_passa_no_filtro_preco_fora_da_faixa():
    assert utils.passa_no_filtro(5000, 3) is False


def test_passa_no_filtro_campos_ausentes_nao_reprovam():
    assert utils.passa_no_filtro(None, None) is True


def test_passa_no_filtro_area_ausente_nao_reprova():
    # OLX/REMAX não mostram m² no card da listagem -- área None não pode
    # derrubar o imóvel, senão essas duas fontes ficam sem resultado nenhum
    assert utils.passa_no_filtro(2000, 3, area=None) is True


# ---------------------------------------------------------------------------
# passa_no_filtro: perfil por cidade (Recife: 2+ qtos/60m²+, Olinda: 3+
# qtos/70m²+, cidade sem entrada cai no perfil padrão = Recife)
# ---------------------------------------------------------------------------

def test_passa_no_filtro_recife_aceita_2_quartos():
    assert utils.passa_no_filtro(2000, 2, area=60, cidade="Recife") is True


def test_passa_no_filtro_recife_rejeita_1_quarto():
    assert utils.passa_no_filtro(2000, 1, area=60, cidade="Recife") is False


def test_passa_no_filtro_recife_rejeita_area_abaixo_60():
    assert utils.passa_no_filtro(2000, 3, area=59, cidade="Recife") is False


def test_passa_no_filtro_olinda_rejeita_2_quartos():
    # Olinda exige 3+, diferente de Recife (2+)
    assert utils.passa_no_filtro(2000, 2, area=70, cidade="Olinda") is False


def test_passa_no_filtro_olinda_aceita_3_quartos_70m():
    assert utils.passa_no_filtro(2000, 3, area=70, cidade="Olinda") is True


def test_passa_no_filtro_olinda_rejeita_area_abaixo_70():
    assert utils.passa_no_filtro(2000, 3, area=65, cidade="Olinda") is False


def test_passa_no_filtro_cidade_desconhecida_usa_perfil_padrao():
    # cidade sem entrada em FILTROS_POR_CIDADE cai no perfil padrão
    # (Recife: 2+ quartos, 60m²+), não reprova por engano nem trava
    assert utils.passa_no_filtro(2000, 2, area=60, cidade="Jaboatão dos Guararapes") is True
