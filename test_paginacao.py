# -*- coding: utf-8 -*-
"""Paginação dos portais: seguir o link do site em vez de adivinhar parâmetro.

O código montava a página seguinte como `?pagina={n}`. O OLX pagina por `?o=`
e os portais do Grupo ZAP também ignoram `pagina` nessa posição: os três
devolviam a MESMA primeira página, o scraper via "0 links novos" e concluía
"acabaram os imóveis". Cinco fontes rodaram semanas trazendo só a p1 --
medido nos logs de produção: Viva Real 30/0, Zap 30/0, OLX 49/0.
"""
import scraper_playwright as sp


class _Botao:
    def __init__(self, ativo=True, visivel=True):
        self._a, self._v = ativo, visivel

    def is_enabled(self):
        return self._a

    def is_visible(self):
        return self._v


class _Pagina:
    """Só o que _proxima_pagina usa do objeto do Playwright."""

    def __init__(self, links=None, botoes=None, url="https://x.com/busca"):
        self.links = links or {}
        self.botoes = botoes or {}
        self.url = url

    def eval_on_selector(self, seletor, _js):
        if seletor in self.links:
            return self.links[seletor]
        raise RuntimeError("seletor não encontrado")

    def query_selector(self, seletor):
        return self.botoes.get(seletor)


def test_segue_rel_next():
    pg = _Pagina({'link[rel="next"]': "https://x.com/busca?o=2"})
    acao, alvo, via = sp._proxima_pagina(pg, pg.url)
    assert (acao, alvo) == ("ir", "https://x.com/busca?o=2")
    assert via == 'link[rel="next"]', "o log precisa dizer por onde avançou"


def test_rel_next_tem_prioridade_sobre_o_rotulo():
    """rel=next é contrato; 'Próxima' é convenção de texto."""
    pg = _Pagina({
        'a[aria-label*="óxima" i]': "https://x.com/errado",
        'link[rel="next"]': "https://x.com/certo",
    })
    assert sp._proxima_pagina(pg, pg.url)[:2] == ("ir", "https://x.com/certo")


def test_encontra_pelo_rotulo_com_acento_e_maiuscula():
    pg = _Pagina({'a[aria-label*="óxima" i]': "https://x.com/p2"})
    assert sp._proxima_pagina(pg, pg.url)[:2] == ("ir", "https://x.com/p2")


def test_link_para_a_propria_pagina_e_ultima_pagina():
    """Na última página o portal costuma deixar o link apontando para ela
    mesma. Seguir isso daria um laço buscando o mesmo conteúdo até o teto."""
    pg = _Pagina({'a[rel="next"]': "https://x.com/busca"}, url="https://x.com/busca")
    assert sp._proxima_pagina(pg, pg.url) is None


def test_sem_proxima_devolve_none():
    assert sp._proxima_pagina(_Pagina(), "https://x.com/busca") is None


def test_cai_para_o_botao_quando_a_spa_nao_troca_de_url():
    pg = _Pagina(botoes={'button[aria-label*="óxima" i]': _Botao()})
    assert sp._proxima_pagina(pg, pg.url)[:2] == (
        "clicar", 'button[aria-label*="óxima" i]')


def test_botao_desabilitado_e_fim_da_lista():
    pg = _Pagina(botoes={'button[aria-label*="óxima" i]': _Botao(ativo=False)})
    assert sp._proxima_pagina(pg, pg.url) is None


def test_botao_invisivel_nao_conta():
    pg = _Pagina(botoes={'button[aria-label*="óxima" i]': _Botao(visivel=False)})
    assert sp._proxima_pagina(pg, pg.url) is None


def test_link_vazio_nao_vira_navegacao():
    pg = _Pagina({'a[rel="next"]': None, 'link[rel="next"]': ""})
    assert sp._proxima_pagina(pg, pg.url) is None


def test_erro_no_seletor_nao_derruba_a_busca():
    """query_selector/eval podem levantar em página meio carregada."""
    class Explosiva(_Pagina):
        def query_selector(self, seletor):
            raise RuntimeError("contexto destruído")

    assert sp._proxima_pagina(Explosiva(), "https://x.com/busca") is None


def test_localizador_de_botao_ignora_ancora():
    """O fallback roda justamente quando a âncora existe e não funciona.

    Reusar _proxima_pagina ali devolveria a mesma âncora inútil e o clique
    nunca aconteceria -- foi o que a rodada #53 mostrou, com Zap e Viva Real
    parando na p1 apesar do fallback existir.
    """
    pg = _Pagina(
        links={'a[rel="next"]': "https://x.com/p2"},
        botoes={'button[aria-label*="óxima" i]': _Botao()},
    )
    # a busca normal prefere a âncora...
    assert sp._proxima_pagina(pg, pg.url)[0] == "ir"
    # ...e a busca de botão a ignora
    assert sp._proxima_pagina_botao(pg) == (
        "clicar", 'button[aria-label*="óxima" i]', 'button[aria-label*="óxima" i]')


def test_localizador_de_botao_sem_botao():
    pg = _Pagina(links={'a[rel="next"]': "https://x.com/p2"})
    assert sp._proxima_pagina_botao(pg) is None
