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
from datetime import date
from concurrent.futures import ThreadPoolExecutor

import config
import db
import report
import robots
import dashboard
import galeria
import scraper_pratica_internet
import scraper_cards_inline
import scraper_playwright
import utils
from utils import log

# Mapeia o "tipo" de site (config.py) para o módulo de scraping responsável
# Fontes coletadas em paralelo. Ver o comentário na etapa 2 de rodar():
# 3 foi medido contra a memória do runner, não escolhido por gosto.
WORKERS = 3

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


def _completar_galerias(imoveis: list[dict]) -> None:
    """Busca a galeria dos imóveis exibidos e persiste no banco.

    Trabalha sobre os ANÚNCIOS do imóvel (é neles que a foto é gravada), e
    para no primeiro que devolver galeria: dois portais anunciando o mesmo
    apartamento mostram as mesmas paredes."""
    pendentes = []
    for imovel in imoveis:
        anuncios = imovel.get("anuncios") or []
        if any((a.get("fotos") or []) for a in anuncios):
            continue
        pendentes += [dict(a) for a in anuncios[:2]]

    if not pendentes:
        return

    galeria.enriquecer(pendentes)
    novas = {a["url"]: a["fotos"] for a in pendentes if a.get("fotos")}
    if novas:
        db.atualizar_fotos(novas)
        # o dashboard é gerado a seguir, na mesma execução: sem isto as
        # fotos só apareceriam na rodada seguinte
        por_url = {a["url"]: a["fotos"] for a in pendentes if a.get("fotos")}
        for imovel in imoveis:
            if imovel.get("foto"):
                continue
            for a in imovel.get("anuncios") or []:
                if por_url.get(a["url"]):
                    imovel["foto"] = por_url[a["url"]][0]
                    imovel["fotos"] = por_url[a["url"]]
                    break


def rodar():
    log.info("=" * 60)
    log.info("Iniciando monitor de apartamentos")
    log.info(f"Filtros: {config.FILTROS}")

    # Migra o que restar do snapshot antigo e derruba a tabela. O histórico
    # anterior à Fase 3 existe só em historico_precos e as datas de julho não
    # podem ser recoletadas -- por isso migra ANTES de derrubar, sempre.
    db.aposentar_historico_precos()

    execucao_id = db.abrir_execucao(_versao_codigo())
    todos_itens = []
    sites_pulados = []
    fontes_confiaveis: set[str] = set()

    # ---------------------------------------------------------------------
    # 1. TRIAGEM (sequencial) -- decide quem vai ser consultado
    # ---------------------------------------------------------------------
    # Fica fora do paralelo de propósito: a checagem de robots.txt grava em
    # cache no banco, e SQLite com vários escritores dá "database is locked".
    a_coletar = []
    for site in config.SITES:
        nome, tipo = site["nome"], site["tipo"]

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
            db.registrar_fonte(execucao_id, nome, db.FALHA,
                               motivo=f"tipo desconhecido: {tipo}")
            log.warning(f"[{nome}] tipo desconhecido: {tipo}")
            continue

        a_coletar.append((site, modulo))

    # ---------------------------------------------------------------------
    # 2. COLETA (paralela) -- só rede e parsing, nenhuma escrita no banco
    # ---------------------------------------------------------------------
    # As fontes são independentes: cada uma abre seu próprio contexto de
    # navegador. Antes disso a rodada era sequencial e as 7 fontes Playwright
    # respondiam por ~70% do tempo total.
    #
    # WORKERS = 3 foi medido, não escolhido: 3 Chromium simultâneos usaram
    # 1.667 MB de pico (~556 MB cada), contra os ~7 GB do runner do Actions.
    # Sobra folga para o Python, o sistema e páginas grandes (o OLX carrega
    # 1,2 MB). Subir para 4 caberia; 3 mantém margem sem perder quase nada,
    # porque o tempo passa a ser ditado pela fonte mais lenta.
    #
    # Nenhum worker toca o banco. O registro acontece na etapa 3, na thread
    # principal, porque escrita concorrente em SQLite trava.
    def coletar(par):
        site, modulo = par
        inicio = time.monotonic()
        try:
            itens = modulo.scrape(site)
            return site, itens, time.monotonic() - inicio, None
        except Exception as e:
            return site, None, time.monotonic() - inicio, e

    resultados = []
    if a_coletar:
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            for r in executor.map(coletar, a_coletar):
                resultados.append(r)

    # ---------------------------------------------------------------------
    # 3. REGISTRO (sequencial) -- avalia e grava
    # ---------------------------------------------------------------------
    # Ordena por nome para o log sair estável entre rodadas: com paralelismo
    # a ordem de chegada varia, e log que muda de ordem é difícil de comparar.
    for site, itens, duracao, erro in sorted(resultados, key=lambda x: x[0]["nome"]):
        nome = site["nome"]
        if erro is not None:
            db.registrar_fonte(execucao_id, nome, db.FALHA, motivo=str(erro)[:180],
                               duracao_s=round(duracao, 1), erros=1)
            log.error(f"[{nome}] erro inesperado: {erro}")
            continue

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

    # Recorte de APRESENTAÇÃO (config.BAIRROS_EXIBIDOS). O banco guarda a
    # cidade inteira -- é dele que sai a série de preço e o dedupe entre
    # portais --, mas dashboard e planilha mostram só os bairros escolhidos.
    # Filtrar aqui, e não na coleta, é o que permite mudar de ideia sobre um
    # bairro sem recomeçar o histórico dele do zero.
    exibidos = [i for i in imoveis
                if utils.bairro_exibivel(i.get("cidade"), i.get("bairro"))]
    ocultos = {
        "sem_bairro": sum(1 for i in imoveis if not i.get("bairro")),
        "fora": len(imoveis) - len(exibidos) - sum(
            1 for i in imoveis if not i.get("bairro")),
    }
    log.info(
        f"Apresentação: {len(exibidos)} de {len(imoveis)} imóveis nos bairros "
        f"escolhidos ({ocultos['fora']} fora, {ocultos['sem_bairro']} sem bairro)"
    )

    # Galeria completa: uma requisição por imóvel EXIBIDO que ainda esteja
    # sem fotos. Só Viva Real e Zap publicam imagem na listagem (e mesmo
    # assim cinco por anúncio) -- as outras dezesseis fontes chegavam aqui
    # sem foto nenhuma, e card sem foto é card que ninguém abre.
    #
    # Depois do recorte, e não antes: visitar a cidade inteira gastaria uma
    # requisição por anúncio para encher de foto imóvel que ninguém vai ver.
    _completar_galerias(exibidos)

    report.gerar_excel(exibidos)
    caminho_dashboard = dashboard.gerar_dashboard(
        exibidos, db.resumo_fontes(execucao_id), db.rendimento_por_fonte(),
        ocultos=ocultos,
    )

    saude = db.resumo_fontes(execucao_id)
    degradadas = [f for f in saude if f["status"] in (db.FALHA, db.BLOQUEADO, db.PARCIAL)]
    db.encerrar_execucao(execucao_id, db.PARCIAL if degradadas else db.OK)
    if degradadas:
        log.warning(
            f"{len(degradadas)} fonte(s) degradada(s): "
            + ", ".join(f"{f['fonte']} ({f['status']})" for f in degradadas)
        )

    # Manutenção no fim: poda todo dia (é barata e só toca o que está
    # inativo há 180+ dias), VACUUM só no domingo -- ele reescreve o arquivo
    # inteiro e não vale o custo diário.
    db.manutencao(vacuum=date.today().weekday() == 6)

    log.info(f"Dashboard: {caminho_dashboard}")
    log.info("Concluído.")
    return todos_itens


if __name__ == "__main__":
    try:
        rodar()
    except Exception as e:
        log.error(f"Falha geral na execução: {e}")
        sys.exit(1)
