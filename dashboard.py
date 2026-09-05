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
            "noRecorte": bool(i.get("noRecorte", True)),
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
            "<div><dt>Coletados e não exibidos</dt><dd>"
            f"{' · '.join(partes)}. A coleta cobre a cidade inteira; a lista "
            "de bairros acima é só o recorte da exibição — o botão "
            "<b>Outros bairros</b>, no topo, mostra o que ficou de fora.</dd></div>"
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

  <div class="escopo" role="group" aria-label="Recorte da lista">
    <button class="chip-escopo" id="e-meus" type="button" aria-pressed="true">
      Minhas preferências <span class="chip-n" id="n-meus"></span></button>
    <button class="chip-escopo" id="e-outros" type="button" aria-pressed="false">
      Outros bairros <span class="chip-n" id="n-outros"></span></button>
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

    <label class="campo">{ic['local']}
      <select id="f-cidade" aria-label="Cidade"><option value="">Cidade: todas</option></select>
    </label>
    <label class="campo">
      <select id="f-bairro" aria-label="Bairro"><option value="">Bairro: todos</option></select>
    </label>
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
  </div>

  <nav class="abas" role="tablist">
    <button class="aba" id="aba-imoveis" role="tab" aria-selected="true"
            aria-controls="painel-imoveis" type="button">
      Imóveis <span class="aba-n" id="n-aba-imoveis">{len(dados)}</span></button>
    <button class="aba" id="aba-fontes" role="tab" aria-selected="false"
            aria-controls="painel-fontes" type="button">
      Fontes <span class="aba-n">{len(rendimento or [])}</span></button>
  </nav>

  <section id="painel-imoveis" role="tabpanel" aria-labelledby="aba-imoveis">
    <div id="lista" class="lista"></div>
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
const IC = {json.dumps({k: v for k, v in ic.items() if k in ('local', 'externo', 'vazio', 'sol', 'lua', 'foto', 'seta',
                        'estrela', 'descartar', 'restaurar', 'lixeira')}, ensure_ascii=False)};

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

/* ---------- recorte de bairros ----------
   Os dois lados são EXCLUSIVOS: "Minhas preferências" mostra o que está no
   filtro de bairros e "Outros bairros" mostra o complemento -- o que ficou
   de fora, e só isso. Um botão "todos" (preferências + resto) obrigaria a
   procurar os conhecidos no meio da lista inteira para descobrir o que há
   de novo fora dela, que é justamente a pergunta que ele deveria responder.

   O recorte é do usuário, não do robô: a coleta cobre a cidade inteira e o
   arquivo carrega tudo, então trocar de lado é instantâneo. O selo de
   sugestão não muda -- continua só nos bairros preferidos. */
const el = id => document.getElementById(id);
let escopo = 'meus';

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

/* Descartado sai das duas listas de bairro E das contagens -- senão o número
   do topo volta a discordar do que está na tela, que é o problema que a
   contagem dinâmica veio resolver. Favorito NÃO some das listas: continua
   onde está, com a estrela acesa. */
function noEscopo(d){{
  if (escopo === 'lixeira') return descartado(d);
  if (descartado(d)) return false;
  if (escopo === 'favoritos') return favorito(d);
  if (escopo === 'outros') return !d.noRecorte;
  return d.noRecorte;
}}

/* ---------- filtros ---------- */
const selCidade = el('f-cidade'), selBairro = el('f-bairro'), selQuartos = el('f-quartos');
const selOrdem = el('f-ordem'), inpMin = el('f-min'), inpMax = el('f-max'), inpBusca = el('f-busca');
const chips = {{novos: el('c-novos'), quedas: el('c-quedas'), multi: el('c-multi')}};

[...new Set(DADOS.map(d => d.cidade).filter(Boolean))].sort().forEach(c => {{
  const o = document.createElement('option'); o.value = o.textContent = c; selCidade.appendChild(o);
}});

function preencherBairros(){{
  const cid = selCidade.value, atual = selBairro.value;
  const visiveis = DADOS.filter(d => noEscopo(d) && (!cid || d.cidade === cid));
  selBairro.innerHTML = '<option value="">Bairro: todos</option>';
  [...new Set(visiveis.map(d => d.bairro).filter(Boolean))].sort().forEach(b => {{
    const o = document.createElement('option'); o.value = o.textContent = b; selBairro.appendChild(o);
  }});
  if ([...selBairro.options].some(o => o.value === atual)) selBairro.value = atual;
}}
preencherBairros();

Object.values(chips).forEach(c => c.addEventListener('click', () => {{
  c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
  render();
  pintarPulso();  // o pulso espelha os chips: os dois têm de contar a mesma coisa
}}));

function filtrar(){{
  const qMin = parseInt(selQuartos.value || '0', 10);
  const cid = selCidade.value, bai = selBairro.value;
  const mn = inpMin.value ? parseFloat(inpMin.value) : null;
  const mx = inpMax.value ? parseFloat(inpMax.value) : null;
  const q = (inpBusca.value || '').trim().toLowerCase();
  const soNovos = chips.novos.getAttribute('aria-pressed') === 'true';
  const soQuedas = chips.quedas.getAttribute('aria-pressed') === 'true';
  const soMulti = chips.multi.getAttribute('aria-pressed') === 'true';

  return DADOS.filter(d => {{
    if (!noEscopo(d)) return false;
    if (soNovos && !d.novo) return false;
    if (soQuedas && !d.queda) return false;
    if (soMulti && d.qtdFontes < 2) return false;
    if (qMin > 0 && (!d.quartos || d.quartos < qMin)) return false;
    if (cid && d.cidade !== cid) return false;
    if (bai && d.bairro !== bai) return false;
    if (mn != null && (d.preco == null || d.preco < mn)) return false;
    if (mx != null && (d.preco == null || d.preco > mx)) return false;
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
  const base = DADOS.filter(noEscopo);
  const novos = base.filter(d => d.novo).length;
  const quedas = base.filter(d => d.queda).length;
  const multi = base.filter(d => d.qtdFontes > 1).length;
  const m2 = base.map(d => d.precoM2).filter(v => v != null).sort((a,b) => a-b);
  const mediana = m2.length ? m2[Math.floor(m2.length/2)].toFixed(0) : '—';
  const precos = base.map(d => d.preco).filter(v => v != null);
  const faixa = precos.length
    ? `${{fmtBRL(Math.min(...precos))}}<small>a ${{fmtBRL(Math.max(...precos))}}</small>`
    : '—';

  const item = (rot, val, destaque) =>
    `<div class="pulso-item${{destaque ? ' destaque' : ''}}">
       <div class="pulso-rot">${{rot}}</div><div class="pulso-val">${{val}}</div></div>`;

  /* "Novos hoje" e "Baixaram" são os dois números que respondem "o que mudou
     desde ontem" -- e eram os únicos sem resposta: o contador dizia 3 e não
     havia como chegar nos três, porque o filtro correspondente mora dentro do
     painel recolhido. Aqui o número É o filtro. */
  const acao = (rot, val, chip) =>
    `<button class="pulso-item acionavel" type="button" data-chip="${{chip}}"
             aria-pressed="${{chips[chip].getAttribute('aria-pressed')}}">
       <div class="pulso-rot">${{rot}}</div><div class="pulso-val">${{val}}</div></button>`;

  // o contador da aba acompanha o escopo: dizer "54" com 16 na tela faria
  // parecer que o filtro comeu imóvel
  el('n-aba-imoveis').textContent = base.length;

  pulso.innerHTML =
    item('Imóveis', base.length) +
    acao('Novos hoje', novos, 'novos') +
    acao('Baixaram', quedas, 'quedas') +
    item('Multi-fonte', multi) +
    item('Mediana R$/m²', mediana) +
    item('Faixa', faixa);

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

const BOTOES_ESCOPO = {{
  meus: el('e-meus'), outros: el('e-outros'),
  favoritos: el('e-favoritos'), lixeira: el('e-lixeira'),
}};

/* Os contadores das abas descontam o que está na lixeira -- exceto o da
   própria lixeira. Deixar o descartado somando em "Minhas preferências"
   faria a aba prometer imóveis que a lista não mostra. */
function pintarEscopo(){{
  const vivos = DADOS.filter(d => !descartado(d));
  el('n-meus').textContent = vivos.filter(d => d.noRecorte).length;
  el('n-outros').textContent = vivos.filter(d => !d.noRecorte).length;
  el('n-favoritos').textContent = vivos.filter(favorito).length;
  el('n-lixeira').textContent = DADOS.filter(descartado).length;
}}

function trocarEscopo(novo){{
  escopo = novo;
  Object.entries(BOTOES_ESCOPO).forEach(([k, b]) =>
    b.setAttribute('aria-pressed', String(k === novo)));
  // a lista de bairros do filtro acompanha o escopo, senão sobra opção que
  // não seleciona nada
  preencherBairros();
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

selCidade.addEventListener('change', () => {{ preencherBairros(); render(); }});
[selBairro, selQuartos, selOrdem].forEach(x => x.addEventListener('change', render));
[inpMin, inpMax].forEach(x => x.addEventListener('input', render));
inpBusca.addEventListener('input', render);
el('btn-limpar').addEventListener('click', () => {{
  selCidade.value = ''; selQuartos.value = '0'; selOrdem.value = 'relevancia';
  inpMin.value = inpMax.value = inpBusca.value = '';
  // O bairro precisa ser zerado ANTES de repovoar a lista: preencherBairros
  // preserva a seleção atual quando ela ainda existe entre as opções, então
  // sem esta linha "Limpar" deixava o filtro de bairro de pé -- e a tela
  // continuava mostrando um punhado de imóveis, com cara de botão quebrado.
  selBairro.value = '';
  Object.values(chips).forEach(c => c.setAttribute('aria-pressed', 'false'));
  preencherBairros(); render();
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
  if (selCidade.value) n++;
  if (selBairro.value) n++;
  if (selQuartos.value && selQuartos.value !== '0') n++;
  if (inpMin.value) n++;
  if (inpMax.value) n++;
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

/* ---------- abas ---------- */
const abas = {{imoveis: el('aba-imoveis'), fontes: el('aba-fontes')}};
const paineis = {{imoveis: el('painel-imoveis'), fontes: el('painel-fontes')}};
const filtrosEl = el('filtros');

function mostrarAba(nome, gravar = true){{
  for (const [k, b] of Object.entries(abas)){{
    b.setAttribute('aria-selected', String(k === nome));
    paineis[k].hidden = k !== nome;
  }}
  // filtro de imóvel não filtra fonte: some junto com o catálogo
  el('barra-filtros').hidden = nome !== 'imoveis';
  if (nome !== 'imoveis') abrirFiltros(false);
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
  ['cidade', selCidade], ['bairro', selBairro], ['quartos', selQuartos],
  ['ordem', selOrdem], ['min', inpMin], ['max', inpMax], ['q', inpBusca],
];

function gravarUrl(){{
  const p = new URLSearchParams();
  for (const [nome, campo] of CAMPOS_URL){{
    const v = campo.value;
    if (v && v !== '0' && v !== 'relevancia') p.set(nome, v);
  }}
  const marcados = Object.entries(chips)
    .filter(([, c]) => c.getAttribute('aria-pressed') === 'true').map(([k]) => k);
  if (marcados.length) p.set('sinais', marcados.join(','));
  if (escopo !== 'meus') p.set('escopo', escopo);
  if (abas.fontes.getAttribute('aria-selected') === 'true') p.set('aba', 'fontes');
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
  // cidade primeiro: a lista de bairros depende dela
  if (p.has('cidade')) selCidade.value = p.get('cidade');
  preencherBairros();
  for (const [nome, campo] of CAMPOS_URL){{
    if (nome !== 'cidade' && p.has(nome)) campo.value = p.get(nome);
  }}
  const marcados = (p.get('sinais') || '').split(',').filter(Boolean);
  marcados.forEach(k => chips[k] && chips[k].setAttribute('aria-pressed', 'true'));
  mostrarAba(p.get('aba') === 'fontes' ? 'fontes' : 'imoveis', false);
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
