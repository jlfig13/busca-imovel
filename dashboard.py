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
from datetime import date

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
        if len(hist) >= 2 and preco is not None:
            anterior = next((h[1] for h in reversed(hist[:-1]) if h[1] is not None), None)
            if anterior and anterior > preco:
                queda = round(anterior - preco, 2)

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
            "foto": i.get("foto"),
            "novo": bool(i.get("novo")),
            "historico": hist,
            "queda": queda,
        })

    novos = sum(1 for d in dados if d["novo"])
    quedas = sum(1 for d in dados if d["queda"])
    multi = sum(1 for d in dados if d["qtdFontes"] > 1)
    precos = [d["preco"] for d in dados if d["preco"]]
    mediana_m2 = sorted(d["precoM2"] for d in dados if d["precoM2"])
    med_m2 = mediana_m2[len(mediana_m2) // 2] if mediana_m2 else None

    json_dados = json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
    ic = design.ICONES
    hoje = date.today().strftime("%d/%m/%Y")
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
            "de bairros acima é só o recorte da exibição.</dd></div>"
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
      <span class="marca-sub">{hoje}</span>
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

  <section class="pulso" aria-label="Resumo da busca">
    <div class="pulso-item">
      <div class="pulso-rot">Imóveis</div>
      <div class="pulso-val">{len(dados)}</div>
    </div>
    <div class="pulso-item{' destaque' if novos else ''}">
      <div class="pulso-rot">Novos hoje</div>
      <div class="pulso-val">{novos}</div>
    </div>
    <div class="pulso-item{' destaque' if quedas else ''}">
      <div class="pulso-rot">Baixaram</div>
      <div class="pulso-val">{quedas}</div>
    </div>
    <div class="pulso-item">
      <div class="pulso-rot">Multi-fonte</div>
      <div class="pulso-val">{multi}</div>
    </div>
    <div class="pulso-item">
      <div class="pulso-rot">Mediana R$/m²</div>
      <div class="pulso-val">{f'{med_m2:.0f}' if med_m2 else '—'}</div>
    </div>
    <div class="pulso-item">
      <div class="pulso-rot">Faixa</div>
      <div class="pulso-val">{_fmt_preco(min(precos)) if precos else '—'}
        <small>a {_fmt_preco(max(precos)) if precos else '—'}</small></div>
    </div>
  </section>

  <div class="filtros" id="filtros">
    <button class="chip" id="c-novos" type="button" aria-pressed="false">
      Novos <span class="chip-n">{novos}</span></button>
    <button class="chip" id="c-quedas" type="button" aria-pressed="false">
      Baixaram <span class="chip-n">{quedas}</span></button>
    <button class="chip" id="c-multi" type="button" aria-pressed="false">
      Confirmados <span class="chip-n">{multi}</span></button>

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
        <option value="relevancia">Novos primeiro</option>
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
      Imóveis <span class="aba-n">{len(dados)}</span></button>
    <button class="aba" id="aba-fontes" role="tab" aria-selected="false"
            aria-controls="painel-fontes" type="button">
      Fontes <span class="aba-n">{len(rendimento or [])}</span></button>
  </nav>

  <section id="painel-imoveis" role="tabpanel" aria-labelledby="aba-imoveis">
    <div class="contagem" id="contagem"></div>
    <div id="lista" class="lista"></div>
  </section>

  <section id="painel-fontes" role="tabpanel" aria-labelledby="aba-fontes" hidden>
    <div class="rend">{_painel_rendimento(rendimento)}</div>
    {_painel_saude(saude)}
  </section>

  <footer class="rodape">
    Rodada de {hoje} · {len(dados)} imóveis exibidos
  </footer>
</div>

<script>
const DADOS = {json_dados};
const NAO_LOC = {json.dumps(NAO_LOCALIZADO)};
const IC = {json.dumps({k: v for k, v in ic.items() if k in ('local', 'externo', 'vazio', 'sol', 'lua', 'foto')}, ensure_ascii=False)};

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
function faixa(hist){{
  if (!hist || hist.length < 2) return '';
  const p = hist.map(h => h[1]).filter(v => v != null);
  if (p.length < 2) return '';
  const mn = Math.min(...p), mx = Math.max(...p), rg = (mx - mn) || 1;
  const W = 56, H = 20, n = p.length;
  const pts = p.map((v,i) => `${{(i/(n-1)*W).toFixed(1)}},${{(H-2 - (v-mn)/rg*(H-5)).toFixed(1)}}`).join(' ');
  const cor = p[p.length-1] < p[0] ? 'var(--bom)' : (p[p.length-1] > p[0] ? 'var(--atencao)' : 'var(--tinta-fraca)');
  return `<svg class="faixa" viewBox="0 0 ${{W}} ${{H}}" aria-hidden="true">
    <polyline points="${{pts}}" fill="none" stroke="${{cor}}" stroke-width="1.6"
      stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}}

/* ---------- filtros ---------- */
const el = id => document.getElementById(id);
const selCidade = el('f-cidade'), selBairro = el('f-bairro'), selQuartos = el('f-quartos');
const selOrdem = el('f-ordem'), inpMin = el('f-min'), inpMax = el('f-max'), inpBusca = el('f-busca');
const chips = {{novos: el('c-novos'), quedas: el('c-quedas'), multi: el('c-multi')}};

[...new Set(DADOS.map(d => d.cidade).filter(Boolean))].sort().forEach(c => {{
  const o = document.createElement('option'); o.value = o.textContent = c; selCidade.appendChild(o);
}});

function preencherBairros(){{
  const cid = selCidade.value, atual = selBairro.value;
  const escopo = cid ? DADOS.filter(d => d.cidade === cid) : DADOS;
  selBairro.innerHTML = '<option value="">Bairro: todos</option>';
  [...new Set(escopo.map(d => d.bairro).filter(Boolean))].sort().forEach(b => {{
    const o = document.createElement('option'); o.value = o.textContent = b; selBairro.appendChild(o);
  }});
  if ([...selBairro.options].some(o => o.value === atual)) selBairro.value = atual;
}}
preencherBairros();

Object.values(chips).forEach(c => c.addEventListener('click', () => {{
  c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
  render();
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
  // relevância: novo primeiro, depois quem baixou, depois menor preço
  return c.sort((a,b) =>
    (b.novo - a.novo) || ((b.queda ? 1 : 0) - (a.queda ? 1 : 0)) ||
    ((a.preco ?? 1e9) - (b.preco ?? 1e9)));
}}

/* ---------- render ---------- */
const lista = el('lista'), contagem = el('contagem');

/* Selos de ação (novo, queda) vão sobre a foto -- é o primeiro lugar
   onde o olho pousa no card. Os de contexto ficam no corpo. */
function selosFoto(d){{
  const s = [];
  if (d.novo) s.push('<span class="selo selo-novo">Novo</span>');
  if (d.queda) s.push(`<span class="selo selo-queda">Baixou ${{brl(d.queda)}}</span>`);
  return s.join('');
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

/* Foto de capa. Sem rede (ou sem foto na fonte) cai no marcador cinza:
   o dashboard tem de continuar legível offline, que é a premissa dele. */
function capa(d){{
  const vazio = `<div class="foto-vazia">${{IC.foto}}</div>`;
  const img = d.foto
    ? `<img src="${{esc(d.foto)}}" alt="" loading="lazy" decoding="async"
         onerror="this.remove()">`
    : '';
  return `<div class="foto">${{vazio}}${{img}}
    <div class="foto-selos">${{selosFoto(d)}}</div></div>`;
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

function render(){{
  gravarUrl();
  const res = ordenar(filtrar());
  contagem.textContent = res.length === DADOS.length
    ? `${{res.length}} imóveis`
    : `${{res.length}} de ${{DADOS.length}} imóveis`;

  lista.innerHTML = '';
  if (!res.length){{
    lista.innerHTML = `<div class="estado-vazio">${{IC.vazio}}<div>Nenhum imóvel com esses filtros.</div></div>`;
    return;
  }}

  const frag = document.createDocumentFragment();
  for (const d of res){{
    const card = document.createElement('article');
    card.className = 'imovel';
    const local = [d.bairro, d.cidade].filter(Boolean).join(', ');
    const varias = d.anuncios.length > 1;

    card.innerHTML = `
      ${{capa(d)}}
      <div class="imovel-corpo">
        <div class="imovel-cab">
          <h3 class="imovel-titulo">${{esc(d.titulo)}}</h3>
          ${{faixa(d.historico)}}
        </div>
        <div class="imovel-local">${{IC.local}}<span>${{esc(local)}}</span>
          ${{d.logradouro
              ? `<span class="rua">· ${{esc(d.logradouro)}}</span>`
              : `<span class="rua rua-ausente">· endereço ${{NAO_LOC}}</span>`}}</div>
        <div class="ficha">${{ficha(d)}}</div>
        <div class="selos">${{selos(d)}}</div>
        <div class="imovel-rodape">
          <div class="preco-bloco">
            <div class="preco-val">${{esc(d.precoFmt)}}<span class="preco-un">/mês</span></div>
            ${{d.precoM2 ? `<span class="preco-m2">${{d.precoM2.toFixed(0)}} R$/m²</span>` : ''}}
          </div>
          <div class="acoes">
            ${{varias ? `<button class="btn-ofertas" type="button" aria-expanded="false">
                 <span class="seta">&#9654;</span> ${{d.anuncios.length}} ofertas</button>` : ''}}
            <a class="btn-abrir" href="${{esc(d.url)}}" target="_blank" rel="noopener">
              Ver anúncio ${{IC.externo}}</a>
          </div>
        </div>
      </div>`;

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
  filtrosEl.hidden = nome !== 'imoveis';
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
render();
</script>
</body>
</html>
"""

    with open(config.ARQUIVO_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html_final)
    log.info(f"Dashboard gerado em {config.ARQUIVO_DASHBOARD}")
    return config.ARQUIVO_DASHBOARD
