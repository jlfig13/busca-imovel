# -*- coding: utf-8 -*-
"""Testes da nota de afinidade (config.PERFIL)."""
import afinidade
import config


def _imovel(**kw):
    base = {"preco": 2000.0, "precoM2": 25.0, "bairro": "Boa Vista",
            "quartos": 3, "custoCompleto": True, "qtdFontes": 1,
            "novo": False, "queda": None}
    base.update(kw)
    return base


def test_mais_barato_ganha_do_mais_caro():
    barato = _imovel(preco=1500.0)
    caro = _imovel(preco=2500.0)
    afinidade.pontuar([barato, caro])
    assert barato["score"] > caro["score"]


def test_bairro_preferido_pesa():
    preferido = _imovel(bairro=config.PERFIL["bairros_preferidos"][0])
    outro = _imovel(bairro="Boa Vista")
    afinidade.pontuar([preferido, outro])
    assert preferido["score"] > outro["score"]
    assert any("bairro preferido" in m for m in preferido["motivos"])


def test_menos_quartos_fica_atras_mesmo_sendo_barato():
    """O requisito obriga: 2 quartos vai atrás de QUALQUER 3 quartos.

    Só descontar a nota não bastava -- um 2 quartos barato e espaçoso
    marcava 38 contra 16 de um 3 quartos caro, e o "obrigatório" não
    obrigava nada. Quem ordena usa `atende` como primeira chave."""
    dois = _imovel(quartos=2, preco=1500.0, precoM2=15.0)
    tres = _imovel(quartos=3, preco=2400.0, precoM2=30.0)
    afinidade.pontuar([dois, tres])
    assert dois["atende"] is False and tres["atende"] is True
    assert dois["melhor"] is False
    assert "score" in dois          # continua na lista, com nota


def test_dado_ausente_nao_vira_nota_media():
    """Anúncio sem área não pode subir por não ter sido preenchido."""
    bom = _imovel(precoM2=10.0)
    ruim = _imovel(precoM2=40.0)
    sem_area = _imovel(precoM2=None)
    afinidade.pontuar([bom, ruim, sem_area])
    assert bom["score"] > sem_area["score"]
    # sem área, o critério de espaço simplesmente não conta -- nem a favor
    # nem contra: o item não recebe o ponto que o melhor recebeu
    assert sem_area["score"] < bom["score"]


def test_selo_vai_para_os_melhores_e_no_maximo_tres():
    imoveis = [_imovel(preco=1500.0 + n * 100, precoM2=10.0 + n,
                       bairro=config.PERFIL["bairros_preferidos"][0])
               for n in range(8)]
    afinidade.pontuar(imoveis)
    marcados = [i for i in imoveis if i["melhor"]]
    assert 0 < len(marcados) <= afinidade.DESTAQUES
    assert max(i["score"] for i in imoveis) == marcados[0]["score"]


def test_lista_vazia_nao_explode():
    assert afinidade.pontuar([]) == []


def test_selo_so_sai_em_bairro_preferido():
    """Barato fora da lista não vira recomendação.

    Sem esta regra a sugestão apontava Arruda e Bairro Novo: a nota media
    preço e área, e um imóvel barato o bastante vencia a localização — que
    era justamente o ponto."""
    barato_fora = _imovel(bairro="Arruda", preco=1450.0, precoM2=10.0)
    caro_dentro = _imovel(bairro="Graças", preco=2400.0, precoM2=30.0)
    afinidade.pontuar([barato_fora, caro_dentro])
    assert barato_fora["score"] > caro_dentro["score"]   # continua bem posto
    assert barato_fora["melhor"] is False                # mas sem selo
    assert barato_fora["motivos"]                        # e com as tags de mérito


def test_sem_bairro_preferido_na_lista_ninguem_ganha_selo():
    """Nenhum imóvel nos bairros certos: nenhuma sugestão, não a segunda melhor."""
    fora = [_imovel(bairro="Arruda", preco=1500.0 + n) for n in range(4)]
    afinidade.pontuar(fora)
    assert not any(i["melhor"] for i in fora)


def test_melhores_do_bairro_preferido_ganham_selo_mesmo_em_rodada_fraca():
    """Dentro da lista curta, o melhor do dia é o que se quer ver.

    Somar piso de nota à restrição de bairro deixava a tela sem sugestão
    nenhuma: medido, os melhores em bairro preferido marcavam 40 e 34
    contra um piso de 45."""
    preferidos = [_imovel(bairro=b, preco=2300.0 + n * 50, precoM2=28.0 + n)
                  for n, b in enumerate(("Graças", "Aflitos", "Rosarinho"))]
    baratos_fora = [_imovel(bairro="Arruda", preco=1400.0, precoM2=12.0)
                    for _ in range(3)]
    afinidade.pontuar(preferidos + baratos_fora)
    assert [i["melhor"] for i in preferidos] == [True, True, True]
    assert not any(i["melhor"] for i in baratos_fora)
