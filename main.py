# -*- coding: utf-8 -*-
"""
Monitor semanal de apartamentos para alugar em Recife e Olinda.
Executa todos os sites configurados em config.py, aplica os filtros,
gera uma planilha Excel e um dashboard HTML (consulta online, sem envio
de e-mail -- ver README para publicação via GitHub Pages/Actions).

Uso:
    python main.py
"""
import subprocess
import sys
import time

import config
import db
import report
import robots
import dashboard
import scraper_pratica_internet
import scraper_cards_inline
import scraper_playwright
from utils import log

# Mapeia o "tipo" de site (config.py) para o módulo de scraping responsável
SCRAPERS = {
    "html_estatico": scraper_pratica_internet,
    "cards_inline": scraper_cards_inline,
    "playwright": scraper_playwright,
}


def _versao_codigo() -> str:
    """SHA curto do commit atual, para explicar regressão de scraper."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return ""


def rodar():
    log.info("=" * 60)
    log.info("Iniciando monitor de apartamentos")
    log.info(f"Filtros: {config.FILTROS}")

    execucao_id = db.abrir_execucao(_versao_codigo())
    todos_itens = []
    sites_pulados = []
    fontes_confiaveis: set[str] = set()

    for site in config.SITES:
        nome = site["nome"]
        tipo = site["tipo"]

        if tipo == "revisar":
            sites_pulados.append(nome)
            db.registrar_fonte(execucao_id, nome, db.PULADO,
                               motivo=site.get("obs", "não mapeado")[:180])
            log.info(f"[{nome}] SKIP - {site.get('obs', 'ainda não mapeado, ver README')}")
            continue

        # Guarda de robots.txt (P-17). Antes disso a política de cada site era
        # uma anotação manual no config -- e duas estavam simplesmente erradas,
        # enquanto quatro fontes que PROIBIAM vinham sendo raspadas sem que
        # ninguém tivesse conferido. Agora é verificado, datado e revalidado.
        if not robots.pode_raspar(site["url_listagem"]):
            db.registrar_fonte(execucao_id, nome, db.PULADO,
                               motivo="robots.txt proíbe este caminho")
            log.warning(f"[{nome}] PULADO -- robots.txt proíbe")
            continue

        modulo = SCRAPERS.get(tipo)
        if not modulo:
            db.registrar_fonte(execucao_id, nome, db.FALHA, motivo=f"tipo desconhecido: {tipo}")
            log.warning(f"[{nome}] tipo desconhecido: {tipo}")
            continue

        inicio = time.monotonic()
        try:
            itens = modulo.scrape(site)
            duracao = time.monotonic() - inicio
            # O scraper anexa as contagens em itens.stats quando disponível;
            # sem isso caímos no que dá para inferir da lista devolvida.
            stats = getattr(itens, "stats", {})
            brutos = stats.get("brutos", len(itens))
            status = db.SEM_ESTOQUE if brutos == 0 else db.OK
            motivo = stats.get("motivo")
            if stats.get("bloqueado"):
                status, motivo = db.BLOQUEADO, motivo or "challenge anti-bot"
            # guarda de sanidade: volume anômalo sem erro técnico
            status, motivo_sanidade = db.avaliar_sanidade(nome, brutos, status)
            motivo = motivo or motivo_sanidade

            db.registrar_fonte(
                execucao_id, nome, status, motivo=motivo, brutos=brutos,
                aprovados=len(itens),
                indeterminados=stats.get("indeterminados", 0),
                reprovados=stats.get("reprovados", 0),
                duracao_s=round(duracao, 1), erros=stats.get("erros", 0),
            )
            if status in db.STATUS_CONFIAVEIS:
                fontes_confiaveis.add(nome)
            elif status == db.PARCIAL:
                log.warning(f"[{nome}] REBAIXADO para PARCIAL: {motivo}")

            todos_itens.extend(itens)
        except Exception as e:
            db.registrar_fonte(execucao_id, nome, db.FALHA, motivo=str(e)[:180],
                               duracao_s=round(time.monotonic() - inicio, 1), erros=1)
            log.error(f"[{nome}] erro inesperado: {e}")

    log.info(f"Total de imóveis dentro do filtro (todos os sites): {len(todos_itens)}")
    log.info(
        f"Fontes confiáveis nesta rodada: {len(fontes_confiaveis)} "
        f"(só elas autorizam marcar imóvel como ausente)"
    )

    if sites_pulados:
        log.info(
            f"{len(sites_pulados)} site(s) ainda não mapeados e foram pulados: "
            f"{', '.join(sites_pulados)}. Ver README.md para como adicioná-los."
        )

    todos_itens = report.marcar_novos(todos_itens, fontes_confiaveis, execucao_id)

    # Fase 3: ausência vira SUSPEITO e, na segunda falta, INATIVO
    db.aplicar_ciclo_de_vida(fontes_confiaveis, execucao_id)

    # Fase 2: os anúncios viram imóveis físicos. O dashboard e a planilha
    # passam a listar imóvel -- um apartamento, um card, N selos de fonte --
    # em vez de repetir o mesmo apartamento uma vez por portal.
    imoveis = db.consolidar_imoveis(todos_itens)

    report.gerar_excel(imoveis)
    caminho_dashboard = dashboard.gerar_dashboard(imoveis, db.resumo_fontes(execucao_id))

    saude = db.resumo_fontes(execucao_id)
    degradadas = [f for f in saude if f["status"] in (db.FALHA, db.BLOQUEADO, db.PARCIAL)]
    db.encerrar_execucao(execucao_id, db.PARCIAL if degradadas else db.OK)
    if degradadas:
        log.warning(
            f"{len(degradadas)} fonte(s) degradada(s): "
            + ", ".join(f"{f['fonte']} ({f['status']})" for f in degradadas)
        )

    log.info(f"Dashboard: {caminho_dashboard}")
    log.info("Concluído.")
    return todos_itens


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        log.error(f"Falha geral na execução: {e}")
        sys.exit(1)
