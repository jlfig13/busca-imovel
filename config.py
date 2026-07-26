# -*- coding: utf-8 -*-
"""
Configurações do Monitor de Apartamentos.
Edite os valores abaixo conforme sua busca.
"""

import os

# ---------------------------------------------------------------------------
# FILTROS DE BUSCA
# ---------------------------------------------------------------------------
FILTROS = {
    "preco_min": 1500,
    "preco_max": 2500,
}

# quartos_min/area_min variam por cidade -- Olinda tem exigência maior
# (imóvel menor lá compensa menos que em Recife). Cidade de um imóvel vem
# do campo "cidade" do site em config.SITES, ou detectada no próprio card
# (ex: OLX busca a região metropolitana inteira e mistura Recife/Olinda/
# Jaboatão num resultado só). Cidade sem entrada aqui cai no perfil padrão.
FILTROS_POR_CIDADE = {
    "Recife": {"quartos_min": 2, "area_min": 60},
    "Olinda": {"quartos_min": 3, "area_min": 70},
}
FILTRO_PADRAO = FILTROS_POR_CIDADE["Recife"]

# ---------------------------------------------------------------------------
# ARQUIVOS DE SAÍDA
# ---------------------------------------------------------------------------
PASTA_SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")
ARQUIVO_EXCEL = os.path.join(PASTA_SAIDA, "apartamentos.xlsx")
ARQUIVO_DB = os.path.join(PASTA_SAIDA, "apartamentos.db")
ARQUIVO_DASHBOARD = os.path.join(PASTA_SAIDA, "dashboard.html")
ARQUIVO_LOG = os.path.join(PASTA_SAIDA, "scraper.log")

# ---------------------------------------------------------------------------
# BRIGHT DATA (opcional, mas recomendado para OLX / Viva Real / Zap Imóveis)
# ---------------------------------------------------------------------------
# Esses 3 portais têm proteção anti-bot forte (Cloudflare/DataDome). Requests
# simples costumam ser bloqueados depois de poucas tentativas. Se quiser que
# esses 3 funcionem de forma confiável todo dia, crie uma conta em
# https://brightdata.com, ative uma zona "Web Unlocker" e preencha abaixo
# (ou exporte como variável de ambiente antes de rodar).
BRIGHTDATA_API_KEY = os.environ.get("BRIGHTDATA_API_KEY", "")
BRIGHTDATA_UNLOCKER_ZONE = os.environ.get("BRIGHTDATA_UNLOCKER_ZONE", "")

# ---------------------------------------------------------------------------
# SITES MONITORADOS
# ---------------------------------------------------------------------------
# tipo:
#   "html_estatico" -> listagem vem pronta no HTML (requests + BeautifulSoup)
#   "portal_classificados" -> OLX / Viva Real / Zap (precisa Bright Data p/ ser confiável)
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
        "tipo": "cards_inline",
        "template": "kenlo",
        "url_listagem": "https://www.abasol.com.br/imoveis/para-alugar/apartamento",
        "base_url": "https://www.abasol.com.br",
        "padrao_link_imovel": "/imovel/",
        "max_paginas": 20,
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
        "tipo": "cards_inline",
        "template": "kenlo",
        "url_listagem": "https://www.moradasol.com.br/imoveis/para-alugar/apartamento/recife",
        "base_url": "https://www.moradasol.com.br",
        "padrao_link_imovel": "/imovel/",
    },
    {
        "nome": "Rede Imóveis Pernambuco",
        "tipo": "cards_inline",
        "template": "kenlo",
        "url_listagem": "https://www.redeimoveispe.com.br/imoveis/para-alugar/apartamento/recife",
        "base_url": "https://www.redeimoveispe.com.br",
        "padrao_link_imovel": "/imovel/",
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
            "O robots.txt deste site proíbe explicitamente acesso automatizado. "
            "Por respeito à política do site, não construí um scraper para ele."
        ),
    },
    {
        "nome": "REMAX Recife",
        "tipo": "playwright",
        "url_listagem": "https://www.remax.com.br/pt-br/pesquisa/regiao-nordeste/pernambuco/recife/residencial-apartamento/alugar/",
        "base_url": "https://www.remax.com.br",
        "seletor_href": "/pt-br/imoveis/apartamento/",
        "cidade": "Recife",
        "max_paginas": 3,
    },
    {
        "nome": "REMAX Olinda",
        "tipo": "playwright",
        "url_listagem": "https://www.remax.com.br/pt-br/pesquisa/regiao-nordeste/pernambuco/olinda/residencial-apartamento/alugar/",
        "base_url": "https://www.remax.com.br",
        "seletor_href": "/pt-br/imoveis/apartamento/",
        "cidade": "Olinda",
        "max_paginas": 3,
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
            "O robots.txt deste site proíbe explicitamente acesso automatizado. "
            "Por respeito à política do site, não construí um scraper para ele. "
            "Sugestão: acompanhar manualmente ou perguntar diretamente ao corretor "
            "se ele pode te avisar de novidades por WhatsApp."
        ),
    },
    {
        "nome": "OLX Imóveis",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.olx.com.br/imoveis/aluguel/apartamentos/estado-pe/"
            "recife-e-regiao/recife"
        ),
        "base_url": "https://pe.olx.com.br",
        "seletor_href": "/grande-recife/imoveis/",
        "wait_until": "load",
        "max_paginas": 5,
        # sem "cidade" fixo de propósito: essa busca cobre a região
        "cidade": "Recife",
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
        "max_paginas": 5,
    },
    {
        "nome": "Viva Real",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.vivareal.com.br/aluguel/pernambuco/recife/apartamento_residencial/"
            "?quartos=2&precoMinimo=1500&precoMaximo=2500"
        ),
        "base_url": "https://www.vivareal.com.br",
        "cidade": "Recife",
    },
    {
        "nome": "Viva Real Olinda",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.vivareal.com.br/aluguel/pernambuco/olinda/apartamento_residencial/"
            "?quartos=3&precoMinimo=1500&precoMaximo=2500"
        ),
        "base_url": "https://www.vivareal.com.br",
        "cidade": "Olinda",
    },
    {
        "nome": "Zap Imóveis",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.zapimoveis.com.br/aluguel/apartamentos/pe+recife/"
            "?quartos=2&precoMinimo=1500&precoMaximo=2500"
        ),
        "base_url": "https://www.zapimoveis.com.br",
        "cidade": "Recife",
    },
    {
        "nome": "Zap Imóveis Olinda",
        "tipo": "playwright",
        "url_listagem": (
            "https://www.zapimoveis.com.br/aluguel/apartamentos/pe+olinda/"
            "?quartos=3&precoMinimo=1500&precoMaximo=2500"
        ),
        "base_url": "https://www.zapimoveis.com.br",
        "cidade": "Olinda",
    },
]
