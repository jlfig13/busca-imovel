# -*- coding: utf-8 -*-
"""Testes do dashboard: triagem (favoritos/lixeira) e destaque do que mudou.

Banco e arquivo de saída temporários: gerar_dashboard escreve em
config.ARQUIVO_DASHBOARD e lê a série de preços do banco, e nenhum dos dois
pode ser o versionado.
"""
import os
import tempfile

import pytest

import config


@pytest.fixture
def ambiente(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setattr(config, "ARQUIVO_DB", os.path.join(tmp, "t.db"))
    monkeypatch.setattr(config, "ARQUIVO_DASHBOARD", os.path.join(tmp, "d.html"))
    monkeypatch.setattr(config, "PASTA_SAIDA", tmp)
    import db as _db
    _db.conectar().close()  # cria o schema
    import dashboard as _dash
    return _dash


def _imovel(**extra):
    base = {
        "cidade": "Recife", "bairro": "Pina", "preco": 2000, "quartos": 2,
        "area_m2": 70, "titulo": "Apartamento no Pina", "noRecorte": True,
        "qtd_fontes": 1, "dias_anunciado": 5,
        "anuncios": [{"site": "Fonte A", "url": "https://a.com/1", "preco": 2000,
                      "custo_completo": True}],
    }
    base.update(extra)
    return base


def _html(dash, itens):
    dash.gerar_dashboard(itens, [], [])
    with open(config.ARQUIVO_DASHBOARD, encoding="utf-8") as f:
        return f.read()


def test_queda_traz_valor_e_percentual(ambiente, monkeypatch):
    """R$ 100 em 1.500 é outra conversa que R$ 100 em 2.500: o selo mostra os dois."""
    monkeypatch.setattr(ambiente.db, "obter_serie_precos",
                        lambda urls: {"https://a.com/1": [("2026-08-01", 2500.0),
                                                          ("2026-08-20", 2000.0)]})
    html = _html(ambiente, [_imovel()])
    assert '"queda": 500.0' in html
    assert '"quedaPct": 20' in html


def test_sem_historico_nao_inventa_queda(ambiente, monkeypatch):
    monkeypatch.setattr(ambiente.db, "obter_serie_precos", lambda urls: {})
    html = _html(ambiente, [_imovel()])
    assert '"queda": null' in html
    assert '"quedaPct": null' in html


def test_contagem_dos_chips_nao_vem_fixa_do_python(ambiente):
    """Era interpolada sobre a lista inteira e nunca mudava: com "Minhas
    preferências" ligado, o chip dizia "Novos 4" numa tela com 1."""
    html = _html(ambiente, [_imovel(novo=True), _imovel(noRecorte=False, novo=True)])
    assert 'id="cn-novos"></span>' in html
    assert 'id="cn-quedas"></span>' in html
    assert 'id="cn-multi"></span>' in html


def test_escopos_de_triagem_existem(ambiente):
    html = _html(ambiente, [_imovel()])
    for alvo in ('id="e-favoritos"', 'id="e-lixeira"',
                 'id="n-favoritos"', 'id="n-lixeira"'):
        assert alvo in html


def test_triagem_e_chaveada_por_url_de_anuncio(ambiente):
    """O id do imóvel é reconstruído a cada rodada (db.consolidar_imoveis apaga
    e recria a tabela), então a lista precisa guardar a URL do anúncio."""
    html = _html(ambiente, [_imovel()])
    assert "chavesDe = d => (d.anuncios || []).map(a => a.url)" in html
    assert "lerLista('descartados')" in html
    assert "lerLista('favoritos')" in html


def test_acesso_a_localStorage_e_protegido(ambiente):
    """Em file:// o acesso pode levantar exceção -- e a triagem não pode
    derrubar o render, como já aconteceu com replaceState."""
    html = _html(ambiente, [_imovel()])
    trecho = html[html.index("function lerLista"):html.index("let DESCARTADOS")]
    assert "catch" in trecho
    trecho2 = html[html.index("function gravarLista"):html.index("let DESCARTADOS")]
    assert "catch" in trecho2


def test_pulso_liga_o_filtro(ambiente):
    """O contador dizia "3 baixaram" e não havia como chegar nos três."""
    html = _html(ambiente, [_imovel()])
    assert "acao('Novos hoje', novos, 'novos'" in html
    assert "acao('Baixaram', quedas, 'quedas'" in html
    assert "function ligarChip(nome)" in html


def test_acao_de_descarte_nao_depende_de_hover(ambiente):
    """A funcionalidade não foi encontrada no primeiro uso no celular.

    A causa possível mais séria não era cache: Chrome Android em "versão para
    computador" reporta `hover: hover`, e o botão, que só aparecia no hover
    (com `@media (hover:none)` como escape), ficava invisível para sempre num
    aparelho sem cursor. Agora nasce visível."""
    import design
    css = _css_de(design)
    bloco = css[css.index(".btn-acao{"):css.index(".btn-acao svg{")]
    assert "opacity:1" in bloco, "o botão de ação tem de nascer visível"
    assert ".imovel:hover .btn-acao{opacity" not in css, (
        "revelar a ação no hover devolve o defeito"
    )


def _css_de(design):
    """O CSS mora numa constante de nome variável; acha a que contém .btn-acao."""
    for nome in dir(design):
        v = getattr(design, nome)
        if isinstance(v, str) and ".btn-acao{" in v:
            return v
    raise AssertionError("CSS com .btn-acao não encontrado em design.py")


# ---------------------------------------------------------------------------
# Persistência da triagem
# ---------------------------------------------------------------------------
# O relato foi "marco favorito e na próxima atualização tudo é desfeito".
# Reproduzido: o mecanismo persiste e as URLs são estáveis entre rodadas -- o
# que falhava era o navegador bloqueando dados do site, com a falha engolida
# num catch vazio. Daí estes três: avisar, semear do repositório, e permitir
# backup.

def test_falha_de_armazenamento_nao_e_engolida(ambiente):
    html = _html(ambiente, [_imovel()])
    assert "ARMAZENAMENTO_OK" in html
    assert "pintarAvisoArmazenamento" in html
    assert 'id="aviso-armazenamento"' in html


def test_triagem_ausente_nao_derruba_a_rodada(ambiente, monkeypatch):
    monkeypatch.setattr(config, "ARQUIVO_TRIAGEM", "/nao/existe/triagem.json")
    assert ambiente._ler_triagem() == {"favoritos": {}, "descartados": {}}


def test_triagem_quebrada_nao_derruba_a_rodada(ambiente, monkeypatch, tmp_path):
    """A triagem é conveniência; o catálogo é o produto."""
    arq = tmp_path / "triagem.json"
    arq.write_text("{isto não é json", encoding="utf-8")
    monkeypatch.setattr(config, "ARQUIVO_TRIAGEM", str(arq))
    assert ambiente._ler_triagem() == {"favoritos": {}, "descartados": {}}


def test_triagem_aceita_lista_de_urls(ambiente, monkeypatch, tmp_path):
    """Formato que sai de um copiar-colar apressado."""
    arq = tmp_path / "triagem.json"
    arq.write_text('{"favoritos": ["https://a.com/1"], "descartados": {}}',
                   encoding="utf-8")
    monkeypatch.setattr(config, "ARQUIVO_TRIAGEM", str(arq))
    assert ambiente._ler_triagem()["favoritos"] == {"https://a.com/1": ""}


def test_semente_versionada_vai_para_o_html(ambiente, monkeypatch, tmp_path):
    """É o que sobrevive à limpeza de dados do navegador e à troca de aparelho."""
    arq = tmp_path / "triagem.json"
    arq.write_text('{"favoritos": {"https://a.com/1": "2026-08-22"},'
                   ' "descartados": {}}', encoding="utf-8")
    monkeypatch.setattr(config, "ARQUIVO_TRIAGEM", str(arq))
    html = _html(ambiente, [_imovel()])
    assert '"https://a.com/1": "2026-08-22"' in html
    assert "const SEMENTE" in html
    # união, não substituição: o local soma por cima da semente
    assert "unir(SEMENTE.favoritos" in html


def test_restaurar_backup_nao_apaga_o_que_ja_existe(ambiente):
    """Restaurar num aparelho que já tem marcação não pode zerá-la."""
    html = _html(ambiente, [_imovel()])
    trecho = html[html.index("el('inp-restaurar')"):html.index("/* Liga (ou desliga)")]
    assert "unir(FAVORITOS, dados.favoritos" in trecho
    assert "unir(DESCARTADOS, dados.descartados" in trecho


# ---------------------------------------------------------------------------
# Hora da rodada e carregamento das fotos
# ---------------------------------------------------------------------------

def test_carimbo_traz_hora_e_nao_so_a_data(ambiente):
    """Com 12 rodadas/dia, "05/09" não diz se o dado é de agora ou de 10h."""
    html = _html(ambiente, [_imovel()])
    assert "Atualizado em" in html
    assert "(BRT)" in html
    # duas vezes basta: sob o título (sempre visível) e no rodapé. O pulso
    # é para métrica, e "atualizado" viraria um número grande que não é número.
    assert html.count("05/") >= 1 or "às" in html


def test_carimbo_esta_em_brt_nao_em_utc(ambiente, monkeypatch):
    """O runner roda em UTC e o dashboard é lido no Recife: sem o ajuste, a
    rodada das 08:13 apareceria como 11:13."""
    import dashboard as d
    from datetime import datetime, timezone

    class _Fixo(d.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 5, 11, 13, tzinfo=timezone.utc)

    monkeypatch.setattr(d, "datetime", _Fixo)
    html = _html(ambiente, [_imovel()])
    assert "05/09 às 08:13" in html, "deveria descontar as 3 horas de BRT"


def test_foto_pede_para_nao_mandar_referer(ambiente):
    """Os CDNs dos portais recusam hotlink de outra origem: servido do
    github.io, o card caía no marcador cinza com a URL correta no banco."""
    html = _html(ambiente, [_imovel()])
    assert '<meta name="referrer" content="no-referrer">' in html
    assert 'referrerpolicy="no-referrer"' in html


def test_erro_de_foto_ainda_cai_no_marcador(ambiente):
    """A degradação continua: sem rede, o card tem de seguir legível."""
    html = _html(ambiente, [_imovel()])
    assert "onerror=\"this.closest('.foto').classList.add('sem-foto')\"" in html


# ---------------------------------------------------------------------------
# Preferências no navegador
# ---------------------------------------------------------------------------
# Até 05/09/2026 o recorte era decidido no Python (config.BAIRROS_EXIBIDOS) e
# chegava pronto em cada item como `noRecorte`. Mudar de ideia exigia editar o
# config e esperar a próxima rodada -- e faixa de preço/quartos nem isso
# resolvia, porque estavam cravadas na URL de busca das fontes.

def test_preferencia_padrao_vai_para_o_html(ambiente):
    html = _html(ambiente, [_imovel()])
    assert "const PREFS_PADRAO" in html
    assert '"quartos_min": 2' in html
    assert '"preco_max": 2500' in html


def test_universo_de_bairros_vem_dos_dados_nao_do_config(ambiente):
    """Se viesse do config, ninguém conseguiria escolher um bairro que não
    fosse dos preferidos de quem montou o projeto."""
    html = _html(ambiente, [
        _imovel(cidade="Recife", bairro="Pina"),
        _imovel(cidade="Olinda", bairro="Bairro Novo"),
    ])
    assert "const BAIRROS_POR_CIDADE" in html
    assert '"Pina"' in html
    assert '"Bairro Novo"' in html


def test_recorte_nao_vem_mais_pronto_do_python(ambiente):
    """Duas fontes de verdade para a mesma pergunta é o defeito a evitar."""
    html = _html(ambiente, [_imovel()])
    assert '"noRecorte"' not in html
    assert "function filtrar(" in html


def test_preferencia_e_salva_no_navegador(ambiente):
    html = _html(ambiente, [_imovel()])
    assert "lerLista('preferencias')" in html
    assert "gravarLista('preferencias', PREFS)" in html


def test_campo_ausente_no_imovel_nao_exclui_o_imovel(ambiente):
    """"Não sei a área" não é "área errada" -- mesma regra de três estados do
    filtro de coleta. Vale para área e para bairro."""
    html = _html(ambiente, [_imovel()])
    trecho = html[html.index("function filtrar("):html.index("function ordenar(")]
    for campo in ("d.area != null", "d.bairro &&"):
        assert campo in trecho, f"{campo} precisa ser checado antes de excluir"


# --- a preferência é o filtro, não um recorte paralelo -----------------
# Relato, com print: "o filtro da preferência tem q ser igual a esse. não um
# pré filtrado". A tela dizia "8 imóveis" com 388 no catálogo, e olhando a
# barra de filtros não havia nada explicando de onde vinha o corte -- porque
# não vinha de lá: vinha de um painel separado com campos próprios.

def test_nao_existe_mais_escopo_de_preferencia(ambiente):
    html = _html(ambiente, [_imovel()])
    assert "function atendePrefs" not in html
    assert 'id="e-meus"' not in html
    assert 'id="e-outros"' not in html
    # o painel separado, com campos próprios, foi embora inteiro
    assert 'id="prefs"' not in html
    assert 'id="p-bairros"' not in html


def test_escopos_restantes_sao_de_lista_e_nao_de_filtro(ambiente):
    """Tudo / o que eu marquei / o que eu joguei fora. Filtro mora na barra
    de filtros."""
    html = _html(ambiente, [_imovel()])
    for id_ in ('e-todos', 'e-favoritos', 'e-lixeira'):
        assert f'id="{id_}"' in html


def test_cidade_e_bairro_aceitam_varios_na_propria_barra(ambiente):
    """A seleção múltipla existia só no painel de preferências. Sumir com o
    painel não pode custar a funcionalidade."""
    html = _html(ambiente, [_imovel()])
    assert 'id="lista-cidades"' in html and 'id="lista-bairros"' in html
    assert "let FCidades = [], FBairros = []" in html
    # e o <select> de escolha única foi embora
    assert 'id="f-cidade"' not in html and 'id="f-bairro"' not in html


def test_area_desceu_para_a_barra_de_filtros(ambiente):
    html = _html(ambiente, [_imovel()])
    assert 'id="f-area-min"' in html and 'id="f-area-max"' in html


def test_preferencia_preenche_os_mesmos_campos_da_barra(ambiente):
    """O ponto do relato: a preferência não pode filtrar por fora. Ela só
    escreve nos campos que estão na tela."""
    html = _html(ambiente, [_imovel()])
    trecho = html[html.index("const CAMPOS_PREF = ["):html.index("function estadoDoFiltro")]
    for id_ in ("'f-min'", "'f-max'", "'f-area-min'", "'f-area-max'"):
        assert id_ in trecho


def test_limpar_mostra_tudo(ambiente):
    """Antes a preferência era um escopo e sobrevivia ao Limpar: a tela seguia
    com um punhado de imóveis e o botão parecia quebrado."""
    html = _html(ambiente, [_imovel()])
    trecho = html[html.index("el('btn-limpar').addEventListener"):]
    trecho = trecho[:trecho.index("pintarPulso();")]
    assert "FCidades = []; FBairros = []" in trecho
    assert "inpAreaMin.value = inpAreaMax.value" in trecho


def test_link_compartilhado_ganha_da_preferencia(ambiente):
    """Quem abre um link quer ver o que foi compartilhado; aplicar a
    preferência por cima faria o link mentir."""
    html = _html(ambiente, [_imovel()])
    assert "temFiltroNaUrl" in html
    trecho = html[html.index("const temFiltroNaUrl"):]
    trecho = trecho[:trecho.index("desenharMulti();")]
    assert "aplicarNoFiltro(PREFS)" in trecho


# --- aba de mapa -------------------------------------------------------
# "gostaria de que tivesse uma aba de mapa onde a busca e visualização seja
# pelo mapa", com a decisão de manter o dashboard offline (SVG no arquivo,
# sem tiles).

def _com_geo(monkeypatch, cache):
    import geo
    monkeypatch.setattr(geo, "carregar", lambda: cache)


def _quadrado(lon, lat, r=0.004):
    return [[lon - r, lat - r], [lon + r, lat - r],
            [lon + r, lat + r], [lon - r, lat + r], [lon - r, lat - r]]


def test_aba_de_mapa_existe(ambiente, monkeypatch):
    _com_geo(monkeypatch, {})
    html = _html(ambiente, [_imovel()])
    assert 'id="aba-mapa"' in html and 'id="painel-mapa"' in html


def test_sem_contornos_o_mapa_explica_em_vez_de_ficar_branco(ambiente, monkeypatch):
    _com_geo(monkeypatch, {})
    html = _html(ambiente, [_imovel()])
    assert "mapa-vazio" in html
    assert "geo/bairros.json" in html
    assert 'class="mapa-bairro"' not in html


def test_bairro_com_contorno_vira_path(ambiente, monkeypatch):
    _com_geo(monkeypatch, {"Recife|Pina": {"anel": _quadrado(-34.885, -8.095)}})
    html = _html(ambiente, [_imovel()])
    assert 'data-b="Recife|Pina"' in html


def test_bairro_sem_anuncio_nesta_rodada_nao_e_desenhado(ambiente, monkeypatch):
    """O cache ACUMULA entre rodadas. Desenhar tudo que já foi buscado
    encheria a tela de polígono cinza e faria a região parecer vazia quando o
    vazio é do recorte, não da cidade."""
    _com_geo(monkeypatch, {
        "Recife|Pina": {"anel": _quadrado(-34.885, -8.095)},
        "Recife|Ipsep": {"anel": _quadrado(-34.930, -8.110)},
    })
    html = _html(ambiente, [_imovel()])   # só Pina
    assert 'data-b="Recife|Pina"' in html
    assert 'data-b="Recife|Ipsep"' not in html


def test_atribuicao_do_openstreetmap_acompanha_a_geometria(ambiente, monkeypatch):
    """ODbL exige crédito de quem redistribui. Não é formalidade: é a mesma
    postura que fez o projeto respeitar robots.txt."""
    _com_geo(monkeypatch, {"Recife|Pina": {"anel": _quadrado(-34.885, -8.095)}})
    html = _html(ambiente, [_imovel()])
    assert "openstreetmap.org/copyright" in html
    assert "ODbL" in html


def test_mapa_nao_carrega_nada_de_fora(ambiente, monkeypatch):
    """O invariante do projeto: um arquivo só, sem servidor. Tile é requisição
    em tempo de execução e cairia junto com a rede."""
    _com_geo(monkeypatch, {"Recife|Pina": {"anel": _quadrado(-34.885, -8.095)}})
    html = _html(ambiente, [_imovel()])
    for proibido in ("leaflet", "tile.openstreetmap", "unpkg.com", "cdn."):
        assert proibido not in html.lower()


def test_mapa_pinta_ignorando_cidade_e_bairro(ambiente, monkeypatch):
    """O mapa É o seletor de bairro: pintar só o bairro já escolhido tornaria
    a comparação impossível, porque todo o resto viraria cinza no instante da
    escolha. O resto do recorte (preço, quartos, área) continua valendo."""
    _com_geo(monkeypatch, {"Recife|Pina": {"anel": _quadrado(-34.885, -8.095)}})
    html = _html(ambiente, [_imovel()])
    assert "porBairro(filtrar({semLocal: true}))" in html


def test_ir_para_o_bairro_acrescenta_em_vez_de_substituir(ambiente, monkeypatch):
    """No mapa a pessoa compara bairros vizinhos; tocar no segundo apagando o
    primeiro tiraria justamente o que a seleção múltipla veio permitir."""
    _com_geo(monkeypatch, {"Recife|Pina": {"anel": _quadrado(-34.885, -8.095)}})
    html = _html(ambiente, [_imovel()])
    trecho = html[html.index("el('mapa-ir').addEventListener"):]
    trecho = trecho[:trecho.index("mostrarAba('imoveis')")]
    assert "FBairros.push(bai)" in trecho
    assert "FCidades.push(cid)" in trecho
