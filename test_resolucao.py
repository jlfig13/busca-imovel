# -*- coding: utf-8 -*-
"""Testes da resolução de entidade (P-03 da auditoria).

O princípio que estes testes protegem: agrupar errado é MUITO pior que não
agrupar. Juntar dois apartamentos distintos faz perder um candidato real sem
deixar rastro; falhar em juntar só repete uma linha na lista.
"""
import resolucao as r


def _anuncio(**kw):
    base = {"site": "Viva Real", "cidade": "Recife", "bairro": "Boa Viagem",
            "quartos": 2, "area_m2": 70.0, "custo_mensal_total": 2000.0,
            "url": "https://x/1"}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------

def test_normalizar_expande_abreviacao():
    # 'Ed. Maria Luiza' e 'Edf Maria Luiza' são o mesmo condomínio
    assert r.normalizar("Ed. Maria Luiza") == r.normalizar("Edf Maria Luiza")
    assert r.normalizar("R. Gaspar Perez") == r.normalizar("Rua Gaspar Perez")


def test_normalizar_remove_acento_e_caixa():
    assert r.normalizar("Graças") == r.normalizar("GRACAS")


# ---------------------------------------------------------------------------
# Vetos
# ---------------------------------------------------------------------------

def test_veto_cidades_diferentes():
    a, b = _anuncio(), _anuncio(site="Zap", cidade="Olinda")
    assert r.comparar(a, b)["classificacao"] == r.DIFERENTE


def test_veto_diferenca_de_dois_quartos():
    a, b = _anuncio(quartos=2), _anuncio(site="Zap", quartos=4)
    assert r.comparar(a, b)["classificacao"] == r.DIFERENTE


def test_veto_area_muito_diferente():
    a, b = _anuncio(area_m2=70), _anuncio(site="Zap", area_m2=120)
    assert r.comparar(a, b)["classificacao"] == r.DIFERENTE


def test_veto_mesma_fonte():
    # portal sério não duplica o próprio anúncio: quase sempre são
    # unidades distintas do mesmo prédio
    a, b = _anuncio(), _anuncio(url="https://x/2")
    res = r.comparar(a, b)
    assert res["classificacao"] == r.DIFERENTE
    assert res["veto"] == "mesma fonte"


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------

def test_mesmo_imovel_em_portais_diferentes():
    a = _anuncio(logradouro="Rua Gaspar Perez", banheiros=2, vagas=1)
    b = _anuncio(site="Zap Imóveis", logradouro="R. Gaspar Perez",
                 banheiros=2, vagas=1, url="https://y/1")
    res = r.comparar(a, b)
    assert res["classificacao"] == r.MESMO_IMOVEL
    assert res["score"] >= r.LIMIAR_MESMO


def test_area_com_pequena_divergencia_ainda_casa():
    # Viva Real 72 m² x Zap 75 m²: mesma unidade, medida de formas diferentes
    a = _anuncio(area_m2=72, logradouro="Rua A", banheiros=2)
    b = _anuncio(site="Zap", area_m2=75, logradouro="Rua A", banheiros=2,
                 url="https://y/1")
    assert r.comparar(a, b)["classificacao"] in (r.MESMO_IMOVEL, r.PROVAVELMENTE_MESMO)


def test_poucos_comparadores_nao_alcanca_mesmo_imovel():
    # dois sinais fracos coincidindo não é o mesmo que três independentes
    # concordando -- do contrário "mesmo bairro + mesmo preço" bastaria
    a = {"site": "A", "cidade": "Recife", "custo_mensal_total": 2000.0}
    b = {"site": "B", "cidade": "Recife", "custo_mensal_total": 2000.0}
    res = r.comparar(a, b)
    assert res["classificacao"] != r.MESMO_IMOVEL


def test_sem_campo_comparavel_e_diferente():
    assert r.comparar({"site": "A"}, {"site": "B"})["classificacao"] == r.DIFERENTE


# ---------------------------------------------------------------------------
# Blocking
# ---------------------------------------------------------------------------

def test_blocking_une_faixas_de_area_vizinhas():
    # 72 m² e 75 m² caem em faixas diferentes (70 e 75); sem as chaves
    # vizinhas o par nunca seria comparado
    a = _anuncio(area_m2=72)
    b = _anuncio(site="Zap", area_m2=75)
    assert r._chaves_bloco(a) & r._chaves_bloco(b)


def test_blocking_gera_par_para_anuncios_semelhantes():
    itens = [_anuncio(), _anuncio(site="Zap", url="https://y/1")]
    assert (0, 1) in r.gerar_pares(itens)


def test_blocking_ignora_anuncios_sem_nada_em_comum():
    a = _anuncio(bairro="Boa Viagem", area_m2=70)
    b = _anuncio(site="Zap", bairro="Fragoso", area_m2=200, quartos=5)
    assert not (r._chaves_bloco(a) & r._chaves_bloco(b))


# ---------------------------------------------------------------------------
# Clusterização
# ---------------------------------------------------------------------------

def test_agrupa_tres_portais_no_mesmo_imovel():
    itens = [
        _anuncio(site="Viva Real", logradouro="Rua A", banheiros=2, url="u1"),
        _anuncio(site="Zap Imóveis", logradouro="Rua A", banheiros=2, url="u2"),
        _anuncio(site="OLX", logradouro="Rua A", banheiros=2, url="u3"),
    ]
    grupos, _ = r.agrupar(itens)
    assert len(grupos) == 1
    assert len(grupos[0]) == 3


def test_nao_agrupa_imoveis_distintos():
    itens = [
        _anuncio(site="A", bairro="Boa Viagem", area_m2=70, url="u1"),
        _anuncio(site="B", bairro="Fragoso", area_m2=200, quartos=5, url="u2"),
    ]
    grupos, _ = r.agrupar(itens)
    assert len(grupos) == 2


# ---------------------------------------------------------------------------
# Consolidação
# ---------------------------------------------------------------------------

def test_consolidar_registra_conflito_em_vez_de_silenciar():
    anuncios = [
        _anuncio(site="Viva Real", area_m2=72.0),
        _anuncio(site="Zap Imóveis", area_m2=75.0),
        _anuncio(site="OLX", area_m2=72.0),
    ]
    imovel, conflitos = r.consolidar(anuncios)
    assert imovel["area_m2"] == 72.0        # maioria
    campos = {c["campo"] for c in conflitos}
    assert "area_m2" in campos
    conf = next(c for c in conflitos if c["campo"] == "area_m2")
    assert conf["criterio"] == "maioria"
    assert conf["valores"] == {"Viva Real": 72.0, "Zap Imóveis": 75.0, "OLX": 72.0}


def test_consolidar_sem_divergencia_nao_gera_conflito():
    anuncios = [_anuncio(site="A"), _anuncio(site="B")]
    _, conflitos = r.consolidar(anuncios)
    assert conflitos == []


def test_consolidar_conta_fontes_distintas():
    anuncios = [_anuncio(site="A"), _anuncio(site="B"), _anuncio(site="A")]
    imovel, _ = r.consolidar(anuncios)
    assert imovel["qtd_fontes"] == 2
    assert imovel["sites"] == ["A", "B"]


def test_consolidar_empate_usa_mediana_em_numerico():
    anuncios = [_anuncio(site="A", area_m2=70.0), _anuncio(site="B", area_m2=80.0)]
    imovel, conflitos = r.consolidar(anuncios)
    assert imovel["area_m2"] == 75.0
    assert next(c for c in conflitos if c["campo"] == "area_m2")["criterio"] == "mediana"


def test_consolidar_custo_completo_se_alguma_fonte_informou():
    anuncios = [_anuncio(site="A", custo_completo=False),
                _anuncio(site="B", custo_completo=True)]
    imovel, _ = r.consolidar(anuncios)
    assert imovel["custo_completo"] is True
