# -*- coding: utf-8 -*-
"""Testes das funções de parsing em utils.py (regex sobre texto livre de
cards de anúncio). Rodar com: pytest test_utils.py"""
from datetime import date

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


# ---------------------------------------------------------------------------
# avaliar_filtro -- veredito de três estados (P-01)
# ---------------------------------------------------------------------------

def test_avaliar_filtro_aprovado_com_dado_suficiente():
    veredito, motivos = utils.avaliar_filtro(2000, 3, 80, "Recife")
    assert veredito == utils.APROVADO
    assert motivos == []


def test_avaliar_filtro_tudo_ausente_e_indeterminado_nao_aprovado():
    # Este é o bug P-01: 56 dos 57 anúncios do OLX entraram na base assim,
    # sem preço/quartos/área/bairro, porque None era tratado como "passa".
    veredito, motivos = utils.avaliar_filtro(None, None, None, None)
    assert veredito == utils.INDETERMINADO
    assert veredito != utils.APROVADO
    assert "preço ausente" in motivos


def test_avaliar_filtro_sem_preco_e_indeterminado():
    veredito, _ = utils.avaliar_filtro(None, 3, 80, "Recife")
    assert veredito == utils.INDETERMINADO


def test_avaliar_filtro_preco_sem_forma_e_indeterminado():
    # preço na faixa, mas sem quartos nem área não dá para aplicar o
    # perfil da cidade -- é um link com um valor, não um imóvel avaliado
    veredito, motivos = utils.avaliar_filtro(2000, None, None, "Recife")
    assert veredito == utils.INDETERMINADO
    assert "quartos e área ausentes" in motivos


def test_avaliar_filtro_preco_fora_da_faixa_reprova():
    veredito, _ = utils.avaliar_filtro(5000, 3, 80, "Recife")
    assert veredito == utils.REPROVADO


def test_avaliar_filtro_olinda_2_quartos_reprova():
    veredito, _ = utils.avaliar_filtro(2000, 2, 80, "Olinda")
    assert veredito == utils.REPROVADO


def test_passa_no_filtro_continua_compativel_com_indeterminado():
    # a função antiga segue devolvendo True para o que não foi reprovado
    assert utils.passa_no_filtro(None, None) is True
    assert utils.passa_no_filtro(5000, 3) is False


# ---------------------------------------------------------------------------
# bairro_do_slug / cidade_do_slug (P-18)
# ---------------------------------------------------------------------------

def test_bairro_do_slug_portal_creci():
    url = "/Anuncio/Index/apartamento-3-quarto-alugar-114m2-pina-recife--pe_33327742"
    assert utils.bairro_do_slug(url) == "Pina"
    assert utils.cidade_do_slug(url) == "Recife"


def test_bairro_do_slug_multipalavra():
    url = "/imovel/4314734/apartamento-locacao-olinda-pe-bairro-novo-edf-estacao-verde"
    assert utils.bairro_do_slug(url) == "Bairro Novo"
    assert utils.cidade_do_slug(url) == "Olinda"


def test_bairro_do_slug_prefere_o_mais_longo():
    # "curado" casaria dentro de "curado-ii" e devolveria o bairro errado
    assert utils.bairro_do_slug("/imovel/apto-curado-ii-recife") == "Curado II"


def test_bairro_do_slug_ignora_o_que_nao_e_bairro():
    # sem validação contra a lista canônica, regex solto já gravou
    # "Pernambuco" e trechos de rodapé como bairro (P-05)
    assert utils.bairro_do_slug("/imovel/apartamento-pernambuco-brasil") is None
    assert utils.bairro_do_slug("/nada-de-util-aqui") is None
    assert utils.bairro_do_slug("") is None


def test_bairro_do_slug_nao_casa_no_meio_de_palavra():
    assert utils.bairro_do_slug("/imovel/apto-no-torreao-grande") is None


# ---------------------------------------------------------------------------
# detectar_bloqueio (P-11)
# ---------------------------------------------------------------------------

def test_detectar_bloqueio_cloudflare():
    assert utils.detectar_bloqueio("<html>Just a moment... cf-browser-verification</html>") is True


def test_detectar_bloqueio_datadome():
    assert utils.detectar_bloqueio("<html><script src='geo.captcha-delivery.com'>") is True


def test_detectar_bloqueio_pagina_legitima():
    assert utils.detectar_bloqueio("<html>Apartamento R$ 2.000 em Boa Viagem</html>") is False
    assert utils.detectar_bloqueio(None) is False


# ---------------------------------------------------------------------------
# Idade do anúncio -- Portal CRECI carimba a data de atualização no card
# ---------------------------------------------------------------------------

def test_data_atualizacao_do_card_creci():
    texto = "Cód. AP1180 BOA VIAGEM, RECIFE - PE CRECIPE 7986 Atualizado em: 15/08/2026 00:18:59"
    assert utils.data_atualizacao(texto) == date(2026, 8, 15)


def test_data_atualizacao_ausente():
    assert utils.data_atualizacao("Apartamento R$ 2.000 em Boa Viagem") is None
    assert utils.data_atualizacao("") is None


def test_data_atualizacao_invalida_nao_quebra():
    assert utils.data_atualizacao("Atualizado em: 32/13/2026") is None


def test_anuncio_recente_dentro_do_prazo():
    hoje = date.today().strftime("%d/%m/%Y")
    recente, idade = utils.anuncio_recente(f"Atualizado em: {hoje}")
    assert recente is True
    assert idade == 0


def test_anuncio_antigo_e_descartado():
    recente, idade = utils.anuncio_recente("Atualizado em: 01/01/2026", dias_max=30)
    assert recente is False
    assert idade > 30


def test_sem_carimbo_de_data_e_mantido():
    # ausência de data não é prova de anúncio velho, e a maioria das
    # fontes simplesmente não informa
    recente, idade = utils.anuncio_recente("Apartamento R$ 2.000")
    assert recente is True
    assert idade is None


# ---------------------------------------------------------------------------
# endereco_do_texto -- resolveu os 13% sem bairro
# ---------------------------------------------------------------------------

def test_endereco_padrao_imovelweb():
    texto = "R$ 11.000\n162 m² tot.\n4 quartos\nAv. Min. Marcos Freire\nCasa Caiada, Olinda\n"
    logradouro, bairro, cidade = utils.endereco_do_texto(texto)
    assert logradouro == "Av. Min. Marcos Freire"
    assert bairro == "Casa Caiada"
    assert cidade == "Olinda"


def test_endereco_padrao_moradasol_com_texto_colado():
    # o card do Moradasol vem sem separador: "ApartamentoBoa Viagem - Recife - PE"
    texto = "ExclusivoAP1233-MOSAApartamentoBoa Viagem - Recife - PEEd. Bouganvile60 m²"
    _, bairro, cidade = utils.endereco_do_texto(texto)
    assert bairro == "Boa Viagem"
    assert cidade == "Recife"


def test_endereco_rejeita_bairro_invalido():
    # sem validação contra o gazetteer, este padrão capturaria qualquer coisa
    # na posição certa -- foi assim que "Pernambuco" virou bairro (P-05)
    assert utils.endereco_do_texto("Pernambuco - Recife - PE")[1] is None
    assert utils.endereco_do_texto("somos a referencia local - Recife - PE")[1] is None


def test_endereco_texto_vazio():
    assert utils.endereco_do_texto("") == (None, None, None)


def test_ou_nao_localizado():
    assert utils.ou_nao_localizado(None) == utils.NAO_LOCALIZADO
    assert utils.ou_nao_localizado("") == utils.NAO_LOCALIZADO
    assert utils.ou_nao_localizado([]) == utils.NAO_LOCALIZADO
    assert utils.ou_nao_localizado("Rua X") == "Rua X"
    assert utils.ou_nao_localizado(3) == "3"
    # zero é valor legítimo (térreo), não ausência
    assert utils.ou_nao_localizado(0) == "0"


def test_bairro_no_inicio_do_titulo():
    assert utils.bairro_no_inicio(
        "Boa Vista Apartamento Semi-mobiliado para locação na Boa Vista") == "Boa Vista"


def test_bairro_no_inicio_rejeita_mencao_de_proximidade():
    # "a 10 minutos de Boa Viagem" descreve a vizinhança, não onde o imóvel
    # fica -- atribuir o bairro errado é pior do que não ter bairro
    assert utils.bairro_no_inicio("Apartamento otimo, a 10 minutos de Boa Viagem") is None
    assert utils.bairro_no_inicio("Apartamento com acesso rapido a Casa Amarela") is None


def test_bairro_no_inicio_sem_bairro_conhecido():
    assert utils.bairro_no_inicio("Apartamento sem referencia nenhuma") is None
    assert utils.bairro_no_inicio("") is None


# ---------------------------------------------------------------------------
# robots.txt (P-17)
# ---------------------------------------------------------------------------

def test_robots_sem_arquivo_nao_e_proibicao():
    """Ausência de robots.txt não proíbe nada.

    Tratá-la como proibição foi o erro que manteve Nogueira e Paulo Miranda
    fora do monitoramento por meses, com uma nota afirmando uma restrição
    que não existia."""
    import robots
    assert robots.SEM_ROBOTS != robots.PROIBIDO


def test_robots_detecta_html_como_ausencia():
    # servidor com catch-all devolve a home em /robots.txt com HTTP 200;
    # isso não é um robots.txt
    import robots
    assert robots._dominio("https://x.com.br/a/b") == "https://x.com.br"
