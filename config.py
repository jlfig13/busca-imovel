# -*- coding: utf-8 -*-
"""
Configurações do Monitor de Apartamentos.
Edite os valores abaixo conforme sua busca.
"""

import os
import re

# ---------------------------------------------------------------------------
# FILTROS DE BUSCA
# ---------------------------------------------------------------------------
# ENVELOPE DE COLETA -- o que ENTRA no banco. Não confundir com preferência:
# o dashboard filtra livremente dentro deste envelope, e nada fora dele pode
# ser exibido, porque nunca foi coletado.
#
# Até 05/09/2026 os dois eram a mesma coisa, e a faixa 1.500-2.500 estava
# cravada na URL de busca de seis fontes. Consequência: quem quisesse ver um
# apartamento de R$ 1.200 no dashboard não conseguia, e nenhum trabalho de
# interface resolveria -- o anúncio nunca tinha sido coletado.
#
# O envelope é largo de propósito e mais caro de propósito: cada ponto a mais
# de largura é anúncio a mais por rodada, banco maior (commitado 12x/dia) e
# rodada mais longa. É o preço de "escolha livre" ser verdade.
FILTROS = {
    # piso 800: abaixo disso, em Recife, o anúncio de apartamento é quase
    # sempre quarto, vaga de garagem ou erro de digitação.
    "preco_min": 800,
    "preco_max": 6000,
}

# quartos_min/area_min variam por cidade -- Olinda tem exigência maior
# (imóvel menor lá compensa menos que em Recife). Cidade de um imóvel vem
# do campo "cidade" do site em config.SITES, ou detectada no próprio card
# (ex: OLX busca a região metropolitana inteira e mistura Recife/Olinda/
# Jaboatão num resultado só).
#
# Estar aqui é o que AUTORIZA a cidade a entrar no catálogo: quem manda no
# recorte geográfico é este dicionário (ver CIDADES_MONITORADAS abaixo).
# Antes de 05/09/2026 não havia recorte nenhum, e cidade sem entrada caía no
# perfil de Recife -- foi assim que anúncio de Caruaru entrou na lista.
# Perfil de COLETA por cidade. Vale como piso do envelope, não como
# preferência: quem decide quartos e área é quem está olhando, no dashboard.
FILTROS_POR_CIDADE = {
    "Recife": {"quartos_min": 1, "area_min": 30},
    "Olinda": {"quartos_min": 1, "area_min": 30},
}

# Demais cidades da Região Metropolitana do Recife. Entram com o perfil de
# Recife como ponto de partida -- não há motivo medido para exigir diferente
# delas, e um perfil frouxo demais aparece no dashboard, onde dá para julgar.
# Ficam FORA do recorte de bairros (BAIRROS_EXIBIDOS não tem entrada para
# elas), então caem em "Outros bairros" em vez de disputar a lista do dia.
for _cidade_rmr in (
    "Jaboatão dos Guararapes", "Paulista", "Camaragibe", "Igarassu",
    "Ipojuca", "Cabo de Santo Agostinho", "Abreu e Lima",
    "São Lourenço da Mata", "Moreno",
):
    FILTROS_POR_CIDADE.setdefault(_cidade_rmr, dict(FILTROS_POR_CIDADE["Recife"]))
del _cidade_rmr

FILTRO_PADRAO = FILTROS_POR_CIDADE["Recife"]

# Cidades que o projeto monitora. Derivado de FILTROS_POR_CIDADE de propósito:
# cidade sem perfil declarado não tem como ser avaliada, então não pode entrar.
#
# Existe porque o filtro não tinha recorte geográfico nenhum: a busca do OLX
# devolve muito além da região metropolitana (Caruaru, Garanhuns, Gravatá
# apareceram), e qualquer cidade caía no FILTRO_PADRAO e podia ser aprovada.
# Anúncio de Garanhuns num monitor de Recife não é ruído: é resposta errada.
#
# O recorte hoje é Recife, Olinda e a Região Metropolitana. Para incluir outra
# cidade, basta dar a ela um perfil em FILTROS_POR_CIDADE: os dois andam
# juntos de propósito, porque avaliar sem perfil é o que causava o problema.
CIDADES_MONITORADAS = tuple(FILTROS_POR_CIDADE)

# ---------------------------------------------------------------------------
# BAIRROS EXIBIDOS
# ---------------------------------------------------------------------------
# A COLETA continua na cidade inteira -- é ela que alimenta o histórico de
# preço e a detecção de imóvel repetido entre portais. Esta lista é a
# PREFERÊNCIA INICIAL de bairros: o valor com que o dashboard abre para quem
# nunca mexeu nos controles. A partir de 05/09/2026 quem manda é a preferência
# salva no navegador; isto aqui é só a semente.
#
# Separar as duas coisas é de propósito. Filtrar na coleta faria o banco
# perder a série de um imóvel assim que a lista mudasse, e mudar de ideia
# sobre um bairro exigiria recomeçar o histórico dele do zero.
#
# Cidade que não aparece aqui não é exibida (o OLX busca a região
# metropolitana inteira e traz Jaboatão junto). Bairro vazio também não:
# sem o dado não dá para afirmar que o imóvel está na lista.
BAIRROS_EXIBIDOS = {
    "Recife": [
        # centro expandido
        "Recife Antigo", "Boa Vista", "Ilha do Leite", "Paissandu",
        "Santo Amaro", "Derby", "Santana",
        # eixo norte
        "Arruda", "Campo Grande", "Encruzilhada", "Hipódromo", "Rosarinho",
        "Torreão",
        # zona norte / Casa Forte e arredores
        "Aflitos", "Apipucos", "Casa Amarela", "Casa Forte", "Espinheiro",
        "Graças", "Jaqueira", "Monteiro", "Parnamirim", "Poço da Panela",
        "Tamarineira", "Torre",
    ],
    "Olinda": ["Casa Caiada", "Bairro Novo"],
}

# ---------------------------------------------------------------------------
# PERFIL DE ESCOLHA (nota de afinidade)
# ---------------------------------------------------------------------------
# O filtro responde "cabe?". Este perfil responde "é o melhor?" -- e é o que
# faz o dashboard colocar sugestão no topo em vez de despejar 19 anúncios
# equivalentes. Respondido pelo usuário em 19/08/2026:
#
#   - pesam junto: custo mensal baixo, área pelo preço e bairro certo;
#   - menos de 3 quartos derruba a nota (não esconde: um 2 quartos grande e
#     barato ainda merece ser visto, só não na frente);
#   - o resultado aparece como selo "Melhor achado" nos três primeiros.
#
# Mexer aqui muda a recomendação, não a coleta.
PERFIL = {
    # O selo "Melhor achado" SÓ sai nestes bairros. Fora deles o imóvel
    # continua na lista, com as mesmas tags de mérito ("entre os mais
    # baratos", "melhor área pelo preço") -- o que não acontece é ser
    # recomendado. Sem essa restrição a sugestão apontava Arruda e Bairro
    # Novo, que são bairros exibidos mas não são onde o casal quer morar:
    # a nota media preço e área, e barato o bastante vencia qualquer coisa.
    "bairros_preferidos": [
        "Casa Amarela", "Casa Forte", "Graças", "Espinheiro", "Aflitos",
        "Jaqueira", "Encruzilhada", "Torreão", "Rosarinho", "Campo Grande",
    ],
    # Restringe o SELO, não a lista: ver PERFIL["bairros_preferidos"].
    "destaque_so_em_preferidos": True,
    "quartos_min_desejado": 3,
}

# Idade máxima aceita quando a fonte declara a data de atualização.
# O Portal CRECI carimba "Atualizado em: dd/mm/aaaa" em cada card e boa parte
# do inventário está parada há meses -- imóvel de aluguel anunciado há muito
# tempo quase sempre já foi alugado sem ninguém baixar o anúncio.
# Fonte que não declara data não é afetada: ausência de carimbo não é prova
# de anúncio velho.
MAX_DIAS_DESDE_ATUALIZACAO = 30

# ---------------------------------------------------------------------------
# PREFERÊNCIAS PADRÃO (apresentação)
# ---------------------------------------------------------------------------
# Com o que o dashboard abre para quem nunca mexeu nos controles. Daí em
# diante quem manda é o que a pessoa salvou no navegador.
#
# São exatamente os valores que até 05/09/2026 estavam cravados na coleta --
# viraram ponto de partida em vez de teto. Quem quiser 1 quarto ou R$ 4.000
# agora muda na tela, e o dado já está no banco.
#
# Simplificação assumida: quartos e área passam a ser globais, não por cidade.
# Antes Olinda exigia 3+/70m² e Recife 2+/60m². Manter dois perfis obrigaria a
# uma interface de perfil por cidade para uma diferença que quem está olhando
# resolve em dois toques.
PREFERENCIAS_PADRAO = {
    "preco_min": 1500,
    "preco_max": 2500,
    "quartos_min": 2,
    "area_min": 60,
    "area_max": None,
    "cidades": ["Recife", "Olinda"],
    "bairros": sorted({b for lista in BAIRROS_EXIBIDOS.values() for b in lista}),
}

# ---------------------------------------------------------------------------
# ARQUIVOS DE SAÍDA
# ---------------------------------------------------------------------------
PASTA_SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")
ARQUIVO_EXCEL = os.path.join(PASTA_SAIDA, "apartamentos.xlsx")
ARQUIVO_DB = os.path.join(PASTA_SAIDA, "apartamentos.db")
ARQUIVO_DASHBOARD = os.path.join(PASTA_SAIDA, "dashboard.html")
ARQUIVO_LOG = os.path.join(PASTA_SAIDA, "scraper.log")

# Triagem (favoritos e descartes) versionada. Fica na RAIZ, não em saida/: é
# entrada escrita por gente, não artefato de rodada, e o dashboard só a lê.
# É o que sobrevive a troca de aparelho e a limpeza de dados do navegador --
# o localStorage some com qualquer um dos dois.
ARQUIVO_TRIAGEM = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "triagem.json")

# Removido em 21/08/2026: a integração opcional com um serviço de "web
# unlocker" comercial, cuja função declarada era contornar Cloudflare/DataDome.
# Nunca chegou a ser ligada (as duas variáveis viviam vazias e nenhum scraper
# pedia o caminho), mas manter no código um contorno explícito de controle
# técnico de acesso é incoerente com o resto do projeto, que decide o que
# raspar pelo robots.txt e desativa fonte que proíbe. Se um portal protegido
# parar de funcionar, a resposta é desativar a fonte no config -- não furar a
# proteção.

# ---------------------------------------------------------------------------
# SITES MONITORADOS
# ---------------------------------------------------------------------------
# tipo:
#   "html_estatico" -> listagem vem pronta no HTML (requests + BeautifulSoup)
#   "playwright" -> listagem via JS e/ou portal grande (Chromium headless)
#   "cards_inline" -> listagem estática com preço perto do link
#   "revisar" -> site carrega listagem via JavaScript; ainda não mapeado, ver README
SITES = [
    {
        "nome": "Luiza Parizi Imóveis",
        "tipo": "html_estatico",
        "template": "pratica_internet",
        "url_listagem": "https://www.luizapariziimoveis.com.br/aluguel/apartamento/pe/recife",
        "base_url": "https://www.luizapariziimoveis.com.br",
    },
    {
        # ESTREITAMENTO CONHECIDO: "2-quartos" faz parte do CAMINHO da busca,
        # não é query string. Trocar por "todos" arrisca 404 e não foi
        # verificado ao vivo, então esta fonte segue coletando só 2+ quartos
        # enquanto as outras já vêm no envelope largo. Vale conferir a rota de
        # "todos os quartos" no site e trocar aqui.
        "nome": "CTI Imobiliária",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.ctiimobiliaria.com.br/aluguel/apartamento/recife/"
            "todos-os-bairros/todos-os-condominios/todas-as-opcoes/2-quartos"
            "?ordenacao=dataatualizacaodesc"
        ),
        "base_url": "https://www.ctiimobiliaria.com.br",
        "cidade": "Recife",
        # "/imovel/" sozinho também casa com "/venda/imovel/.../" -- links de
        # sugestão de busca relacionada no rodapé, não anúncios de verdade.
        # Confirmado ao vivo: anúncios reais usam sempre esse prefixo mais
        # específico.
        "seletor_href": "/imovel/apartamento-para-alugar-",
        "max_paginas": 3,
        # O card mostra só o aluguel. A página do imóvel traz "Valor /
        # Condomínio / IPTU / Total" -- e a diferença é enorme: um anúncio
        # de R$ 1.850 no card custa R$ 2.997 por mês (condomínio de R$ 953).
        # Sem esta visita, ele entrava no dashboard como se coubesse no teto.
        "custo_no_detalhe": True,
    },
    {
        "nome": "Âncora Imobiliária",
        "tipo": "cards_inline",
        "template": "rocketimob",
        "url_listagem": "https://ancoraimobiliaria.com.br/aluguel/residencial_comercial/recife/",
        "base_url": "https://ancoraimobiliaria.com.br",
        "padrao_link_imovel": "/imovel/",
    },
    {
        "nome": "Abasol Imóveis",
        "tipo": "revisar",
        "template": "kenlo",
        "url_listagem": "https://www.abasol.com.br/imoveis/para-alugar/apartamento",
        "base_url": "https://www.abasol.com.br",
        "padrao_link_imovel": "/imovel/",
        "max_paginas": 20,
        "obs": (
            "DESATIVADO em 19/08/2026 -- robots.txt PROÍBE. Plataforma Kenlo, "
            "cujo robots.txt padrão traz allowlist nomeada (Googlebot, bingbot, "
            "Claude-User etc.) e fecha o resto com 'User-agent: * / Disallow: /'. "
            "Um scraper próprio cai no '*'. Mesma situação do Harry Fernandes, "
            "e a mesma decisão: é política do site, não dificuldade técnica. "
            "Detectado pelo checador automático (robots.py), que passou a rodar "
            "a cada rodada -- antes ninguém tinha conferido. "
            "Alternativa: pedir autorização por escrito à imobiliária."
        ),

    },
    {
        "nome": "Belchior Alvarez Corretor",
        "tipo": "html_estatico",
        "template": "tecimob",
        "url_listagem": (
            "https://belchioralvarezcorretor.com.br/alugar/apartamento/"
            "recife-pe+recife-pe-barro+recife-pe-jardim-sao-paulo+recife-pe-sancho"
            "+jaboatao-dos-guararapes-pe-santana"
            "?by_type_slug=apartamento&sort=-created_at%2Cid&offset=1&limit=21"
            "&typeArea=private_area&floorComparision=equals"
        ),
        "base_url": "https://belchioralvarezcorretor.com.br",
    },
    {
        "nome": "Camila Melo Imóveis",
        "tipo": "cards_inline",
        "template": "imopro",
        "url_listagem": "https://camilameloimoveis.com.br/busca?orst=dta&topr=2",
        "base_url": "https://camilameloimoveis.com.br",
        "padrao_link_imovel": "/imovel/",
    },
    {
        "nome": "Moradasol Imobiliária",
        "tipo": "revisar",
        "template": "kenlo",
        "url_listagem": "https://www.moradasol.com.br/imoveis/para-alugar/apartamento/recife",
        "base_url": "https://www.moradasol.com.br",
        "padrao_link_imovel": "/imovel/",
        "obs": (
            "DESATIVADO em 19/08/2026 -- robots.txt PROÍBE. Plataforma Kenlo, "
            "cujo robots.txt padrão traz allowlist nomeada (Googlebot, bingbot, "
            "Claude-User etc.) e fecha o resto com 'User-agent: * / Disallow: /'. "
            "Um scraper próprio cai no '*'. Mesma situação do Harry Fernandes, "
            "e a mesma decisão: é política do site, não dificuldade técnica. "
            "Detectado pelo checador automático (robots.py), que passou a rodar "
            "a cada rodada -- antes ninguém tinha conferido. "
            "Alternativa: pedir autorização por escrito à imobiliária."
        ),

    },
    {
        "nome": "Rede Imóveis Pernambuco",
        "tipo": "revisar",
        "template": "kenlo",
        "url_listagem": "https://www.redeimoveispe.com.br/imoveis/para-alugar/apartamento/recife",
        "base_url": "https://www.redeimoveispe.com.br",
        "padrao_link_imovel": "/imovel/",
        "obs": (
            "DESATIVADO em 19/08/2026 -- robots.txt PROÍBE. Plataforma Kenlo, "
            "cujo robots.txt padrão traz allowlist nomeada (Googlebot, bingbot, "
            "Claude-User etc.) e fecha o resto com 'User-agent: * / Disallow: /'. "
            "Um scraper próprio cai no '*'. Mesma situação do Harry Fernandes, "
            "e a mesma decisão: é política do site, não dificuldade técnica. "
            "Detectado pelo checador automático (robots.py), que passou a rodar "
            "a cada rodada -- antes ninguém tinha conferido. "
            "Alternativa: pedir autorização por escrito à imobiliária."
        ),

    },
    {
        "nome": "Sérgio Rodrigues Corretor",
        "tipo": "cards_inline",
        "template": "voa_corretor",
        "url_listagem": "https://www.santoscorretorpe.com.br/imoveis/para-alugar/",
        "base_url": "https://www.santoscorretorpe.com.br",
        "padrao_link_imovel": "/imovel/",
        "obs": "Recife e Jaboatão dos Guararapes. Inventário pequeno (poucos imóveis por vez), mas site ativo.",
    },
    {
        "nome": "Nogueira Corretores",
        "tipo": "revisar",
        "url_listagem": "https://www.nogueiracorretores.com.br/",
        "base_url": "https://www.nogueiracorretores.com.br",
        "obs": (
            "CORREÇÃO (verificado em 18/08/2026): a nota anterior dizia que o "
            "robots.txt proíbe acesso automatizado. Isso está errado -- o site "
            "NÃO tem robots.txt (/robots.txt devolve a própria home). O motivo "
            "real de não estar mapeado é outro: o domínio não respondeu na "
            "verificação (HTTP 000) e serve o mesmo HTML de Paulo Miranda "
            "(mesmo container GTM), indicando SPA com catch-all. "
            "Falta descobrir a rota real de listagem de locação."
        ),
    },
    {
        "nome": "Josinildo Imóveis",
        "tipo": "playwright",
        "url_listagem": (
            "https://josinildoimoveis.com.br/alugar/imoveis/recife-pe"
            "?sort=-created_at%2Cid&offset=1&limit=21"
            "&typeArea=total_area&floorComparision=equals"
        ),
        "base_url": "https://josinildoimoveis.com.br",
        "seletor_href": "/imovel/",
        "max_paginas": 1,
    },
    {
        "nome": "Rogério Corretor",
        "tipo": "cards_inline",
        "template": "imobzi",
        "url_listagem": "https://www.rogeriocorretor.com/buscar?availability=rent&order=neighborhood&search_type=properties_map",
        "base_url": "https://www.rogeriocorretor.com",
        "padrao_link_imovel": "/imovel/",
    },
    {
        "nome": "Newville",
        "tipo": "cards_inline",
        "url_listagem": "https://newville.com.br/imoveis?finalidade=Locacao&tipo=Apartamento",
        "base_url": "https://newville.com.br",
        "padrao_link_imovel": "/imovel/",
        "max_paginas": 1,
    },
    {
        "nome": "Paulo Miranda Imóveis",
        "tipo": "revisar",
        "url_listagem": "https://www.paulomiranda.com.br/",
        "base_url": "https://www.paulomiranda.com.br",
        "obs": (
            "CORREÇÃO (verificado em 18/08/2026): a nota anterior dizia que o "
            "robots.txt proíbe acesso automatizado. Isso está errado -- o site "
            "NÃO tem robots.txt (/robots.txt devolve HTTP 404 com o HTML da home). "
            "Não há restrição declarada. O bloqueio real é técnico: é uma SPA com "
            "catch-all -- /alugar, /imoveis?finalidade=locacao e /busca?transacao=alugar "
            "devolvem os mesmos 41.221 bytes da home, então a listagem só existe "
            "depois do JS rodar. Precisa de Playwright + a rota real de locação "
            "(abrir o site, fazer a busca e copiar a URL resultante)."
        ),
    },
    # -----------------------------------------------------------------------
    # Fontes adicionadas em 18/08/2026 -- todas com robots.txt conferido na
    # inclusão. As marcadas "revisar" têm o achado concreto registrado no
    # campo "obs" (não são "não olhei", são "olhei e falta X").
    # -----------------------------------------------------------------------
    {
        # Portal do Conselho Regional de Corretores de Imóveis: só anuncia
        # quem tem CRECI ativo e está adimplente -- é a fonte com menor risco
        # de anúncio irregular. robots.txt: "User-agent: * / Disallow:"
        # (vazio = libera tudo).
        #
        # A rota é /Busca/{finalidade}/{tipo}/{cidade}/{uf}/{cidadeId}/{bairroId}/{activeSearchId}/
        # O último segmento (activeSearchId) é o que realmente seleciona a
        # cidade -- slug e demais ids são cosméticos (testado: trocar só o
        # slug para "olinda" continua devolvendo Recife).
        #
        # Paginação por ?page=N funciona sem o parâmetro "f=" da URL original
        # (que é só um JSON base64 com os filtros da busca). Sem "f=" a
        # listagem vem sem teto de preço -- o filtro local de config.FILTROS
        # corta o que passar de 2500.
        #
        # Validado ao vivo: HTML servido pelo servidor (204 KB), 10 anúncios
        # por página, preço/quartos/área extraídos corretamente pelo
        # scraper_cards_inline.
        "nome": "Portal CRECI Brasil",
        "tipo": "cards_inline",
        "url_listagem": (
            "https://www.portalcreci.org.br/Busca/Alugar/Apartamento/"
            "recife/17/608/0/13371/"
        ),
        "base_url": "https://www.portalcreci.org.br",
        "padrao_link_imovel": "/Anuncio/Index/",
        "padrao_paginacao": "?page={n}",
        "cidade": "Recife",
        "max_paginas": 10,
    },
    {
        "nome": "Portal CRECI Brasil Olinda",
        "tipo": "revisar",
        "url_listagem": "https://www.portalcreci.org.br/",
        "base_url": "https://www.portalcreci.org.br",
        "obs": (
            "Mesma fonte da entrada acima, faltando só a URL de Olinda. O "
            "activeSearchId (último segmento do path) é o que seleciona a "
            "cidade e não é derivável de fora: varrer a faixa 13360-13395 "
            "devolveu Recife em todos os ids, e o endpoint de autocomplete "
            "que gera esse id não foi localizado. "
            "COMO RESOLVER (1 minuto): abrir portalcreci.org.br, buscar "
            "'OLINDA - PE' + Apartamento + Alugar, e copiar a URL do "
            "resultado para cá com tipo 'cards_inline', "
            "padrao_link_imovel '/Anuncio/Index/' e padrao_paginacao '?page={n}'."
        ),
    },
    {
        # Imobiliária de Olinda (Casa Caiada), foco em Olinda e Paulista.
        # robots.txt: "User-Agent: * / Allow: /".
        #
        # padrao_link_imovel usa "-locacao-" em vez de "/imovel/" de
        # propósito: "/imovel/" também casa com os links de filtro do menu
        # (/imovel/?finalidade=venda&tipo=casa), que viram cards vazios --
        # e card vazio hoje PASSA no filtro (ver P-01 da auditoria). O slug
        # dos anúncios reais é sempre .../imovel/<id>/apartamento-locacao-olinda-pe-<bairro>-<edificio>
        # Validado ao vivo: preço e área extraídos; o site não expõe quartos
        # no card da listagem.
        "nome": "Cristina Mirele Imóveis",
        "tipo": "cards_inline",
        "url_listagem": "https://www.cristinamireleimoveis.com.br/imovel/?finalidade=locacao&tipo=apartamento",
        "base_url": "https://www.cristinamireleimoveis.com.br",
        "padrao_link_imovel": "-locacao-",
        "cidade": "Olinda",
        "max_paginas": 5,
    },
    {
        # Plataforma Kenlo (mesma de Abasol/Moradasol/Rede Imóveis), mas
        # aqui a listagem é montada por JS -- o HTML cru não traz os links
        # de imóvel, então precisa de Playwright.
        #
        # RESSALVA CONHECIDA: na validação, os 12 cards vieram com preço,
        # quartos e área IDÊNTICOS (2400 / 1 / 27.01) enquanto os slugs das
        # URLs mostram valores diferentes (27m, 23m, 30m, 28m). É o bug de
        # container compartilhado descrito em P-02 da auditoria: a subida na
        # árvore do DOM ultrapassa o card e pega um bloco com vários
        # anúncios. Hoje isso é inofensivo porque são todos de 1 quarto e o
        # filtro de Recife exige 2+, então nada entra na base -- mas os
        # valores só ficam confiáveis depois da correção da Fase 1.
        "nome": "Morada Real",
        "tipo": "revisar",
        "url_listagem": "https://www.moradareal.com.br/imoveis/para-alugar/apartamento/recife",
        "base_url": "https://www.moradareal.com.br",
        "seletor_href": "/imovel/",
        "cidade": "Recife",
        "max_paginas": 3,
        "obs": (
            "DESATIVADO em 19/08/2026 -- robots.txt PROÍBE. Plataforma Kenlo, "
            "cujo robots.txt padrão traz allowlist nomeada (Googlebot, bingbot, "
            "Claude-User etc.) e fecha o resto com 'User-agent: * / Disallow: /'. "
            "Um scraper próprio cai no '*'. Mesma situação do Harry Fernandes, "
            "e a mesma decisão: é política do site, não dificuldade técnica. "
            "Detectado pelo checador automático (robots.py), que passou a rodar "
            "a cada rodada -- antes ninguém tinha conferido. "
            "Alternativa: pedir autorização por escrito à imobiliária."
        ),

    },
    {
        "nome": "Imobiliária Harry Fernandes",
        "tipo": "revisar",
        "url_listagem": "https://www.harryfernandes.com.br/imoveis/para-alugar/recife",
        "base_url": "https://www.harryfernandes.com.br",
        "obs": (
            "NÃO RASPAR. Este é o único dos sites avaliados que proíbe de "
            "verdade: o robots.txt tem uma allowlist nomeada (Googlebot, "
            "bingbot, Claude-User, ChatGPT-User, etc.) e fecha o resto com "
            "'User-agent: * / Disallow: /'. Um scraper próprio cai no '*'. "
            "A plataforma é Kenlo (a mesma de Abasol/Moradasol), então "
            "tecnicamente seria trivial -- é uma decisão de política, não "
            "de dificuldade. Alternativa: acompanhar manualmente, ou pedir "
            "à imobiliária autorização por escrito para o monitoramento."
        ),
    },
    {
        "nome": "Melo Gestão de Imóveis",
        "tipo": "revisar",
        "url_listagem": "https://melogestaodeimoveis.com.br/imoveis/para-alugar/apartamento",
        "base_url": "https://melogestaodeimoveis.com.br",
        "obs": (
            "Dois problemas achados na validação. (1) A listagem "
            "'para-alugar' devolve preços de VENDA (R$ 198.080, R$ 99.000, "
            "R$ 250.204) -- ou a rota não aplica a finalidade, ou o card "
            "mistura as duas. (2) Os links de anúncio são slugs na raiz "
            "(/apartamento-2qts1-vaga54m2), sem prefixo comum: usar 'qt' "
            "como padrao_link_imovel casa também os links de WhatsApp e "
            "duplica cada imóvel. "
            "Obs: a empresa fica em Barra de Jangada, JABOATÃO -- não em "
            "Olinda. robots.txt libera (inclusive ClaudeBot) mas pede "
            "Crawl-delay: 5 e proíbe /busca, o que precisa ser respeitado."
        ),
    },
    {
        "nome": "Imobiliária Eduardo Feitosa",
        "tipo": "revisar",
        "url_listagem": "https://eduardofeitosa.com.br/imoveis.php?para=alugar",
        "base_url": "https://eduardofeitosa.com.br",
        "obs": (
            "robots.txt libera (Allow: / -- só bloqueia páginas de "
            "formulário). Mas a listagem de locação não sai no HTML: "
            "imoveis.php?para=alugar devolve 200 com 54 KB e ZERO ocorrência "
            "de 'R$' e nenhum link de imóvel; acrescentar &tipo=N devolve "
            "HTTP 500. O sitemap.xml tem 211 URLs, nenhuma de locação. "
            "Coerente com o perfil da empresa (lançamentos e revenda, não "
            "aluguel). Reavaliar se/quando passarem a anunciar locação. "
            "Existe também eduardofeitosaprime.com.br, mesmo robots.txt."
        ),
    },
    {
        "nome": "RM Imobiliária (Olinda)",
        "tipo": "revisar",
        "url_listagem": "",
        "base_url": "",
        "obs": (
            "Site não localizado. rmimobiliaria.com.br e "
            "rmimobiliariaolinda.com.br não respondem; rmimoveis.com.br "
            "redireciona para rmimoveisprime.com.br, que não foi possível "
            "confirmar como sendo a mesma empresa de Olinda. "
            "Falta o domínio correto para mapear."
        ),
    },
    {
        # Uma entrada só cobre Recife E Olinda: a busca aceita várias cidades
        # em City=<id>,<id>. A cidade de cada imóvel sai do slug da URL
        # (/alugar/recife/... ou /alugar/olinda/...), então não há "cidade"
        # fixa aqui -- fixar contaminaria metade dos resultados.
        #
        # Substitui as duas entradas antigas (/pt-br/pesquisa/...), que o site
        # reestruturou: elas ainda carregavam 1,5 MB mas com ZERO anúncio.
        # TransactionTypeUID=260 é aluguel; MacroPropertyTypeUIDs=2667 é
        # apartamento. Confirmado ao vivo em 19/08/2026.
        "nome": "REMAX Recife e Olinda",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.remax.com.br/listings?Country=Brasil&Province=9526"
            "&City=6576316%2C6582925&CountryId=55"
            "&CityNM=6576316-Recife%2C6582925-Olinda&ProvinceNM=9526-Pernambuco"
            "&ListingClass=-1&TransactionTypeUID=260&MacroPropertyTypeUIDs=2667"
        ),
        "base_url": "https://www.remax.com.br",
        "seletor_href": "/pt-br/imoveis/apartamento/",
        "wait_until": "load",
        "espera_ms": 5000,
        "max_paginas": 3,
    },
    {
        # A listagem já traz os dados estruturados no HTML (payload do
        # Next.js): rua, área, quartos, banheiros, vagas, bairro, cidade,
        # foto e aluguel. Coletor próprio em scraper_chavesnamao.py.
        #
        # Paginação limitada a 5 porque é o que o robots.txt libera: ele
        # bloqueia query string ("Disallow: /*?*") e abre exatamente
        # "?pg=2" a "?pg=5".
        "nome": "Chaves na Mão Recife",
        "tipo": "chavesnamao",
        "url_listagem": "https://www.chavesnamao.com.br/apartamentos-para-alugar/pe-recife/",
        "base_url": "https://www.chavesnamao.com.br",
        "cidade": "Recife",
        "max_paginas": 5,
    },
    {
        "nome": "Chaves na Mão Olinda",
        "tipo": "chavesnamao",
        "url_listagem": "https://www.chavesnamao.com.br/apartamentos-para-alugar/pe-olinda/",
        "base_url": "https://www.chavesnamao.com.br",
        "cidade": "Olinda",
        "max_paginas": 5,
    },
    {
        "nome": "OLX Imóveis",
        "tipo": "playwright",
        # faixa de preço na própria busca: sem ela o OLX devolve de R$ 250
        # a R$ 10.500 e as 5 páginas se gastam com imóvel fora do orçamento.
        # Os valores vêm de config.FILTROS -- fonte única de verdade (P-09).
        # No OLX 'ps' é o piso e 'pe' o teto (confirmado ao vivo: invertidos,
        # a busca devolve zero resultado).
        "url_listagem": (
            "https://www.olx.com.br/imoveis/aluguel/apartamentos/estado-pe/"
            "recife-e-regiao/recife?ps={preco_min}&pe={preco_max}"
        ),
        "base_url": "https://pe.olx.com.br",
        "seletor_href": "/grande-recife/imoveis/",
        "wait_until": "load",
        "max_paginas": 5,
        "cidade": "Recife",
        # o OLX renderiza preço/área num segundo passe; com menos de 4 s a
        # maioria dos cards sai sem preço e vira indeterminado
        "espera_ms": 4000,
        # O OLX não publica link de "próxima página" que o scraper consiga
        # ler -- verificado na rodada #52, que registrou "o site não publica
        # próxima página" e parou na p1 com 47 anúncios. Aqui a reserva por
        # parâmetro é o caminho, e o parâmetro dele é `o`, não `pagina`.
        "param_pagina": "o",
        "obs": (
            "REATIVADO em 18/08/2026. O diagnóstico anterior apontava para o "
            "payload RSC (window.__next_f), mas ele vem vazio no momento da "
            "leitura -- o caminho certo era o DOM renderizado. Duas causas "
            "reais, ambas corrigidas: (1) o card usa números NUS "
            "('42m² / 2 / 1 / 1' = área/quartos/banheiros/vagas), sem a "
            "palavra 'quarto' que parse_quartos procura -- tratado por "
            "_RE_OLX_NUMEROS; (2) a subida na árvore parava no primeiro 'R$' "
            "(nível de 103 chars), enquanto o bairro só aparece no pai "
            "(SECTION de 185 chars) -- daí todo anúncio vir sem bairro."
        ),
        # A busca cobre MUITO além da região metropolitana (Caruaru,
        # Garanhuns e Gravatá apareceram). Por isso multi_cidade: sem ela, o
        # anúncio cuja cidade não foi detectada era completado com "Recife" --
        # inventar cidade é pior que não saber, porque passa no filtro.
        "multi_cidade": True,
        # NÃO adicione uma segunda entrada OLX para Olinda: tentado em
        # 05/09/2026 e revertido no mesmo dia. A cidade no caminho da URL
        # (.../recife-e-regiao/olinda) é ignorada pela busca -- as duas
        # entradas trouxeram os MESMOS 235 anúncios, e a segunda só
        # sobrescreveu a coluna `site`, fazendo a primeira aparecer com zero.
        # A rodada de validação devolveu, pela entrada "de Olinda": Recife 15,
        # Jaboatão 8, Paulista 5, Olinda 3, Ipojuca 2, Igarassu 1,
        # Camaragibe 1. Olinda já vem por aqui; o que faltava era paginação.
        #
        # metropolitana inteira (Recife/Olinda/Jaboatão/...), então
        # scraper_playwright._parse_card detecta a cidade por item a
        # partir do padrão "Cidade, Bairro" do próprio card. Isso aqui só
        # vale como fallback pros poucos casos em que não detecta.
    },
    {
        "nome": "Imovelweb",
        "tipo": "playwright",
        "url_listagem": "https://www.imovelweb.com.br/apartamentos-aluguel-recife-pe.html",
        "base_url": "https://www.imovelweb.com.br",
        "seletor_href": "/propriedades/",
        "padrao_url_pagina": "https://www.imovelweb.com.br/apartamentos-aluguel-recife-pe-pagina-{n}.html",
        "cidade": "Recife",
        # networkidle (padrão) estoura os 45s: a página mantém requisições
        # de anúncio abertas indefinidamente. Com "load" carrega em ~6s e
        # devolve os 30 cards. Medido em 18/08/2026.
        "wait_until": "load",
        "max_paginas": 5,
    },
    {
        "nome": "Imovelweb Olinda",
        "tipo": "playwright",
        "url_listagem": "https://www.imovelweb.com.br/apartamentos-aluguel-olinda-pe.html",
        "base_url": "https://www.imovelweb.com.br",
        "seletor_href": "/propriedades/",
        "padrao_url_pagina": "https://www.imovelweb.com.br/apartamentos-aluguel-olinda-pe-pagina-{n}.html",
        "cidade": "Olinda",
        "wait_until": "load",
        "max_paginas": 5,
    },
    {
        "nome": "Viva Real",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.vivareal.com.br/aluguel/pernambuco/recife/apartamento_residencial/"
            "?precoMinimo={preco_min}&precoMaximo={preco_max}"
        ),
        "base_url": "https://www.vivareal.com.br",
        "cidade": "Recife",
    },
    {
        "nome": "Viva Real Olinda",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.vivareal.com.br/aluguel/pernambuco/olinda/apartamento_residencial/"
            "?precoMinimo={preco_min}&precoMaximo={preco_max}"
        ),
        "base_url": "https://www.vivareal.com.br",
        "cidade": "Olinda",
    },
    {
        "nome": "Zap Imóveis",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.zapimoveis.com.br/aluguel/apartamentos/pe+recife/"
            "?precoMinimo={preco_min}&precoMaximo={preco_max}"
        ),
        "base_url": "https://www.zapimoveis.com.br",
        "cidade": "Recife",
    },
    {
        "nome": "Zap Imóveis Olinda",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.zapimoveis.com.br/aluguel/apartamentos/pe+olinda/"
            "?precoMinimo={preco_min}&precoMaximo={preco_max}"
        ),
        "base_url": "https://www.zapimoveis.com.br",
        "cidade": "Olinda",
    },
]


# ---------------------------------------------------------------------------
# Resolução de templates nas URLs (P-09 da auditoria)
# ---------------------------------------------------------------------------
# Antes, a faixa de preço aparecia hardcoded na URL de alguns portais E em
# FILTROS. Mudar o orçamento em FILTROS não mudava a busca no portal: ele
# continuava trazendo a faixa antiga e o filtro local cortava o resto -- você
# achava que tinha ampliado a busca e não tinha. Agora a URL declara
# {preco_min}/{preco_max} e o valor vem de FILTROS na carga.
_PLACEHOLDERS = {
    "preco_min": FILTROS["preco_min"],
    "preco_max": FILTROS["preco_max"],
}

# Piso zero não vai para a URL: "ps=0" é um piso literal, e portal que trata
# 0 como valor válido pode devolver busca vazia. Sem o parâmetro, a listagem
# simplesmente não tem piso -- que é o que zero significa aqui.
_RE_PISO_NA_URL = re.compile(r"[?&]ps=\{preco_min\}")

for _site in SITES:
    for _campo in ("url_listagem", "padrao_url_pagina"):
        _valor = _site.get(_campo)
        if not _valor or "{preco_" not in _valor:
            continue
        if not FILTROS["preco_min"]:
            _valor = _RE_PISO_NA_URL.sub(
                lambda m: "?" if m.group(0)[0] == "?" else "", _valor, count=1
            )
            # o corte pode ter deixado "?&pe=" -- normaliza
            _valor = _valor.replace("?&", "?")
        _site[_campo] = _valor.format(**_PLACEHOLDERS)
