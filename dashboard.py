# -*- coding: utf-8 -*-
"""
Gera um único arquivo HTML autocontido (dashboard.html), com os dados
embutidos como JSON. Abre com duplo clique -- sem servidor, sem internet,
sem instalação. É essa restrição que permite publicá-lo no GitHub Pages
como artefato estático.

O sistema visual está em design.py, com o racional de cada decisão.
"""
import html
import json
from datetime import date, datetime, timedelta, timezone

import afinidade
import config
import db
import design
import geo
import mapa
from utils import log, NAO_LOCALIZADO


def _fmt_preco(v):
    if v is None:
        return NAO_LOCALIZADO
    return f"R$ {v:,.0f}".replace(",", ".")


def _historico_unificado(historico_map: dict, urls: list) -> list:
    """Une as séries de preço dos anúncios de um mesmo imóvel.

    Quando dois portais anunciam o mesmo apartamento, cada um tem sua série.
    Mesclar por data ficando com o menor valor do dia evita que o gráfico
    serrilhe entre portais que cobram valores levemente diferentes, e faz a
    queda aparecer assim que QUALQUER fonte baixa o preço."""
    por_data: dict[str, float] = {}
    for url in urls:
        for data, preco in historico_map.get(url, []):
            if preco is None:
                continue
            if data not in por_data or preco < por_data[data]:
                por_data[data] = preco
    return [[d, por_data[d]] for d in sorted(por_data)][-30:]


_CLASSE_STATUS = {
    "OK": "st-ok", "SEM_ESTOQUE": "st-neutro", "PULADO": "st-neutro",
    "PARCIAL": "st-alerta", "BLOQUEADO": "st-erro", "FALHA": "st-erro",
}


def _painel_saude(saude: list[dict] | None) -> str:
    """Saúde por fonte, recolhida por padrão e aberta quando há problema.

    Existe porque fonte que quebra em silêncio é indistinguível de fonte sem
    estoque (P-04): antes disso só o log contava a diferença, e ninguém lê
    log de rodada que "funcionou"."""
    if not saude:
        return ""

    degradadas = [f for f in saude if f["status"] in ("FALHA", "BLOQUEADO", "PARCIAL")]
    ok = len([f for f in saude if f["status"] == "OK"])
    resumo = (f"{len(degradadas)} fonte(s) exigindo atenção"
              if degradadas else f"{ok} fontes saudáveis")

    linhas = []
    for f in saude:
        if f["status"] == "PULADO":
            continue  # não mapeada de propósito; não é sintoma de quebra
        linhas.append(
            f"<tr><td>{html.escape(f['fonte'])}</td>"
            f"<td><span class='st {_CLASSE_STATUS.get(f['status'], 'st-neutro')}'>"
            f"{f['status']}</span></td>"
            f"<td class='n'>{f['brutos'] or 0}</td>"
            f"<td class='n'>{f['aprovados'] or 0}</td>"
            f"<td class='n'>{f['indeterminados'] or 0}</td>"
            f"<td class='n'>{f['duracao_s'] or 0:.0f}s</td>"
            f"<td>{html.escape(f['motivo'] or '')}</td></tr>"
        )

    return f"""<details class="saude"{' open' if degradadas else ''}>
    <summary><span class="ponto{' alerta' if degradadas else ''}"></span>Saúde das fontes — {resumo}</summary>
    <div class="saude-rolagem"><table>
      <thead><tr><th>Fonte</th><th>Status</th><th class="n">Coletados</th>
        <th class="n">No filtro</th><th class="n">Incompletos</th>
        <th class="n">Tempo</th><th>Observação</th></tr></thead>
      <tbody>{''.join(linhas)}</tbody>
    </table></div>
  </details>"""


def _painel_rendimento(rendimento: list[dict] | None) -> str:
    """Custo x retorno por fonte, para decidir o que desligar.

    A ordem vem do banco: pior rendimento primeiro (sem exclusivos, pouco
    volume, muito tempo). É a lista de candidatos a corte, de cima para
    baixo. Marcamos em âmbar quem gastou tempo e não trouxe nada exclusivo
    -- não é ordem de desligar, é onde olhar."""
    if not rendimento:
        return '<div class="estado-vazio">Sem execuções registradas ainda.</div>'

    max_filtro = max((f["no_filtro"] for f in rendimento), default=0) or 1
    max_excl = max((f["exclusivos"] for f in rendimento), default=0) or 1

    linhas = []
    for f in rendimento:
        # Candidato a corte: gastou tempo e não passou NADA no filtro.
        # Marcar por "zero exclusivos" pegaria Zap e Viva Real, que só têm
        # zero porque duplicam uma à outra -- e são o catálogo inteiro.
        suspeito = f["no_filtro"] == 0 and f["segundos"] >= 20
        larg_f = round(100 * f["no_filtro"] / max_filtro)
        larg_e = round(100 * f["exclusivos"] / max_excl)
        # sem nenhum anúncio útil não existe custo por útil -- e escrever
        # "Não Localizado" aqui sugeriria dado que a fonte não informou
        s_util = f"{f['s_por_util']:.0f}s" if f["s_por_util"] else "—"
        linhas.append(
            f"<tr class='{'aviso' if suspeito else ''}'>"
            f"<td class='fonte'>{html.escape(f['fonte'])}</td>"
            f"<td><span class='st {_CLASSE_STATUS.get(f['status'], 'st-neutro')}'>"
            f"{html.escape(str(f['status']))}</span></td>"
            f"<td class='n'>{f['rodadas']}</td>"
            f"<td class='n'>{f['brutos']}</td>"
            f"<td class='n'>{f['no_filtro']}"
            f"<span class='barra{'' if f['no_filtro'] else ' vazia'}' "
            f"style='width:{max(larg_f, 2)}%'></span></td>"
            f"<td class='n'>{f['exclusivos']}"
            f"<span class='barra{'' if f['exclusivos'] else ' vazia'}' "
            f"style='width:{max(larg_e, 2)}%'></span></td>"
            f"<td class='n'>{f['segundos']:.0f}s</td>"
            f"<td class='n'>{s_util}</td>"
            f"<td class='n'>{f['falhas'] or ''}</td></tr>"
        )

    vazias = [f for f in rendimento if f["no_filtro"] == 0]
    tempo_vazio = sum(f["segundos"] for f in vazias)
    nota = (f"{len(vazias)} fonte(s) não passaram nenhum anúncio no filtro nessas "
            f"rodadas, gastando {tempo_vazio:.0f}s no total."
            if vazias else "Todas as fontes passaram pelo menos um anúncio no filtro.")

    return f"""<p class="rend-nota">Últimas 10 execuções. <b>No filtro</b> é o que a
    fonte entrega dentro do perfil de busca; <b>só ela</b> é o que se perde ao
    desligá-la — imóveis ativos que nenhuma outra fonte anuncia. {nota}</p>
    <div class="rend-rolagem"><table>
      <thead><tr><th>Fonte</th><th>Último status</th><th class="n">Rodadas</th>
        <th class="n">Coletados</th><th class="n">No filtro</th>
        <th class="n">Só ela</th><th class="n">Tempo</th>
        <th class="n">Por útil</th><th class="n">Falhas</th></tr></thead>
      <tbody>{''.join(linhas)}</tbody>
    </table></div>
    <div class="rend-legenda">
      Linha em âmbar: gastou 20s+ e não trouxe nenhum imóvel exclusivo.<br>
      "Por útil" = segundos gastos por anúncio que passou no filtro.<br>
      Volume baixo não basta para desligar: uma fonte pequena pode ser a única
      com o imóvel que interessa. A coluna "Só ela" é a que decide.
    </div>"""


def _painel_mapa(svg: str) -> str:
    """Aba de mapa. Sem geometria no cache, diz por quê em vez de ficar branca.

    A atribuição à OpenStreetMap não é enfeite de rodapé: os polígonos vêm de
    lá sob ODbL, que EXIGE crédito de quem redistribui. É a mesma postura que
    fez o projeto respeitar robots.txt -- usar o trabalho dos outros nas
    condições que eles pediram.
    """
    if not svg:
        return """<div class="mapa-caixa"><p class="mapa-vazio">
        O mapa ainda não tem os contornos dos bairros.<br>
        Eles são buscados na OpenStreetMap uma vez por bairro e guardados em
        <code>geo/bairros.json</code>; a próxima rodada completa o que faltar.
        </p></div>"""
    return f"""<div class="mapa-caixa">
      {svg}
      <div class="mapa-legenda">
        <span>Mais barato</span>
        <span class="mapa-escala">
          <span class="mapa-degrau q1"></span><span class="mapa-degrau q2"></span>
          <span class="mapa-degrau q3"></span><span class="mapa-degrau q4"></span>
          <span class="mapa-degrau q5"></span>
        </span>
        <span>Mais caro</span>
        <span id="mapa-legenda-nota"></span>
      </div>
      <div class="mapa-detalhe" id="mapa-detalhe" hidden></div>
      <p class="mapa-fonte">Contornos dos bairros:
        <a href="https://www.openstreetmap.org/copyright" target="_blank"
           rel="noopener noreferrer">OpenStreetMap</a>, sob ODbL.</p>
    </div>"""


def _ler_triagem() -> dict:
    """Lê triagem.json (favoritos/descartes versionados) para embutir no HTML.

    Arquivo ausente ou quebrado não pode derrubar a rodada: a triagem é
    conveniência, o catálogo é o produto. Volta vazio e a vida segue."""
    try:
        with open(config.ARQUIVO_TRIAGEM, encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        return {"favoritos": {}, "descartados": {}}
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"triagem.json ilegível ({e}); seguindo sem semente")
        return {"favoritos": {}, "descartados": {}}

    saida = {}
    for chave in ("favoritos", "descartados"):
        valor = dados.get(chave)
        # aceita tanto {url: data} quanto uma lista de urls, que é o que
        # sai de um copiar-colar apressado
        if isinstance(valor, list):
            saida[chave] = {u: "" for u in valor if isinstance(u, str)}
        elif isinstance(valor, dict):
            saida[chave] = {k: v for k, v in valor.items() if isinstance(k, str)}
        else:
            saida[chave] = {}
    return saida


def gerar_dashboard(itens: list[dict], saude: list[dict] | None = None,
                    rendimento: list[dict] | None = None,
                    ocultos: dict | None = None) -> str:
    """Monta o dashboard a partir dos IMÓVEIS consolidados (não anúncios)."""

    urls = [u for i in itens for u in (i.get("urls") or [i.get("url", "")])]
    historico_map = db.obter_serie_precos(urls)

    dados = []
    for i in itens:
        anuncios = i.get("anuncios") or []
        urls_item = ([a["url"] for a in anuncios] if anuncios
                     else (i.get("urls") or [i.get("url", "#")]))
        hist = _historico_unificado(historico_map, urls_item)
        # Preço de vitrine é o MENOR entre as fontes: é o que você de fato
        # pagaria. A mediana consolidada mostraria um valor que não está
        # disponível em portal nenhum.
        preco = i.get("preco_min") or i.get("custo_mensal_total") or i.get("preco")

        queda = None
        queda_pct = None
        if len(hist) >= 2 and preco is not None:
            anterior = next((h[1] for h in reversed(hist[:-1]) if h[1] is not None), None)
            if anterior and anterior > preco:
                queda = round(anterior - preco, 2)
                # O valor absoluto sozinho não diz se a queda é notícia: R$ 100
                # em 1.500 é outra conversa que R$ 100 em 2.500. O selo mostra
                # os dois, e é o percentual que decide se vale abrir.
                queda_pct = round(100 * queda / anterior)

        dados.append({
            "titulo": i.get("titulo") or "Apartamento",
            "cidade": i.get("cidade") or "",
            "bairro": i.get("bairro") or "",
            "logradouro": i.get("logradouro") or "",
            "preco": preco,
            "precoFmt": _fmt_preco(preco),
            "quartos": i.get("quartos"),
            "area": i.get("area_m2"),
            "banheiros": i.get("banheiros"),
            "vagas": i.get("vagas"),
            "andar": i.get("andar"),
            "precoM2": i.get("preco_m2"),
            "diasAnunciado": i.get("dias_anunciado") or 0,
            "custoCompleto": bool(i.get("custo_completo")),
            "conflitos": [c["campo"] for c in (i.get("conflitos") or [])],
            "sites": i.get("sites") or ([i["site"]] if i.get("site") else []),
            "qtdFontes": i.get("qtd_fontes", 1),
            "anuncios": anuncios,
            "economia": i.get("economia") or 0,
            "url": urls_item[0] if urls_item else "#",
            "fotos": i.get("fotos") or ([i["foto"]] if i.get("foto") else []),
            "novo": bool(i.get("novo")),
            # noRecorte NÃO vai mais para o JSON: quem decide o recorte é a
            # preferência salva no navegador. O campo continua existindo no
            # item porque main.py o usa para escolher de quem buscar galeria e
            # o que entra na planilha -- mas mandá-lo para a tela agora só
            # criaria duas fontes de verdade para a mesma pergunta.
            "historico": hist,
            "queda": queda,
            "quedaPct": queda_pct,
        })

    # Nota de afinidade: quem combina com o perfil vai para o topo com selo.
    # Roda aqui, e não no main, para que qualquer geração do HTML (inclusive
    # a partir de uma cópia do banco, em teste de layout) traga a sugestão.
    afinidade.pontuar(dados)

    precos = [d["preco"] for d in dados if d["preco"]]
    mediana_m2 = sorted(d["precoM2"] for d in dados if d["precoM2"])
    med_m2 = mediana_m2[len(mediana_m2) // 2] if mediana_m2 else None

    json_dados = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    json_semente = json.dumps(_ler_triagem(), ensure_ascii=False)
    # Preferências: o dashboard passa a recortar no navegador, então precisa
    # do padrão (para quem nunca mexeu) e do universo de escolhas (todas as
    # cidades e bairros que a coleta trouxe -- não a lista fixa do config,
    # senão ninguém consegue escolher um bairro que não seja o meu).
    json_prefs = json.dumps(config.PREFERENCIAS_PADRAO, ensure_ascii=False)
    bairros_por_cidade: dict[str, list[str]] = {}
    for d in dados:
        if d["cidade"] and d["bairro"]:
            bairros_por_cidade.setdefault(d["cidade"], set()).add(d["bairro"])
    bairros_por_cidade = {c: sorted(b) for c, b in sorted(bairros_por_cidade.items())}
    json_bairros = json.dumps(bairros_por_cidade, ensure_ascii=False)

    # Geometria do mapa: só os bairros que a rodada realmente trouxe. O cache
    # acumula (geo/bairros.json guarda tudo que já foi buscado), mas desenhar
    # bairro sem anúncio nenhum encheria a tela de polígono cinza e faria a
    # região parecer vazia quando o vazio é do recorte, não da cidade.
    presentes = {f"{d['cidade']}|{d['bairro']}"
                 for d in dados if d["cidade"] and d["bairro"]}
    cache_geo = {k: v for k, v in geo.carregar().items() if k in presentes}
    mapa_svg, mapa_centros = mapa.caminhos(cache_geo)
    json_centros = json.dumps(mapa_centros, ensure_ascii=False)

    ic = design.ICONES
    hoje = date.today().strftime("%d/%m/%Y")
    # Hora da rodada em BRT. O runner do Actions roda em UTC e o dashboard é
    # lido no Recife: carimbar UTC faria a rodada das 08:13 aparecer como
    # 11:13. Offset fixo porque o Brasil não tem horário de verão desde 2019
    # -- e zoneinfo exigiria tzdata no runner, dependência nova para resolver
    # um fuso que não muda.
    agora_brt = datetime.now(timezone.utc) - timedelta(hours=3)
    atualizado_em = agora_brt.strftime("%d/%m às %H:%M")
    perfis = " · ".join(
        f"{c} {p['quartos_min']}+ qtos, {p['area_min']}m²+"
        for c, p in config.FILTROS_POR_CIDADE.items()
    )
    bairros = " · ".join(
        f"<b>{html.escape(c)}</b>: " + ", ".join(html.escape(b) for b in bs)
        for c, bs in config.BAIRROS_EXIBIDOS.items()
    )
    # Contagem do que o recorte de bairro escondeu. Aparece porque filtro
    # silencioso é indistinguível de fonte quebrada: sem a linha, uma rodada
    # ruim e uma lista de bairros estreita demais têm exatamente a mesma
    # cara -- poucos imóveis e nenhuma explicação.
    linha_ocultos = ""
    if ocultos and (ocultos.get("fora") or ocultos.get("sem_bairro")):
        partes = []
        if ocultos.get("fora"):
            partes.append(f"{ocultos['fora']} em outros bairros")
        if ocultos.get("sem_bairro"):
            partes.append(f"{ocultos['sem_bairro']} sem bairro informado")
        linha_ocultos = (
            "<div><dt>Fora dos bairros sugeridos</dt><dd>"
            f"{' · '.join(partes)}. A coleta cobre a cidade inteira e o "
            "arquivo carrega tudo: a lista de bairros acima é só a sugestão "
            "que já vem marcada em <b>Filtros → Bairro</b>. Desmarque para ver "
            "o resto, ou use <b>Limpar</b>.</dd></div>"
        )

    html_final = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0D1114" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<!-- As fotos vêm do CDN de cada portal. Servidas de jlfig13.github.io, o
     navegador manda o Referer e boa parte dos CDNs recusa hotlink de outra
     origem -- o card caía no marcador cinza mesmo com a URL correta no
     banco. Sem Referer a imagem é servida como acesso direto. -->
<meta name="referrer" content="no-referrer">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" media="all"
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
<title>Monitor de Apartamentos — Recife e Olinda</title>
<style>{design.CSS_TOKENS}{design.CSS_BASE}</style>
</head>
<body>

<header class="topo">
  <div class="topo-linha">
    <div class="marca">
      <span class="marca-glifo">{ic['marca']}</span>
      <span>Monitor de Apartamentos</span>
      <span class="marca-sub">{atualizado_em}</span>
    </div>
    <div class="topo-dir">
      <button class="btn-obs" id="btn-obs" type="button" aria-expanded="false"
              aria-controls="observacoes">
        {ic['info']} <span class="btn-obs-txt">Observações</span>
      </button>
      <button class="btn-tema" id="btn-tema" type="button"
              aria-label="Alternar modo claro e escuro" title="Alternar tema">
        <span id="ic-tema">{ic['lua']}</span>
      </button>
    </div>
  </div>
</header>

<div class="pagina">

  <!-- O que estava no rodapé: quem lia no celular precisava rolar a lista
       inteira para descobrir por que um imóvel não aparecia. Aqui em cima,
       fechado por padrão, fica a um toque de distância. -->
  <section class="obs" id="observacoes" hidden aria-label="Observações da rodada">
    <dl class="obs-lista">
      <div><dt>Preço</dt><dd>até {_fmt_preco(config.FILTROS['preco_max'])}
        {'(sem piso)' if not config.FILTROS['preco_min'] else
         'a partir de ' + _fmt_preco(config.FILTROS['preco_min'])}</dd></div>
      <div><dt>Perfil</dt><dd>{perfis}</dd></div>
      <div><dt>Idade do anúncio</dt><dd>mais de {config.MAX_DIAS_DESDE_ATUALIZACAO}
        dias sem atualização é descartado (quando a fonte informa a data)</dd></div>
      <div><dt>Bairros exibidos</dt><dd>{bairros}</dd></div>
      {linha_ocultos}
      <div><dt>Preço mostrado</dt><dd>o MENOR entre as fontes do mesmo imóvel —
        é o que se paga de fato. "{NAO_LOCALIZADO}" marca dado que a fonte não
        informou.</dd></div>
    </dl>
  </section>

  <!-- Desenhado em JS: os números mudam com o escopo (meus bairros / todos),
       e um pulso fixo diria "19 imóveis" numa tela mostrando 45. -->
  <section class="pulso" id="pulso" aria-label="Resumo da busca"></section>
  <p class="pulso-sec" id="pulso-sec"></p>

  <div class="escopo" role="group" aria-label="Recorte da lista">
    <button class="chip-escopo" id="e-todos" type="button" aria-pressed="true">
      {ic['casa']} Todos <span class="chip-n" id="n-todos"></span></button>
    <button class="chip-escopo" id="e-favoritos" type="button" aria-pressed="false">
      {ic['estrela']} Favoritos <span class="chip-n" id="n-favoritos"></span></button>
    <button class="chip-escopo" id="e-lixeira" type="button" aria-pressed="false">
      {ic['lixeira']} Lixeira <span class="chip-n" id="n-lixeira"></span></button>
  </div>

  <p class="aviso-armazenamento" id="aviso-armazenamento" hidden>
    {ic['info']} <span>Este navegador está bloqueando os dados deste site.
    Favoritos e descartes valem só até fechar a página — use
    <b>Baixar backup</b> e me mande o arquivo para gravar no repositório.</span>
  </p>

  <div class="triagem-backup" id="triagem-backup" hidden>
    <span class="backup-rot">Triagem</span>
    <button class="btn-backup" id="btn-baixar" type="button">Baixar backup</button>
    <label class="btn-backup">Restaurar
      <input type="file" id="inp-restaurar" accept="application/json" hidden>
    </label>
    <span class="backup-nota" id="backup-nota"></span>
  </div>

  <div class="barra-filtros" id="barra-filtros">
    <button class="btn-filtros" id="btn-filtros" type="button"
            aria-expanded="false" aria-controls="filtros">
      {ic['filtro']} Filtros
      <span class="filtros-n" id="filtros-n" hidden></span>
      <span class="seta">{ic['seta']}</span>
    </button>
    <span class="contagem" id="contagem"></span>
  </div>

  <div class="filtros" id="filtros" hidden>
    <!-- Contagem preenchida em JS: ela precisa acompanhar o escopo e os
         descartes. Fixa no HTML, o chip dizia "Novos 4" numa tela com 1. -->
    <button class="chip" id="c-novos" type="button" aria-pressed="false">
      Novos <span class="chip-n" id="cn-novos"></span></button>
    <button class="chip" id="c-quedas" type="button" aria-pressed="false">
      Baixaram <span class="chip-n" id="cn-quedas"></span></button>
    <button class="chip" id="c-multi" type="button" aria-pressed="false">
      Confirmados <span class="chip-n" id="cn-multi"></span></button>

    <!-- Cidade e bairro aceitam VÁRIOS. Era um <select> de escolha única, e
         a seleção múltipla morava num painel "Preferências" separado, que
         recortava o catálogo em dois baldes ("Minhas preferências" / "Fora
         delas"). Relato: "o filtro da preferência tem q ser igual a esse, não
         um pré filtrado". Agora é um filtro só, e ele sabe fazer as duas
         coisas. -->
    <div class="campo-multi">
      <button class="btn-multi" id="btn-cidades" type="button"
              aria-expanded="false" aria-controls="lista-cidades">
        {ic['local']}<span id="rot-cidades">Cidade: todas</span>
        <span class="seta">{ic['seta']}</span>
      </button>
      <div class="chips-multi" id="lista-cidades" hidden></div>
    </div>
    <div class="campo-multi">
      <button class="btn-multi" id="btn-bairros" type="button"
              aria-expanded="false" aria-controls="lista-bairros">
        <span id="rot-bairros">Bairro: todos</span>
        <span class="seta">{ic['seta']}</span>
      </button>
      <div class="chips-multi" id="lista-bairros" hidden></div>
    </div>
    <label class="campo">{ic['filtro']}
      <select id="f-quartos" aria-label="Quartos mínimos">
        <option value="0">Quartos</option><option value="1">1+</option>
        <option value="2">2+</option><option value="3">3+</option><option value="4">4+</option>
      </select>
    </label>
    <label class="campo preco">{ic['moeda']}
      <input id="f-min" type="number" inputmode="numeric" placeholder="mín" aria-label="Preço mínimo">
      <span class="sep">–</span>
      <input id="f-max" type="number" inputmode="numeric" placeholder="máx" aria-label="Preço máximo">
    </label>
    <!-- Área estava só no painel de preferências. Sumir com o painel não pode
         custar a funcionalidade: ela desce para cá. -->
    <label class="campo preco">
      <input id="f-area-min" type="number" inputmode="numeric" placeholder="m² mín"
             aria-label="Área mínima">
      <span class="sep">–</span>
      <input id="f-area-max" type="number" inputmode="numeric" placeholder="m² máx"
             aria-label="Área máxima">
    </label>
    <label class="campo busca">{ic['busca']}
      <input id="f-busca" type="search" placeholder="bairro, rua, fonte…" aria-label="Busca livre">
    </label>
    <label class="campo">
      <select id="f-ordem" aria-label="Ordenação">
        <option value="relevancia">Sugeridos para você</option>
        <option value="preco">Menor preço</option>
        <option value="m2">Melhor R$/m²</option>
        <option value="area">Maior área</option>
        <option value="tempo">Mais recentes no mercado</option>
      </select>
    </label>
    <button class="btn-limpar" id="btn-limpar" type="button">Limpar</button>

    <!-- "Preferência" deixou de ser um recorte paralelo e virou o que sempre
         devia ter sido: este filtro, guardado. Salva no navegador e volta
         aplicado na próxima abertura, nos MESMOS campos acima -- visíveis e
         editáveis, com "Limpar" mostrando tudo. -->
    <div class="filtros-rodape">
      <button class="btn-mini" id="btn-salvar-pref" type="button">
        {ic['estrela']} Salvar como meu padrão</button>
      <button class="btn-mini" id="btn-usar-pref" type="button">Usar meu padrão</button>
      <button class="btn-mini" id="btn-pref-padrao" type="button">Restaurar sugerido</button>
      <span class="prefs-conta" id="pref-nota"></span>
    </div>
  </div>

  <nav class="abas" role="tablist">
    <button class="aba" id="aba-imoveis" role="tab" aria-selected="true"
            aria-controls="painel-imoveis" type="button">
      Imóveis <span class="aba-n" id="n-aba-imoveis">{len(dados)}</span></button>
    <button class="aba" id="aba-mapa" role="tab" aria-selected="false"
            aria-controls="painel-mapa" type="button">
      Mapa <span class="aba-n">{len(mapa_centros)}</span></button>
    <button class="aba" id="aba-fontes" role="tab" aria-selected="false"
            aria-controls="painel-fontes" type="button">
      Fontes <span class="aba-n">{len(rendimento or [])}</span></button>
  </nav>

  <section id="painel-imoveis" role="tabpanel" aria-labelledby="aba-imoveis">
    <div id="lista" class="lista"></div>
  </section>

  <section id="painel-mapa" role="tabpanel" aria-labelledby="aba-mapa" hidden>
    {_painel_mapa(mapa_svg)}
  </section>

  <section id="painel-fontes" role="tabpanel" aria-labelledby="aba-fontes" hidden>
    <div class="rend">{_painel_rendimento(rendimento)}</div>
    {_painel_saude(saude)}
  </section>

  <footer class="rodape">
    Atualizado em {atualizado_em} (BRT) · {len(dados)} imóveis exibidos
  </footer>
</div>

<script>
const DADOS = {json_dados};
const NAO_LOC = {json.dumps(NAO_LOCALIZADO)};
const PREFS_PADRAO = {json_prefs};
const BAIRROS_POR_CIDADE = {json_bairros};
const MAPA_CENTROS = {json_centros};
const IC = {json.dumps({k: v for k, v in ic.items() if k in ('local', 'externo', 'vazio', 'sol', 'lua', 'foto', 'seta',
                        'estrela', 'descartar', 'restaurar', 'lixeira',
                        'casa', 'mais', 'baixou')}, ensure_ascii=False)};

/* ---------- tema ---------- */
const raiz = document.documentElement;
const btnTema = document.getElementById('btn-tema');
const icTema = document.getElementById('ic-tema');
function escuroAtivo(){{
  const t = raiz.getAttribute('data-tema');
  if (t) return t === 'escuro';
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}}
function pintarIcone(){{ icTema.innerHTML = escuroAtivo() ? IC.sol : IC.lua; }}
try {{
  const salvo = localStorage.getItem('tema');
  if (salvo) raiz.setAttribute('data-tema', salvo);
}} catch (e) {{}}
pintarIcone();
btnTema.addEventListener('click', () => {{
  const novo = escuroAtivo() ? 'claro' : 'escuro';
  raiz.setAttribute('data-tema', novo);
  try {{ localStorage.setItem('tema', novo); }} catch (e) {{}}
  pintarIcone();
}});

/* ---------- utilidades ---------- */
const esc = s => (s == null ? '' : String(s)).replace(/[&<>"']/g,
  c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const num = v => v == null ? null : Number(v);
const brl = v => 'R$ ' + Number(v).toLocaleString('pt-BR', {{maximumFractionDigits:0}});

/* Faixa de preço: mostra a trajetória sem ocupar espaço de gráfico.
   Verde quando desceu, âmbar quando subiu -- cor só quando há movimento. */
/* Trajetória do preço em miniatura.

   Exige TRÊS pontos: com dois, a "tendência" é uma reta ligando início e
   fim -- que é exatamente o que o selo "Baixou R$ X" já diz, só que em
   forma de risco atravessando o card. Era o caso da maioria dos imóveis, e
   o desenho solto ao lado do título parecia defeito de render.

   Também precisa de variação real: série de preço parado vira uma linha
   horizontal, ruído puro. */
function faixa(hist){{
  if (!hist) return '';
  const p = hist.map(h => h[1]).filter(v => v != null);
  if (p.length < 3) return '';
  const mn = Math.min(...p), mx = Math.max(...p);
  if (mx === mn) return '';

  const W = 64, H = 16, n = p.length, rg = mx - mn;
  const y = v => (H - 2 - (v - mn) / rg * (H - 4)).toFixed(1);
  const pts = p.map((v, i) => `${{(i / (n - 1) * W).toFixed(1)}},${{y(v)}}`).join(' ');
  const cor = p[n-1] < p[0] ? 'var(--bom)' : (p[n-1] > p[0] ? 'var(--atencao)' : 'var(--tinta-fraca)');
  return `<svg class="faixa" viewBox="0 0 ${{W}} ${{H}}" aria-hidden="true">
    <polyline points="${{pts}}" fill="none" stroke="${{cor}}" stroke-width="1.5"
      stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${{W}}" cy="${{y(p[n-1])}}" r="1.8" fill="${{cor}}"/></svg>`;
}}

/* ---------- recorte ----------
   Já foram dois recortes concorrentes: uma barra de filtros e, por fora dela,
   um par de botões "Minhas preferências" / "Fora delas" que dividia o
   catálogo em dois baldes exclusivos. A tela dizia "8 imóveis" com 388 no
   catálogo, e a barra de filtros não tinha nada que explicasse a diferença.
   Relato: "o filtro da preferência tem q ser igual a esse, não um pré
   filtrado".

   Agora é um recorte só, e ele está inteiro na barra de filtros. Sobrou aqui
   o que é recorte de LISTA e não de busca: tudo, favoritos, lixeira.

   O recorte é do usuário, não do robô: a coleta cobre a cidade inteira e o
   arquivo carrega tudo, então mudar de ideia é instantâneo. */
const el = id => document.getElementById(id);
let escopo = 'todos';

/* ---------- triagem: favoritos e descartados ----------
   A chave é a URL do ANÚNCIO, não o id do imóvel. db.consolidar_imoveis()
   apaga e reconstrói a tabela `imovel` a cada rodada -- os agrupamentos mudam
   quando anúncios entram e saem --, então o id de hoje não é o de amanhã, e
   uma lista chaveada por ele esqueceria tudo em 12 horas.

   O imóvel conta como marcado se QUALQUER anúncio dele estiver na lista. Isso
   resolve de graça os dois casos que quebrariam a versão ingênua: o imóvel
   ganhar uma segunda fonte depois de descartado (regrupamento), e o anúncio
   sumir de um portal e voltar por outro.

   localStorage é por navegador: descartar no celular não reflete no desktop.
   Sem servidor não há como fazer diferente, e a alternativa (commitar a lista
   no repositório a cada rodada) daria conflito garantido. O try/catch é o
   mesmo cuidado do tema -- em file:// o acesso pode levantar exceção, e a
   triagem não pode custar o dashboard. */
/* Sonda de escrita. A primeira versão engolia a falha num catch vazio, e o
   resultado foi o pior comportamento possível: navegador que bloqueia dados de
   site aceitava a marcação na tela e perdia tudo na recarga, sem uma palavra.
   Falha silenciosa em persistência é pior que funcionalidade ausente -- a
   pessoa confia na marcação e refaz a triagem toda no dia seguinte. */
let ARMAZENAMENTO_OK = false;
try {{
  const sonda = '__sonda__';
  localStorage.setItem(sonda, '1');
  ARMAZENAMENTO_OK = localStorage.getItem(sonda) === '1';
  localStorage.removeItem(sonda);
}} catch (e) {{ ARMAZENAMENTO_OK = false; }}

function lerLista(chave){{
  try {{
    const cru = localStorage.getItem(chave);
    return cru ? JSON.parse(cru) : {{}};
  }} catch (e) {{ return {{}}; }}
}}
function gravarLista(chave, obj){{
  try {{ localStorage.setItem(chave, JSON.stringify(obj)); }} catch (e) {{
    ARMAZENAMENTO_OK = false;
    pintarAvisoArmazenamento();
  }}
}}

/* Semente versionada: o que estiver em saida/triagem.json entra como estado
   inicial, vindo embutido no HTML. É a única parte da triagem que sobrevive a
   troca de aparelho e a limpeza de dados do navegador, porque mora no
   repositório e não no telefone. O localStorage continua por cima, para a
   marcação do dia valer na hora, sem esperar rodada. */
const SEMENTE = {json_semente};

function unir(semente, local){{
  const r = Object.assign({{}}, semente);
  for (const k in local) r[k] = local[k];
  return r;
}}

let DESCARTADOS = unir(SEMENTE.descartados || {{}}, lerLista('descartados'));
let FAVORITOS = unir(SEMENTE.favoritos || {{}}, lerLista('favoritos'));

const chavesDe = d => (d.anuncios || []).map(a => a.url).filter(Boolean);
const marcado = (d, lista) => chavesDe(d).some(u => u in lista);
const descartado = d => marcado(d, DESCARTADOS);
const favorito = d => marcado(d, FAVORITOS);

function alternar(d, chave, lista){{
  const urls = chavesDe(d);
  const ligado = urls.some(u => u in lista);
  // Grava TODAS as urls do imóvel, não só a primeira: amanhã o agrupamento
  // pode quebrar em dois, e cada pedaço precisa lembrar da decisão.
  if (ligado) urls.forEach(u => delete lista[u]);
  else urls.forEach(u => {{ lista[u] = new Date().toISOString().slice(0,10); }});
  gravarLista(chave, lista);
  return !ligado;
}}

/* ---------- preferências ----------
   Até 05/09/2026 o recorte era decidido no Python (config.BAIRROS_EXIBIDOS) e
   chegava pronto em cada item, como `noRecorte`. Isso tornava impossível o que
   se pede aqui: mudar de ideia sem esperar a próxima rodada. Agora o Python
   manda o UNIVERSO (tudo que a coleta trouxe) e o recorte acontece na tela.

   O envelope de coleta continua sendo o limite duro: nada fora dele existe no
   arquivo, e por isso ele foi alargado junto (config.FILTROS). */
function lerPrefs(){{
  const salvo = lerLista('preferencias');
  // Object.assign e não spread aninhado: preferência salva com versão antiga
  // do arquivo pode não ter todas as chaves, e faltar chave tem de cair no
  // padrão em vez de virar undefined no meio de uma comparação.
  return Object.assign({{}}, PREFS_PADRAO, salvo || {{}});
}}
let PREFS = lerPrefs();

function gravarPrefs(){{
  gravarLista('preferencias', PREFS);
}}

/* Descartado sai das contagens -- senão o número do topo volta a discordar do
   que está na tela, que é o problema que a contagem dinâmica veio resolver.
   Favorito NÃO some da lista: continua onde está, com a estrela acesa.

   Não há mais escopo de preferência aqui. Ele existia como um TERCEIRO
   recorte, invisível na barra de filtros: a tela dizia "8 imóveis" e o
   catálogo tinha 388, com um balde "Fora delas" do lado. Relato: "o filtro
   da preferência tem q ser igual a esse, não um pré filtrado". A preferência
   virou o estado salvo do próprio filtro -- o que está na tela é o que
   filtra. */
function noEscopo(d){{
  if (escopo === 'lixeira') return descartado(d);
  if (descartado(d)) return false;
  if (escopo === 'favoritos') return favorito(d);
  return true;
}}

/* ---------- filtros ----------
   Um filtro só. Cidade e bairro guardam LISTAS: era escolha única, e a
   seleção múltipla morava num painel de preferências que recortava o
   catálogo por fora da barra. */
const selQuartos = el('f-quartos');
const selOrdem = el('f-ordem'), inpMin = el('f-min'), inpMax = el('f-max');
const inpAreaMin = el('f-area-min'), inpAreaMax = el('f-area-max');
const inpBusca = el('f-busca');
const chips = {{novos: el('c-novos'), quedas: el('c-quedas'), multi: el('c-multi')}};

// Listas vazias querem dizer "qualquer um". Isso é melhor que marcar as 11
// cidades de hoje: cidade ou bairro que aparecer amanhã entra sozinho, em vez
// de ficar de fora por ter nascido depois da escolha.
let FCidades = [], FBairros = [];

function alternar(lista, v){{
  const i = lista.indexOf(v);
  if (i >= 0) lista.splice(i, 1); else lista.push(v);
}}

function rotuloMulti(lista, singularVazio, nome){{
  if (!lista.length) return singularVazio;
  if (lista.length === 1) return nome + ': ' + lista[0];
  return nome + ': ' + lista.length + ' escolhidos';
}}

function chipMulti(rot, ligado){{
  return `<button class="chip-pref" type="button" data-v="${{esc(rot)}}"
           aria-pressed="${{ligado}}">${{esc(rot)}}</button>`;
}}

function desenharMulti(){{
  const cidades = Object.keys(BAIRROS_POR_CIDADE);
  el('lista-cidades').innerHTML = cidades
    .map(c => chipMulti(c, FCidades.includes(c))).join('');

  // Só os bairros das cidades escolhidas: a lista inteira das 11 cidades
  // seria uma parede de chips onde ninguém acha o próprio bairro.
  const doEscolhido = FCidades.length ? FCidades : cidades;
  const bairros = [...new Set(doEscolhido
    .flatMap(c => BAIRROS_POR_CIDADE[c] || []))].sort();
  // Bairro escolhido cuja cidade saiu da seleção sairia da tela e continuaria
  // filtrando em silêncio -- a lista encolheria sem nada explicando por quê.
  FBairros = FBairros.filter(b => bairros.includes(b));
  el('lista-bairros').innerHTML = bairros
    .map(b => chipMulti(b, FBairros.includes(b))).join('');

  el('rot-cidades').textContent = rotuloMulti(FCidades, 'Cidade: todas', 'Cidade');
  el('rot-bairros').textContent = rotuloMulti(FBairros, 'Bairro: todos', 'Bairro');
}}

/* Delegação: os chips são redesenhados a cada mudança, então ouvir no
   contêiner evita religar dezenas de handlers a cada toque. */
function ligarMulti(idLista, obterLista){{
  el(idLista).addEventListener('click', ev => {{
    const b = ev.target.closest('.chip-pref');
    if (!b) return;
    alternar(obterLista(), b.dataset.v);
    desenharMulti();
    render();
    pintarPulso();
  }});
}}
ligarMulti('lista-cidades', () => FCidades);
ligarMulti('lista-bairros', () => FBairros);

function abrirMulti(botao, lista, abrir){{
  botao.setAttribute('aria-expanded', String(abrir));
  el(lista).hidden = !abrir;
}}
for (const [bid, lid] of [['btn-cidades','lista-cidades'], ['btn-bairros','lista-bairros']]){{
  el(bid).addEventListener('click', () => {{
    const aberto = el(bid).getAttribute('aria-expanded') === 'true';
    abrirMulti(el(bid), lid, !aberto);
  }});
}}

Object.values(chips).forEach(c => c.addEventListener('click', () => {{
  c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
  render();
  pintarPulso();  // o pulso espelha os chips: os dois têm de contar a mesma coisa
}}));

// `num` já existe para valor solto; este lê CAMPO, e campo vazio é "sem
// limite", não zero.
function numCampo(campo){{
  const v = (campo.value || '').trim();
  return v === '' ? null : parseFloat(v);
}}

/* Duas variações do MESMO filtro, e nenhuma delas é um recorte escondido:

   `semLocal` é para o mapa. O mapa É o seletor de bairro; pintar só o bairro
   já escolhido tornaria a comparação impossível, porque todo o resto viraria
   cinza no instante da escolha. Ele pinta com o recorte inteiro MENOS
   cidade/bairro.

   `semChips` é para o pulso. "Novos hoje" precisa contar dentro do filtro
   atual, senão o número no topo e a lista embaixo discordam -- mas contando
   COM o chip ligado ele viraria a própria contagem dele. */
function filtrar(opcoes){{
  const o = opcoes || {{}};
  const qMin = parseInt(selQuartos.value || '0', 10);
  const cidades = o.semLocal ? [] : FCidades;
  const bairros = o.semLocal ? [] : FBairros;
  const mn = numCampo(inpMin), mx = numCampo(inpMax);
  const aMin = numCampo(inpAreaMin), aMax = numCampo(inpAreaMax);
  const q = (inpBusca.value || '').trim().toLowerCase();
  const lig = k => !o.semChips && chips[k].getAttribute('aria-pressed') === 'true';
  const soNovos = lig('novos'), soQuedas = lig('quedas'), soMulti = lig('multi');

  return DADOS.filter(d => {{
    if (!noEscopo(d)) return false;
    if (soNovos && !d.novo) return false;
    if (soQuedas && !d.queda) return false;
    if (soMulti && d.qtdFontes < 2) return false;
    if (qMin > 0 && (!d.quartos || d.quartos < qMin)) return false;
    if (cidades.length && !cidades.includes(d.cidade)) return false;
    // Bairro vazio no imóvel não é excluído por escolha de bairro: "não sei o
    // bairro" não é "bairro errado" -- é a mesma regra de três estados do
    // filtro de coleta, e some-lo esconderia imóvel por falta de dado.
    if (bairros.length && d.bairro && !bairros.includes(d.bairro)) return false;
    if (mn != null && (d.preco == null || d.preco < mn)) return false;
    if (mx != null && (d.preco == null || d.preco > mx)) return false;
    // Área ausente NÃO exclui, pelo mesmo motivo.
    if (aMin != null && d.area != null && d.area < aMin) return false;
    if (aMax != null && d.area != null && d.area > aMax) return false;
    if (q) {{
      const alvo = [d.titulo, d.bairro, d.cidade, d.logradouro, d.sites.join(' ')]
        .join(' ').toLowerCase();
      if (!alvo.includes(q)) return false;
    }}
    return true;
  }});
}}

function ordenar(lista){{
  const o = selOrdem.value;
  const c = [...lista];
  if (o === 'preco') return c.sort((a,b) => (a.preco ?? 1e9) - (b.preco ?? 1e9));
  if (o === 'm2') return c.sort((a,b) => (a.precoM2 ?? 1e9) - (b.precoM2 ?? 1e9));
  if (o === 'area') return c.sort((a,b) => (b.area ?? 0) - (a.area ?? 0));
  if (o === 'tempo') return c.sort((a,b) => (a.diasAnunciado ?? 1e9) - (b.diasAnunciado ?? 1e9));
  // Sugestão: nota de afinidade primeiro (config.PERFIL), empate desfeito
  // por novidade e preço. Era "novo primeiro" puro -- que colocava na frente
  // qualquer anúncio recém-publicado, inclusive o que não serve.
  // 'queda' entra logo depois de 'novo': baixar de preço é a outra notícia
  // do dia, e sem isto um imóvel que caiu R$ 300 podia parar no meio da
  // lista -- o selo existia e ninguém rolava até ele.
  return c.sort((a,b) =>
    ((b.atende ? 1 : 0) - (a.atende ? 1 : 0)) ||
    ((b.melhor ? 1 : 0) - (a.melhor ? 1 : 0)) ||
    ((b.score ?? 0) - (a.score ?? 0)) ||
    (b.novo - a.novo) ||
    ((b.queda ? 1 : 0) - (a.queda ? 1 : 0)) ||
    ((a.preco ?? 1e9) - (b.preco ?? 1e9)));
}}

/* ---------- pulso ---------- */
const pulso = el('pulso');
const fmtBRL = v => v == null ? '—' : 'R$ ' + Number(v).toLocaleString('pt-BR',
  {{maximumFractionDigits:0}});

function pintarPulso(){{
  /* A base do pulso é o FILTRO ATUAL, sem os três chips. Era o escopo inteiro
     (o catálogo, ou a antiga preferência): com um filtro só, isso passaria a
     dizer "Novos hoje 12" numa tela com 8 imóveis. Sem os chips porque, com
     eles, o contador de "Novos" viraria a contagem dele mesmo depois de
     ligado -- sempre igual ao tamanho da lista. */
  const base = filtrar({{semChips: true}});
  const novos = base.filter(d => d.novo).length;
  const quedas = base.filter(d => d.queda).length;
  const multi = base.filter(d => d.qtdFontes > 1).length;
  const m2 = base.map(d => d.precoM2).filter(v => v != null).sort((a,b) => a-b);
  const mediana = m2.length ? m2[Math.floor(m2.length/2)].toFixed(0) : '—';
  const precos = base.map(d => d.preco).filter(v => v != null);
  const faixa = precos.length
    ? `${{fmtBRL(Math.min(...precos))}}<small> a ${{fmtBRL(Math.max(...precos))}}</small>`
    : '—';

  const icone = (nome, classe) => nome
    ? `<div class="pulso-icone ${{classe || ''}}">${{IC[nome]}}</div>` : '';

  const item = (rot, val, destaque, ic, classe) =>
    `<div class="pulso-item${{destaque ? ' destaque' : ''}}">${{icone(ic, classe)}}
       <div><div class="pulso-rot">${{rot}}</div>
       <div class="pulso-val">${{val}}</div></div></div>`;

  /* "Novos hoje" e "Baixaram" são os dois números que respondem "o que mudou
     desde ontem" -- e eram os únicos sem resposta: o contador dizia 3 e não
     havia como chegar nos três, porque o filtro correspondente mora dentro do
     painel recolhido. Aqui o número É o filtro. */
  const acao = (rot, val, chip, ic, classe) =>
    `<button class="pulso-item acionavel" type="button" data-chip="${{chip}}"
             aria-pressed="${{chips[chip].getAttribute('aria-pressed')}}">
       ${{icone(ic, classe)}}
       <div><div class="pulso-rot">${{rot}}</div>
       <div class="pulso-val">${{val}}</div></div></button>`;

  // o contador da aba acompanha o filtro: dizer "54" com 16 na tela faria
  // parecer que o filtro comeu imóvel
  el('n-aba-imoveis').textContent = filtrar().length;

  /* Três tiles, não seis. O design system mostra três, e há razão de sobra:
     seis cartões empilham em quatro linhas num telefone e empurram a lista
     de imóveis para fora da tela. Os três que viram tile são os que
     respondem "o que mudou desde ontem"; o resto é contexto e vai numa linha
     compacta, legível sem ocupar altura. */
  pulso.innerHTML =
    item('Imóveis', base.length, false, 'casa') +
    acao('Novos hoje', novos, 'novos', 'mais', 'novo') +
    acao('Baixaram', quedas, 'quedas', 'baixou', 'queda');

  el('pulso-sec').innerHTML =
    `<span><b>${{multi}}</b> multi-fonte</span>` +
    `<span>mediana <b>${{mediana}}</b> R$/m²</span>` +
    `<span>${{faixa}}</span>`;

  pulso.querySelectorAll('.acionavel').forEach(b =>
    b.addEventListener('click', () => ligarChip(b.dataset.chip)));

  // as contagens dos chips vivem na mesma base do pulso: um número só,
  // calculado num lugar só
  el('cn-novos').textContent = novos;
  el('cn-quedas').textContent = quedas;
  el('cn-multi').textContent = multi;
}}

/* ---------- armazenamento: avisar em vez de perder em silêncio ---------- */
function pintarAvisoArmazenamento(){{
  el('aviso-armazenamento').hidden = ARMAZENAMENTO_OK;
}}

/* Backup só aparece em Favoritos e Lixeira: é onde a pergunta "e se eu perder
   isso?" existe. Na lista do dia seria mais um botão a ignorar. */
function pintarBackup(){{
  el('triagem-backup').hidden = !(escopo === 'favoritos' || escopo === 'lixeira');
}}

function nota(txt){{
  const n = el('backup-nota');
  n.textContent = txt;
  setTimeout(() => {{ if (n.textContent === txt) n.textContent = ''; }}, 6000);
}}

/* O arquivo baixado tem a MESMA forma que o dashboard lê como semente
   (triagem.json na raiz do repositório). Assim o backup não é só um consolo:
   é o caminho para tornar a triagem permanente e válida em qualquer aparelho
   -- basta o arquivo entrar no repositório. */
el('btn-baixar').addEventListener('click', () => {{
  const conteudo = JSON.stringify(
    {{favoritos: FAVORITOS, descartados: DESCARTADOS}}, null, 2);
  const url = URL.createObjectURL(new Blob([conteudo], {{type: 'application/json'}}));
  const a = document.createElement('a');
  a.href = url; a.download = 'triagem.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  const n = Object.keys(FAVORITOS).length + Object.keys(DESCARTADOS).length;
  nota(`${{n}} marcação(ões) no arquivo`);
}});

el('inp-restaurar').addEventListener('change', ev => {{
  const arq = ev.target.files && ev.target.files[0];
  if (!arq) return;
  const leitor = new FileReader();
  leitor.onload = () => {{
    let dados;
    try {{ dados = JSON.parse(leitor.result); }}
    catch (e) {{ nota('arquivo inválido'); return; }}
    // UNIÃO, não substituição: restaurar no aparelho novo não pode apagar o
    // que já foi marcado nele antes de lembrar do backup.
    FAVORITOS = unir(FAVORITOS, dados.favoritos || {{}});
    DESCARTADOS = unir(DESCARTADOS, dados.descartados || {{}});
    gravarLista('favoritos', FAVORITOS);
    gravarLista('descartados', DESCARTADOS);
    pintarEscopo(); pintarPulso(); render();
    nota('restaurado');
  }};
  leitor.readAsText(arq);
  ev.target.value = '';
}});

/* ---------- painel de preferências ---------- */
/* ---------- preferência = este filtro, guardado ----------
   Antes era um recorte paralelo, com campos próprios num painel separado e
   dois baldes no topo ("Minhas preferências" 8 / "Fora delas" 380). Quem
   olhava a barra de filtros não via nada que explicasse por que a tela
   mostrava 8 de 388. Agora a preferência não filtra nada por conta própria:
   ela só PREENCHE estes campos, que continuam visíveis e editáveis. */
const CAMPOS_PREF = [
  ['preco_min', 'f-min'], ['preco_max', 'f-max'],
  ['area_min', 'f-area-min'], ['area_max', 'f-area-max'],
];

function estadoDoFiltro(){{
  const p = {{cidades: [...FCidades], bairros: [...FBairros],
             quartos_min: Number(selQuartos.value) || 0}};
  for (const [chave, id] of CAMPOS_PREF){{
    const v = (el(id).value || '').trim();
    p[chave] = v === '' ? null : Number(v);
  }}
  return p;
}}

function aplicarNoFiltro(p){{
  FCidades = [...(p.cidades || [])];
  FBairros = [...(p.bairros || [])];
  selQuartos.value = String(p.quartos_min || 0);
  for (const [chave, id] of CAMPOS_PREF)
    el(id).value = p[chave] == null ? '' : p[chave];
  desenharMulti();
}}

function notaPref(txt){{
  const n = el('pref-nota');
  if (n) n.textContent = txt || '';
}}

el('btn-salvar-pref').addEventListener('click', () => {{
  PREFS = estadoDoFiltro();
  gravarPrefs();
  notaPref(ARMAZENAMENTO_OK
    ? 'Salvo. Abre assim da próxima vez.'
    : 'Este navegador bloqueia dados do site — não deu para salvar.');
}});

el('btn-usar-pref').addEventListener('click', () => {{
  aplicarNoFiltro(PREFS);
  notaPref('');
  render();
  pintarPulso();
}});

el('btn-pref-padrao').addEventListener('click', () => {{
  aplicarNoFiltro(PREFS_PADRAO);
  notaPref('Sugerido carregado. "Salvar como meu padrão" para guardar.');
  render();
  pintarPulso();
}});

/* Liga (ou desliga) um chip e leva o olho até a lista. Sem a rolagem, no
   celular o clique no número não parece ter feito nada: o efeito acontece
   abaixo da dobra. */
function ligarChip(nome){{
  const c = chips[nome];
  c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
  render();
  pintarPulso();
  el('painel-imoveis').scrollIntoView({{behavior: 'smooth', block: 'start'}});
}}

/* Restaram os três recortes que são MESMO recortes de lista, e não filtro
   disfarçado: tudo, o que eu marquei, o que eu joguei fora. "Minhas
   preferências" e "Fora delas" saíram daqui -- eram filtro, e filtro mora na
   barra de filtros. */
const BOTOES_ESCOPO = {{
  todos: el('e-todos'),
  favoritos: el('e-favoritos'), lixeira: el('e-lixeira'),
}};

/* Os contadores descontam o que está na lixeira -- exceto o da própria
   lixeira. Deixar o descartado somando em "Todos" faria o chip prometer
   imóveis que a lista não mostra. */
function pintarEscopo(){{
  const vivos = DADOS.filter(d => !descartado(d));
  el('n-todos').textContent = vivos.length;
  el('n-favoritos').textContent = vivos.filter(favorito).length;
  el('n-lixeira').textContent = DADOS.filter(descartado).length;
}}

function trocarEscopo(novo){{
  escopo = novo;
  Object.entries(BOTOES_ESCOPO).forEach(([k, b]) =>
    b.setAttribute('aria-pressed', String(k === novo)));
  // a lista de bairros acompanha o escopo, senão sobra chip que não seleciona
  // nada
  desenharMulti();
  pintarEscopo();
  pintarBackup();
  pintarPulso();
  render();
}}
Object.entries(BOTOES_ESCOPO).forEach(([k, b]) =>
  b.addEventListener('click', () => trocarEscopo(k)));

/* ---------- render ---------- */
const lista = el('lista'), contagem = el('contagem');

/* Selos de ação (novo, queda) vão sobre a foto -- é o primeiro lugar
   onde o olho pousa no card. Os de contexto ficam no corpo. */
/* No máximo DOIS selos sobre a foto, por prioridade. Três empilhados em
   412px de largura não destacam nada -- viram uma faixa de etiquetas que o
   olho pula inteira. A ordem é a da urgência: o que mudou hoje (queda, novo)
   vem antes do que é verdade desde ontem (melhor achado).

   A queda leva o percentual junto: R$ 100 em 1.500 é outra conversa que
   R$ 100 em 2.500, e o valor sozinho não deixa decidir se vale abrir. */
function selosFoto(d){{
  const s = [];
  if (d.queda) s.push(`<span class="selo selo-queda">Baixou ${{brl(d.queda)}}${{
    d.quedaPct ? ' · ' + d.quedaPct + '%' : ''}}</span>`);
  if (d.novo) s.push('<span class="selo selo-novo">Novo</span>');
  if (d.melhor) s.push('<span class="selo selo-melhor">★ Melhor achado</span>');
  return s.slice(0, 2).join('');
}}

/* Favoritar e descartar. Ficam sobre a foto, no canto oposto aos selos. */
function acoesCard(d){{
  const fav = favorito(d);
  if (escopo === 'lixeira'){{
    return `<div class="acoes-card">
      <button class="btn-acao restaurar" type="button" title="Tirar da lixeira"
              aria-label="Restaurar imóvel">${{IC.restaurar}}</button></div>`;
  }}
  return `<div class="acoes-card">
    <button class="btn-acao favorito" type="button" aria-pressed="${{fav}}"
            title="${{fav ? 'Tirar dos favoritos' : 'Favoritar'}}"
            aria-label="Favoritar imóvel">${{IC.estrela}}</button>
    <button class="btn-acao descartar" type="button" title="Descartar"
            aria-label="Descartar imóvel">${{IC.descartar}}</button></div>`;
}}

function selos(d){{
  const s = [];
  if (d.qtdFontes > 1) s.push(`<span class="selo selo-fontes">${{d.qtdFontes}} fontes confirmam</span>`);
  if (d.economia > 0) s.push(`<span class="selo selo-economia">Economize ${{brl(d.economia)}}</span>`);
  if (!d.custoCompleto) s.push('<span class="selo selo-alerta" title="a fonte não informou o condomínio">Custo parcial</span>');
  if (d.conflitos.length) s.push(`<span class="selo selo-alerta">Fontes divergem: ${{esc(d.conflitos.join(', '))}}</span>`);
  if (d.diasAnunciado > 60) s.push(`<span class="selo">${{d.diasAnunciado}}d no mercado</span>`);
  // as fontes vêm por último: contexto, não chamada de atenção
  d.sites.forEach(f => s.push(`<span class="selo selo-fonte">${{esc(f)}}</span>`));
  return s.join('');
}}

/* Capa com galeria. Sem rede (ou sem foto na fonte) cai no marcador
   cinza: o dashboard tem de continuar legível offline, que é a premissa
   dele.

   Uma <img> só, trocando o src, em vez de um carrossel com as doze fotos
   no DOM. Com 19 cards, empilhar a galeria inteira seriam ~230 imagens
   pedidas de uma vez -- a lista levaria segundos para ficar utilizável no
   celular, para mostrar fotos que quase ninguém percorre. Aqui a segunda
   foto só é baixada quando alguém pede. */
function capa(d){{
  const fotos = d.fotos || [];
  const vazio = `<div class="foto-vazia">${{IC.foto}}</div>`;
  const img = fotos.length
    ? `<img src="${{esc(fotos[0])}}" alt="" loading="lazy" decoding="async"
         referrerpolicy="no-referrer"
         onerror="this.closest('.foto').classList.add('sem-foto')">`
    : '';
  const nav = fotos.length > 1
    ? `<button class="foto-nav ant" type="button" aria-label="Foto anterior">${{IC.seta}}</button>
       <button class="foto-nav prox" type="button" aria-label="Próxima foto">${{IC.seta}}</button>
       <span class="foto-conta">1/${{fotos.length}}</span>`
    : '';
  return `<div class="foto${{fotos.length ? '' : ' sem-foto'}}">${{vazio}}${{img}}${{nav}}
    <div class="foto-selos">${{selosFoto(d)}}</div>${{acoesCard(d)}}</div>`;
}}

/* Troca de foto no card já montado. */
function ligarGaleria(card, fotos){{
  if (fotos.length < 2) return;
  const img = card.querySelector('.foto img');
  const conta = card.querySelector('.foto-conta');
  let i = 0;
  const ir = passo => {{
    i = (i + passo + fotos.length) % fotos.length;
    img.src = fotos[i];
    conta.textContent = `${{i + 1}}/${{fotos.length}}`;
  }};
  card.querySelector('.foto-nav.ant').addEventListener('click', e => {{
    e.stopPropagation(); ir(-1);
  }});
  card.querySelector('.foto-nav.prox').addEventListener('click', e => {{
    e.stopPropagation(); ir(1);
  }});
}}

function ficha(d){{
  const p = [];
  if (d.quartos) p.push(`<span><b>${{d.quartos}}</b> quartos</span>`);
  if (d.area) p.push(`<span><b>${{d.area}}</b> m²</span>`);
  if (d.banheiros != null) p.push(`<span><b>${{d.banheiros}}</b> banh.</span>`);
  if (d.vagas != null) p.push(`<span><b>${{d.vagas}}</b> vaga${{d.vagas === 1 ? '' : 's'}}</span>`);
  if (d.andar != null) p.push(`<span><b>${{d.andar}}</b>º andar</span>`);
  return p.join('');
}}

/* Descartar sem rede de segurança é caro de usar: na dúvida, ninguém
   descarta, e a lista volta a acumular. O "Desfazer" aparece NO LUGAR do card
   que saiu -- não num toast de canto -- porque é onde o olho já está. Ele
   sobrevive até o próximo render, que é o tempo natural da decisão. */
function ligarTriagem(card, d){{
  const bFav = card.querySelector('.btn-acao.favorito');
  if (bFav) bFav.addEventListener('click', e => {{
    e.stopPropagation();
    const ligado = alternar(d, 'favoritos', FAVORITOS);
    bFav.setAttribute('aria-pressed', String(ligado));
    bFav.title = ligado ? 'Tirar dos favoritos' : 'Favoritar';
    pintarEscopo();
    // No escopo "Favoritos", desmarcar tem de tirar o card da tela na hora --
    // senão fica um card órfão que some só no próximo render.
    if (escopo === 'favoritos' && !ligado) render();
  }});

  const bDesc = card.querySelector('.btn-acao.descartar');
  if (bDesc) bDesc.addEventListener('click', e => {{
    e.stopPropagation();
    alternar(d, 'descartados', DESCARTADOS);
    trocarPorDesfazer(card, d);
  }});

  const bRest = card.querySelector('.btn-acao.restaurar');
  if (bRest) bRest.addEventListener('click', e => {{
    e.stopPropagation();
    alternar(d, 'descartados', DESCARTADOS);
    pintarEscopo(); pintarPulso(); render();
  }});
}}

function trocarPorDesfazer(card, d){{
  const aviso = document.createElement('div');
  aviso.className = 'desfazer';
  aviso.innerHTML = `<span>Descartado: <b>${{esc(d.titulo)}}</b></span>
    <button class="btn-desfazer" type="button">Desfazer</button>`;
  card.replaceWith(aviso);
  pintarEscopo();
  pintarPulso();
  atualizarContagem();
  aviso.querySelector('.btn-desfazer').addEventListener('click', () => {{
    alternar(d, 'descartados', DESCARTADOS);
    pintarEscopo(); pintarPulso(); render();
  }});
}}

/* A contagem da barra é recalculada fora do render porque o descarte tira um
   card sem redesenhar a lista -- e o número precisa acompanhar.
   O plural aparecia como "1 imóveis": passava despercebido numa lista de 19,
   mas a lixeira quase sempre tem um item só. */
const contar = (n, total) => {{
  // na forma "1 de 11" quem manda no plural é o TOTAL, não o recorte
  const palavra = v => v === 1 ? 'imóvel' : 'imóveis';
  return n === total ? `${{n}} ${{palavra(n)}}` : `${{n}} de ${{total}} ${{palavra(total)}}`;
}};

function atualizarContagem(){{
  contagem.textContent = contar(filtrar().length, DADOS.filter(noEscopo).length);
}}

function render(){{
  gravarUrl();
  contarFiltros();
  // o mapa é outra vista do MESMO recorte; deixá-lo de fora faria as duas
  // abas discordarem sobre quantos imóveis existem
  pintarMapa();
  const res = ordenar(filtrar());
  contagem.textContent = contar(res.length, DADOS.filter(noEscopo).length);

  lista.innerHTML = '';
  if (!res.length){{
    // A mensagem tem de dizer o que fazer, não só que está vazio: uma lixeira
    // vazia e um filtro estreito demais parecem a mesma tela sem isto.
    const vazio = {{
      lixeira: 'Nada descartado ainda. O ✕ sobre a foto tira o imóvel da lista.',
      favoritos: 'Nenhum favorito ainda. A estrela sobre a foto marca o que você gostou.',
    }}[escopo] || 'Nenhum imóvel com esses filtros.';
    lista.innerHTML = `<div class="estado-vazio">${{IC.vazio}}<div>${{vazio}}</div></div>`;
    return;
  }}

  const frag = document.createDocumentFragment();
  for (const d of res){{
    const card = document.createElement('article');
    card.className = 'imovel' + (descartado(d) ? ' descartado' : '');
    const local = [d.bairro, d.cidade].filter(Boolean).join(', ');
    const varias = d.anuncios.length > 1;

    card.innerHTML = `
      ${{capa(d)}}
      <div class="imovel-corpo">
        <div class="imovel-cab">
          <h3 class="imovel-titulo">${{esc(d.titulo)}}</h3>
        </div>
        <div class="imovel-local">${{IC.local}}<span>${{esc(local)}}</span>
          ${{d.logradouro
              ? `<span class="rua">· ${{esc(d.logradouro)}}</span>`
              : `<span class="rua rua-ausente">· endereço ${{NAO_LOC}}</span>`}}</div>
        <div class="ficha">${{ficha(d)}}</div>
        <div class="selos">${{selos(d)}}</div>
        ${{d.motivos.length
            ? `<div class="porque${{d.melhor ? ' destaque' : ''}}">${{
                 d.melhor ? IC.estrela : ''}} ${{esc(d.motivos.join(' · '))}}</div>`
            : ''}}
        <div class="imovel-rodape">
          <div class="preco-bloco">
            <div class="preco-val">${{esc(d.precoFmt)}}<span class="preco-un">/mês</span></div>
            ${{d.precoM2 ? `<span class="preco-m2">${{d.precoM2.toFixed(0)}} R$/m²</span>` : ''}}
            ${{faixa(d.historico)}}
          </div>
          <div class="acoes">
            ${{varias ? `<button class="btn-ofertas" type="button" aria-expanded="false">
                 <span class="seta">${{IC.seta}}</span> ${{d.anuncios.length}} ofertas</button>` : ''}}
            <a class="btn-abrir" href="${{esc(d.url)}}" target="_blank" rel="noopener">
              Ver anúncio ${{IC.externo}}</a>
          </div>
        </div>
      </div>`;

    ligarGaleria(card, d.fotos || []);
    ligarTriagem(card, d);

    // Progressive disclosure: só o imóvel com mais de uma oferta expande, e
    // a expansão vive DENTRO do card -- solta embaixo, parecia de outro
    // imóvel. Lista, não tabela: tabela obrigava rolagem horizontal.
    if (varias){{
      const painel = document.createElement('div');
      painel.className = 'ofertas';
      painel.hidden = true;
      painel.innerHTML = d.anuncios.map((o,i) => `
        <div class="oferta ${{i === 0 ? 'melhor' : ''}}">
          <span class="oferta-fonte">${{esc(o.site)}}${{
            i === 0 ? '<span class="marca-melhor">melhor</span>' : ''}}</span>
          <span class="oferta-preco">${{o.preco ? brl(o.preco) : NAO_LOC}}</span>
          <a class="oferta-link" href="${{esc(o.url)}}" target="_blank" rel="noopener">abrir</a>
          <span class="oferta-obs">${{o.custo_completo
              ? (o.condominio ? 'inclui condomínio ' + brl(o.condominio) : 'custo total')
              : 'sem condomínio informado'}}</span>
        </div>`).join('');
      card.appendChild(painel);

      const btn = card.querySelector('.btn-ofertas');
      btn.addEventListener('click', () => {{
        const aberto = btn.getAttribute('aria-expanded') === 'true';
        btn.setAttribute('aria-expanded', String(!aberto));
        painel.hidden = aberto;
      }});
    }}

    frag.appendChild(card);
  }}
  lista.appendChild(frag);
}}

[selQuartos, selOrdem].forEach(x => x.addEventListener('change', render));
[inpMin, inpMax, inpAreaMin, inpAreaMax].forEach(
  x => x.addEventListener('input', render));
inpBusca.addEventListener('input', render);

el('btn-limpar').addEventListener('click', () => {{
  // "Limpar" mostra TUDO -- inclusive o que a preferência salva escondia.
  // Antes ela era um escopo à parte e sobrevivia ao Limpar: a tela seguia com
  // um punhado de imóveis e o botão parecia quebrado.
  FCidades = []; FBairros = [];
  selQuartos.value = '0'; selOrdem.value = 'relevancia';
  inpMin.value = inpMax.value = '';
  inpAreaMin.value = inpAreaMax.value = inpBusca.value = '';
  Object.values(chips).forEach(c => c.setAttribute('aria-pressed', 'false'));
  notaPref('');
  desenharMulti(); render(); pintarPulso();
}});

/* ---------- barra de filtros ----------
   Recolhida por padrão: no celular os três chips mais seis campos comiam
   meia tela antes do primeiro imóvel. O contador no botão é o que evita o
   efeito colateral óbvio de esconder filtro -- sem ele, ninguém lembra que
   a lista está recortada, e uma busca estreita vira "o robô não achou
   nada". */
const btnFiltros = el('btn-filtros'), selo = el('filtros-n');

function contarFiltros(){{
  let n = 0;
  if (FCidades.length) n++;
  if (FBairros.length) n++;
  if (selQuartos.value && selQuartos.value !== '0') n++;
  if (inpMin.value) n++;
  if (inpMax.value) n++;
  if (inpAreaMin.value) n++;
  if (inpAreaMax.value) n++;
  if (inpBusca.value.trim()) n++;
  n += Object.values(chips).filter(
    c => c.getAttribute('aria-pressed') === 'true').length;
  selo.hidden = !n;
  selo.textContent = n;
  return n;
}}

function abrirFiltros(abrir){{
  btnFiltros.setAttribute('aria-expanded', String(abrir));
  filtrosEl.hidden = !abrir;
}}
btnFiltros.addEventListener('click', () => {{
  abrirFiltros(btnFiltros.getAttribute('aria-expanded') !== 'true');
}});

/* ---------- observações ---------- */
const btnObs = el('btn-obs'), painelObs = el('observacoes');
btnObs.addEventListener('click', () => {{
  const aberto = btnObs.getAttribute('aria-expanded') === 'true';
  btnObs.setAttribute('aria-expanded', String(!aberto));
  painelObs.hidden = aberto;
}});

/* ---------- mapa ----------
   Pinta cada bairro pelo R$/m² MEDIANO do recorte atual e devolve o clique
   como filtro. Mediana e não média: uma única cobertura puxa a média do
   bairro inteiro, e o mapa passaria a dizer que Casa Caiada é cara por causa
   de um anúncio.

   Corte por QUANTIL, não por faixa fixa de reais: faixa fixa empilharia quase
   todos os bairros num degrau só, porque os preços da região são próximos.
   Quantil garante que os cinco degraus sempre separam alguma coisa -- o mapa
   responde "mais caro que os vizinhos", que é a pergunta de quem procura onde
   morar. Custo: a cor é relativa ao recorte e muda quando o filtro muda; por
   isso a legenda diz os extremos em reais.

   Mínimo de 2 anúncios por bairro para colorir: com um só, a "mediana" É o
   anúncio, e um outlier pintaria o bairro inteiro. */
const MIN_ANUNCIOS_BAIRRO = 2;
const mapaSvg = document.querySelector('.mapa-svg');
const mapaDet = el('mapa-detalhe');
let mapaSelecionado = null;
// Enquadramento atual [x, y, largura, altura]. Deixa de ser o que o Python
// emitiu assim que o filtro escolhe cidade -- ver ajustarViewBox.
let VB = ((mapaSvg && mapaSvg.getAttribute('viewBox')) || '0 0 100 100')
  .split(' ').map(Number);

function mediana(v){{
  if (!v.length) return null;
  const o = [...v].sort((a,b) => a-b);
  const m = Math.floor(o.length / 2);
  return o.length % 2 ? o[m] : (o[m-1] + o[m]) / 2;
}}

function porBairro(lista){{
  const por = {{}};
  for (const d of lista){{
    if (!d.cidade || !d.bairro) continue;
    (por[d.cidade + '|' + d.bairro] ||= []).push(d);
  }}
  return por;
}}

function resumoBairro(itens){{
  return {{
    n: itens.length,
    m2: itens.length >= MIN_ANUNCIOS_BAIRRO
      ? mediana(itens.map(d => d.precoM2).filter(x => x != null)) : null,
    preco: mediana(itens.map(d => d.preco).filter(x => x != null)),
  }};
}}

function pintarMapa(){{
  if (!mapaSvg) return;
  const por = porBairro(filtrar({{semLocal: true}}));
  const resumo = {{}};
  for (const [k, itens] of Object.entries(por)) resumo[k] = resumoBairro(itens);

  const paths = mapaSvg.querySelectorAll('.mapa-bairro');
  const valores = [];
  paths.forEach(p => {{
    const v = resumo[p.dataset.b] && resumo[p.dataset.b].m2;
    if (v != null) valores.push(v);
  }});
  valores.sort((a,b) => a-b);

  const degrau = v => {{
    if (v == null || !valores.length) return '';
    const i = valores.indexOf(v);
    const pos = valores.length > 1 ? i / (valores.length - 1) : 0;
    return 'q' + Math.min(5, Math.floor(pos * 5) + 1);
  }};

  paths.forEach(p => {{
    const partes = p.dataset.b.split('|');
    const cid = partes[0], bai = partes[1];
    const info = resumo[p.dataset.b];
    p.setAttribute('class', 'mapa-bairro');
    const q = degrau(info && info.m2);
    if (q) p.classList.add(q);
    // fora da cidade escolhida o bairro esmaece, mas continua desenhado:
    // apagar mudaria a forma da região a cada filtro e tirava a referência
    if (FCidades.length && !FCidades.includes(cid)) p.classList.add('apagado');
    if (mapaSelecionado === p.dataset.b) p.classList.add('sel');
    else if (FBairros.includes(bai) &&
             (!FCidades.length || FCidades.includes(cid))) p.classList.add('sel');

    const n = info ? info.n : 0;
    const m2 = info && info.m2;
    const antigo = p.querySelector('title');
    if (antigo) antigo.remove();
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    t.textContent = bai + ' — ' + n + (n === 1 ? ' imóvel' : ' imóveis') +
      (m2 != null ? ' · ' + m2.toFixed(0) + ' R$/m² (mediana)' : '');
    p.appendChild(t);
  }});

  ajustarViewBox();
  desenharRotulos(resumo);

  const nota = el('mapa-legenda-nota');
  if (nota){{
    nota.textContent = valores.length
      ? valores[0].toFixed(0) + ' a ' + valores[valores.length-1].toFixed(0) + ' R$/m²'
      : 'sem preço por m² nesta seleção';
  }}
  pintarDetalheMapa(resumo);
}}

/* Reenquadra o mapa nas cidades escolhidas.

   A região monitorada vai do Cabo de Santo Agostinho a Paulista: 42km de
   norte a sul contra 23km de leste a oeste. Com o mapa fixo nessa extensão e
   Recife+Olinda no filtro, os bairros que interessam ficavam espremidos num
   terço da tela enquanto dois terços eram litoral vazio.

   Enquadra pela CAIXA de cada bairro, lida do atributo data-bb. getBBox()
   seria o caminho natural, mas devolve zeros num elemento sem layout (a aba
   fechada) -- enquadramento errado e silencioso. */
function ajustarViewBox(){{
  if (!mapaSvg) return;
  const paths = [...mapaSvg.querySelectorAll('.mapa-bairro')];
  if (!paths.length) return;
  const daCidade = FCidades.length
    ? paths.filter(p => FCidades.includes(p.dataset.b.split('|')[0]))
    : paths;
  // Cidade escolhida sem nenhum contorno ainda no cache não pode zerar o
  // mapa: cai para a região inteira, que é informação, não tela em branco.
  const alvo = daCidade.length ? daCidade : paths;

  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of alvo){{
    const bb = (p.dataset.bb || '').split(' ').map(Number);
    if (bb.length !== 4 || bb.some(isNaN)) continue;
    x0 = Math.min(x0, bb[0]); y0 = Math.min(y0, bb[1]);
    x1 = Math.max(x1, bb[2]); y1 = Math.max(y1, bb[3]);
  }}
  if (!isFinite(x0)) return;

  const folga = Math.max((x1 - x0), (y1 - y0)) * 0.06 + 2;
  x0 -= folga; y0 -= folga; x1 += folga; y1 += folga;
  VB = [x0, y0, x1 - x0, y1 - y0];
  mapaSvg.setAttribute('viewBox', VB.join(' '));
}}

/* Rótulos: só onde há imóvel, e sem colidir.

   Eram desenhados uma vez, para TODOS os bairros do cache. Com 33 no mapa o
   resultado foi ilegível -- "Jardim A|Rio Doce", "FragosoIada",
   "Casa E|Espinheiroa" empilhados. Nome sobreposto é pior que nome nenhum:
   além de não se ler, esconde o polígono que ele deveria explicar.

   Duas regras: rotula só bairro com imóvel no recorte (o resto é contexto, e
   o toque revela o nome na faixa de detalhe), e pula o rótulo cuja caixa
   encostar num já colocado. Quem tem mais imóveis entra primeiro, porque na
   disputa por espaço o bairro com mais oferta é o que a pessoa procura. */
function desenharRotulos(resumo){{
  if (!mapaSvg) return;
  const ns = 'http://www.w3.org/2000/svg';
  mapaSvg.querySelectorAll('.mapa-rotulo, .mapa-ponto').forEach(e => e.remove());

  // A fonte acompanha o enquadramento: com o viewBox mudando de escala, um
  // tamanho fixo em unidades de SVG viraria letra gigante quando o mapa se
  // aproxima de dois bairros.
  const fonte = Math.max(VB[3] * 0.023, 2.5);
  const candidatos = Object.keys(MAPA_CENTROS)
    .filter(k => (resumo[k] || {{}}).n > 0)
    .sort((a, b) => (resumo[b].n - resumo[a].n));

  const postos = [];
  const encosta = (a, b) =>
    a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0;

  for (const chave of candidatos){{
    const xy = MAPA_CENTROS[chave];
    if (xy[0] < VB[0] || xy[0] > VB[0] + VB[2]) continue;
    if (xy[1] < VB[1] || xy[1] > VB[1] + VB[3]) continue;

    const nome = chave.split('|')[1];
    // Largura estimada: 0.52em por caractere é a média de uma sans em caixa
    // mista. Medir de verdade exigiria getComputedTextLength(), que precisa
    // de layout -- e o mapa é repintado com a aba fechada.
    const larg = nome.length * fonte * 0.52;
    const caixa = {{x0: xy[0] - larg / 2, x1: xy[0] + larg / 2,
                   y0: xy[1] - fonte * 1.9, y1: xy[1] - fonte * 0.4}};
    if (postos.some(p => encosta(caixa, p))) continue;
    postos.push(caixa);

    const t = document.createElementNS(ns, 'text');
    t.setAttribute('x', xy[0]);
    t.setAttribute('y', xy[1] - fonte * 0.7);
    t.setAttribute('class', 'mapa-rotulo');
    t.setAttribute('font-size', fonte.toFixed(2));
    t.setAttribute('stroke-width', (fonte * 0.32).toFixed(2));
    t.textContent = nome;
    mapaSvg.appendChild(t);

    const c = document.createElementNS(ns, 'circle');
    c.setAttribute('cx', xy[0]); c.setAttribute('cy', xy[1]);
    c.setAttribute('r', (fonte * 0.18).toFixed(2));
    c.setAttribute('class', 'mapa-ponto');
    mapaSvg.appendChild(c);
  }}
}}

/* Tocar no bairro abre esta faixa em vez de trocar de aba na hora: no celular,
   mudar de tela ao encostar num polígono de 20px transforma erro de mira em
   navegação indesejada. Aqui a pessoa vê o que escolheu e decide. */
function pintarDetalheMapa(resumo){{
  if (!mapaDet) return;
  if (!mapaSelecionado){{ mapaDet.hidden = true; mapaDet.innerHTML = ''; return; }}
  const partes = mapaSelecionado.split('|');
  const cid = partes[0], bai = partes[1];
  const info = resumo[mapaSelecionado] || {{n: 0, m2: null, preco: null}};
  const jaFiltrado = FBairros.includes(bai) &&
    (!FCidades.length || FCidades.includes(cid));
  const eraOculto = mapaDet.hidden;
  mapaDet.hidden = false;
  mapaDet.innerHTML =
    '<h3>' + esc(bai) + '</h3>' +
    '<p>' + esc(cid) + ' · ' + info.n + (info.n === 1 ? ' imóvel' : ' imóveis') +
    (info.preco != null ? ' · mediana ' + fmtBRL(info.preco) : '') +
    (info.m2 != null ? ' · ' + info.m2.toFixed(0) + ' R$/m²' : '') + '</p>' +
    '<button class="btn-ofertas" id="mapa-ir" type="button">' +
    (jaFiltrado ? 'Ver os imóveis' : 'Filtrar por ' + esc(bai)) + '</button>';
  // trazer para a tela ao ABRIR, não a cada repintura: rolar sozinho toda vez
  // que o filtro muda tiraria a página do lugar enquanto se digita na busca
  if (eraOculto && mapaDet.scrollIntoView){{
    mapaDet.scrollIntoView({{block: 'nearest', behavior: 'smooth'}});
  }}
  el('mapa-ir').addEventListener('click', () => {{
    /* ACRESCENTA ao filtro em vez de substituir: no mapa a pessoa compara
       bairros vizinhos, e tocar no segundo apagando o primeiro tornaria
       impossível acompanhar dois de uma vez -- que é justamente o que a
       seleção múltipla veio permitir. Segundo toque no mesmo bairro tira. */
    if (!FCidades.includes(cid)) FCidades.push(cid);
    desenharMulti();          // o bairro só existe depois que a cidade entra
    if (!FBairros.includes(bai)) FBairros.push(bai);
    desenharMulti();
    render();
    mostrarAba('imoveis');
  }});
}}

if (mapaSvg){{
  mapaSvg.addEventListener('click', ev => {{
    const p = ev.target.closest('.mapa-bairro');
    if (!p) return;
    // segundo toque no mesmo bairro fecha a faixa: sem isto não há como
    // desfazer a escolha sem acertar o fundo entre dois polígonos
    mapaSelecionado = mapaSelecionado === p.dataset.b ? null : p.dataset.b;
    pintarMapa();
  }});
}}

/* ---------- abas ---------- */
const abas = {{imoveis: el('aba-imoveis'), mapa: el('aba-mapa'),
              fontes: el('aba-fontes')}};
const paineis = {{imoveis: el('painel-imoveis'), mapa: el('painel-mapa'),
                 fontes: el('painel-fontes')}};
const filtrosEl = el('filtros');

function mostrarAba(nome, gravar = true){{
  for (const [k, b] of Object.entries(abas)){{
    b.setAttribute('aria-selected', String(k === nome));
    paineis[k].hidden = k !== nome;
  }}
  // O filtro vale para o mapa também: lá o recorte é o que dá a cor. Só a
  // aba de Fontes não tem o que filtrar -- ela fala de coleta, não de imóvel.
  el('barra-filtros').hidden = nome === 'fontes';
  if (nome === 'fontes') abrirFiltros(false);
  // repinta ao ENTRAR: enquanto o painel está hidden o SVG não tem layout, e
  // pintar num elemento sem caixa já rendeu mapa em branco neste projeto
  if (nome === 'mapa') pintarMapa();
  if (gravar) gravarUrl();
}}
Object.entries(abas).forEach(([k, b]) =>
  b.addEventListener('click', () => mostrarAba(k)));

/* ---------- estado na URL ----------
   Um recorte útil ("2 quartos em Casa Caiada até 2.500") só se compartilha
   e só se refaz amanhã se couber num link. Sem isto, cada abertura do
   dashboard recomeça do zero. replaceState, não pushState: refazer filtro
   não é navegação, e encher o histórico faria o botão "voltar" do celular
   virar desfazer-filtro em vez de sair da página. */
const CAMPOS_URL = [
  ['quartos', selQuartos], ['ordem', selOrdem],
  ['min', inpMin], ['max', inpMax],
  ['amin', inpAreaMin], ['amax', inpAreaMax], ['q', inpBusca],
];

function gravarUrl(){{
  const p = new URLSearchParams();
  for (const [nome, campo] of CAMPOS_URL){{
    const v = campo.value;
    if (v && v !== '0' && v !== 'relevancia') p.set(nome, v);
  }}
  // Listas viram valores repetidos (?bairro=Pina&bairro=Boa+Viagem) em vez de
  // um campo separado por vírgula: bairro com vírgula no nome quebraria o
  // split, e URLSearchParams já sabe repetir chave.
  FCidades.forEach(c => p.append('cidade', c));
  FBairros.forEach(b => p.append('bairro', b));
  const marcados = Object.entries(chips)
    .filter(([, c]) => c.getAttribute('aria-pressed') === 'true').map(([k]) => k);
  if (marcados.length) p.set('sinais', marcados.join(','));
  if (escopo !== 'todos') p.set('escopo', escopo);
  for (const nome of ['mapa', 'fontes']){{
    if (abas[nome].getAttribute('aria-selected') === 'true') p.set('aba', nome);
  }}
  const s = p.toString();
  // Abrir por duplo clique (file://) ou de um data: URL dá origem nula, e aí
  // replaceState levanta SecurityError. Sem a guarda, a exceção sobe pelo
  // render() e a lista inteira deixa de ser desenhada -- o link
  // compartilhável não pode custar o dashboard.
  try {{
    history.replaceState(null, '', s ? '?' + s : location.pathname);
  }} catch (e) {{}}
}}

function lerUrl(){{
  const p = new URLSearchParams(location.search);
  // escopo antes de tudo: ele define quais bairros existem para escolher
  const esc0 = p.get('escopo');
  if (esc0 && BOTOES_ESCOPO[esc0]){{
    escopo = esc0;
    Object.entries(BOTOES_ESCOPO).forEach(([k, b]) =>
      b.setAttribute('aria-pressed', String(k === esc0)));
  }}
  /* Link compartilhado GANHA da preferência salva. Quem abre um link quer ver
     o que foi compartilhado; aplicar a preferência por cima mostraria outra
     coisa e o link viraria mentira. Sem parâmetro nenhum, a preferência entra
     -- que é o "abre do meu jeito" pedido. */
  const temFiltroNaUrl = ['cidade','bairro','quartos','min','max','amin','amax','q','sinais']
    .some(k => p.has(k));
  if (temFiltroNaUrl){{
    FCidades = p.getAll('cidade');
    FBairros = p.getAll('bairro');
    for (const [nome, campo] of CAMPOS_URL){{
      if (p.has(nome)) campo.value = p.get(nome);
    }}
    const marcados = (p.get('sinais') || '').split(',').filter(Boolean);
    marcados.forEach(k => chips[k] && chips[k].setAttribute('aria-pressed', 'true'));
  }} else {{
    aplicarNoFiltro(PREFS);
  }}
  desenharMulti();
  const aba0 = p.get('aba');
  mostrarAba(abas[aba0] ? aba0 : 'imoveis', false);
}}

lerUrl();
pintarEscopo();
pintarBackup();
pintarAvisoArmazenamento();
pintarPulso();
// Aberta de saída quando o link já traz recorte -- quem abre um link
// filtrado precisa ver O QUE está filtrado --, e no desktop, onde a barra
// cabe numa linha e esconder não economiza nada.
abrirFiltros(contarFiltros() > 0 || window.matchMedia('(min-width:721px)').matches);
render();
</script>
</body>
</html>
"""

    with open(config.ARQUIVO_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html_final)
    log.info(f"Dashboard gerado em {config.ARQUIVO_DASHBOARD}")
    return config.ARQUIVO_DASHBOARD
