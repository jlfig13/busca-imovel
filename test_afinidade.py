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
