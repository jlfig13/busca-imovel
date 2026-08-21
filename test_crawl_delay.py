# -*- coding: utf-8 -*-
"""Crawl-delay: a diretiva lida tem que virar espera de verdade.

Antes destes testes o robots.py extraía o valor, gravava no banco e ninguém
esperava nada -- inclusive num site que o config diz explicitamente que "pede
Crawl-delay: 5, o que precisa ser respeitado".
"""
import threading
import time

import utils


def _limpar():
    with utils._trava_atraso:
        utils._atraso_por_dominio.clear()
        utils._ultimo_acesso.clear()


def test_sem_diretiva_nao_espera():
    _limpar()
    inicio = time.monotonic()
    assert utils.aguardar_vez("https://exemplo.com/lista") == 0.0
    assert time.monotonic() - inicio < 0.1


def test_primeiro_acesso_nao_espera_o_segundo_sim():
    _limpar()
    utils.registrar_crawl_delay("https://exemplo.com/lista", 0.3)
    assert utils.aguardar_vez("https://exemplo.com/lista") == 0.0
    espera = utils.aguardar_vez("https://exemplo.com/p2")
    assert 0.2 < espera <= 0.35


def test_espera_e_por_dominio_nao_por_fonte():
    """Zap Recife e Zap Olinda são duas fontes no mesmo servidor."""
    _limpar()
    utils.registrar_crawl_delay("https://exemplo.com/recife", 0.3)
    utils.aguardar_vez("https://exemplo.com/recife")
    assert utils.aguardar_vez("https://exemplo.com/olinda") > 0.2
    # domínio diferente não herda a espera
    assert utils.aguardar_vez("https://outro.com/lista") == 0.0


def test_maior_diretiva_vence():
    _limpar()
    utils.registrar_crawl_delay("https://exemplo.com/a", 1)
    utils.registrar_crawl_delay("https://exemplo.com/b", 5)
    utils.registrar_crawl_delay("https://exemplo.com/c", 2)
    assert utils._atraso_por_dominio["exemplo.com"] == 5.0


def test_valor_absurdo_cai_no_teto():
    _limpar()
    utils.registrar_crawl_delay("https://exemplo.com/a", 3600)
    assert utils._atraso_por_dominio["exemplo.com"] == utils.ATRASO_MAXIMO


def test_valor_invalido_e_ignorado():
    _limpar()
    for ruim in (None, "", "abc", 0, -5):
        utils.registrar_crawl_delay("https://exemplo.com/a", ruim)
    assert "exemplo.com" not in utils._atraso_por_dominio


def test_workers_concorrentes_nao_saem_juntos():
    """Dois workers no mesmo domínio têm que se enfileirar, não sincronizar.

    Se a marca de último acesso fosse gravada depois do sleep, os dois leriam
    a mesma marca velha e bateriam no servidor no mesmo instante."""
    _limpar()
    utils.registrar_crawl_delay("https://exemplo.com/x", 0.3)
    utils.aguardar_vez("https://exemplo.com/x")  # consome o primeiro slot
    saidas = []

    def bater():
        utils.aguardar_vez("https://exemplo.com/x")
        saidas.append(time.monotonic())

    ts = [threading.Thread(target=bater) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert abs(saidas[1] - saidas[0]) > 0.2
