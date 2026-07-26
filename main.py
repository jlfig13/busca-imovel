# -*- coding: utf-8 -*-
"""
Monitor semanal de apartamentos para alugar em Recife e Olinda.
Executa todos os sites configurados em config.py, aplica os filtros,
gera uma planilha Excel e um dashboard HTML (consulta online, sem envio
de e-mail -- ver README para publicação via GitHub Pages/Actions).

Uso:
    python main.py
"""
import sys

import config
import report
import dashboard
import scraper_pratica_internet
import scraper_portais
import scraper_cards_inline
import scraper_playwright
from utils import log

# Mapeia o "tipo" de site (config.py) para o módulo de scraping responsável
SCRAPERS = {
    "html_estatico": scraper_pratica_internet,
    "portal_classificados": scraper_portais,
    "cards_inline": scraper_cards_inline,
    "playwright": scraper_playwright,
}


def rodar():
    log.info("=" * 60)
    log.info("Iniciando monitor de apartamentos")
    log.info(f"Filtros: {config.FILTROS}")

    todos_itens = []
    sites_pulados = []

    for site in config.SITES:
        tipo = site["tipo"]

        if tipo == "revisar":
            sites_pulados.append(site["nome"])
            log.info(f"[{site['nome']}] SKIP - {site.get('obs', 'ainda não mapeado, ver README')}")
            continue

        modulo = SCRAPERS.get(tipo)
        if not modulo:
            log.warning(f"[{site['nome']}] tipo desconhecido: {tipo}")
            continue

        try:
            itens = modulo.scrape(site)
            todos_itens.extend(itens)
        except Exception as e:
            log.error(f"[{site['nome']}] erro inesperado: {e}")

    log.info(f"Total de imóveis dentro do filtro (todos os sites): {len(todos_itens)}")

    if sites_pulados:
        log.info(
            f"{len(sites_pulados)} site(s) ainda não mapeados e foram pulados: "
            f"{', '.join(sites_pulados)}. Ver README.md para como adicioná-los."
        )

    todos_itens = report.marcar_novos(todos_itens)
    report.gerar_excel(todos_itens)
    caminho_dashboard = dashboard.gerar_dashboard(todos_itens)

    log.info(f"Dashboard: {caminho_dashboard}")
    log.info("Concluído.")
    return todos_itens


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        log.error(f"Falha geral na execução: {e}")
        sys.exit(1)
