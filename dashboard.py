# -*- coding: utf-8 -*-
"""
Gera um único arquivo HTML autocontido (dashboard.html) com todos os
dados embutidos como JSON. Abre com duplo clique, sem precisar de
servidor, internet (exceto pelas 3 fontes do Google Fonts, que caem
para uma fonte padrão do sistema se estiver offline) ou instalação.

Conceito visual: "Diário de Busca" -- um livro de registros de imóveis,
onde cada anúncio novo do dia ganha um carimbo, como um carimbo de data
num protocolo. Paleta de papel e tinta, tipografia serifada no título e
monoespaçada nos dados (preço, m², contadores).
"""
import html
import json
from datetime import date

import config
import db
from utils import log

ICONES_SVG = {
    "quarto": '''<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 15.5V6.5a1 1 0 0 1 1-1h13a1 1 0 0 1 1 1v9"/><path d="M2.5 12h15"/><path d="M4.5 9.5h4a1 1 0 0 1 1 1V12h-5V9.5Z"/><path d="M2.5 15.5v1.7M17.5 15.5v1.7"/></svg>''',
    "bairro": '''<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10 18s6-5.2 6-9.8A6 6 0 0 0 4 8.2C4 12.8 10 18 10 18Z"/><circle cx="10" cy="8" r="2.1"/></svg>''',
    "valor": '''<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M11.5 2.5 17.5 8.5v6a1 1 0 0 1-1 1h-6a1 1 0 0 1-.7-.3l-7-7a1 1 0 0 1 0-1.4l4.6-4.6a1 1 0 0 1 1.4 0Z"/><circle cx="12.2" cy="7.8" r="1.1"/></svg>''',
    "busca": '''<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="8.7" cy="8.7" r="5.7"/><path d="m17 17-4.3-4.3"/></svg>''',
    "externo": '''<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 5H5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-3"/><path d="M12 3h5v5"/><path d="M17 3 9 11"/></svg>''',
    "area": '''<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3h5M3 3v5M17 3h-5M17 3v5M3 17h5M3 17v-5M17 17h-5M17 17v-5"/></svg>''',
    "limpar": '''<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5l10 10M15 5 5 15"/></svg>''',
    "vazio": '''<svg width="32" height="32" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="opacity:.4;display:block;margin:0 auto 10px"><circle cx="8.7" cy="8.7" r="5.7"/><path d="m17 17-4.3-4.3"/></svg>''',
}


CSS = """
:root{
  --papel: #E8E4D8;
  --papel-alto: #F1EEE4;
  --tinta: #1E241B;
  --tinta-suave: #5B6154;
  --linha: #C9C4B2;
  --carimbo: #205C4F;
  --carimbo-fundo: #E2ECE8;
  --foco: #2B4A6F;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  background:var(--papel);
  color:var(--tinta);
  font-family:'IBM Plex Sans', -apple-system, Segoe UI, Arial, sans-serif;
  font-size:15px;
  line-height:1.45;
}
.icone{width:17px;height:17px;display:inline-block;vertical-align:-3px;flex-shrink:0;}
a{color:inherit;}

.pagina{max-width:900px;margin:0 auto;padding:0 20px 64px;}

.mastro{
  padding:40px 0 22px;
  border-bottom:2px solid var(--tinta);
}
.mastro-topo{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;}
.mastro h1{
  font-family:'Fraunces', Georgia, serif;
  font-weight:600;
  font-size:34px;
  letter-spacing:-0.01em;
  margin:0;
}
.mastro .data{
  font-family:'IBM Plex Mono', monospace;
  font-size:13px;
  color:var(--tinta-suave);
  letter-spacing:0.03em;
}
.mastro .subtitulo{
  margin-top:6px;
  color:var(--tinta-suave);
  font-size:14.5px;
}

.barra-filtros{
  margin-top:26px;
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  align-items:stretch;
}
.campo{
  display:flex;
  align-items:center;
  gap:7px;
  background:var(--papel-alto);
  border:1px solid var(--linha);
  border-radius:3px;
  padding:0 10px;
  height:40px;
  color:var(--tinta-suave);
}
.campo:focus-within{border-color:var(--foco);color:var(--tinta);}
.campo select,.campo input{
  border:0;background:transparent;color:var(--tinta);
  font-family:'IBM Plex Sans', sans-serif; font-size:14px;
  height:38px; outline:none; min-width:0;
}
.campo select{cursor:pointer;}
#f-busca{width:170px;}
.campo.valor{width:170px;}
.campo.valor input{width:68px; font-family:'IBM Plex Mono',monospace;}
.til{color:var(--tinta-suave);}
.campo select.largo{min-width:140px;}

.btn{
  height:40px;
  padding:0 18px;
  border:1px solid var(--tinta);
  background:var(--tinta);
  color:var(--papel-alto);
  border-radius:3px;
  font-family:'IBM Plex Sans', sans-serif;
  font-size:14px;
  font-weight:600;
  letter-spacing:0.01em;
  cursor:pointer;
  display:flex; align-items:center; gap:8px;
}
.btn:hover{background:#333c2c;}
.btn.fantasma{
  background:transparent; color:var(--tinta-suave); border-color:var(--linha);
  font-weight:400;
}
.btn.fantasma:hover{color:var(--tinta); border-color:var(--tinta-suave);}
.btn:focus-visible,.campo:focus-within,select:focus-visible,input:focus-visible{
  outline:2px solid var(--foco); outline-offset:2px;
}

.resumo{
  margin-top:20px;
  padding:9px 2px;
  font-family:'IBM Plex Mono', monospace;
  font-size:12.5px;
  color:var(--tinta-suave);
  letter-spacing:0.02em;
  border-bottom:1px solid var(--linha);
}

.lista{margin-top:4px;}
.linha{
  display:flex;
  gap:16px;
  align-items:center;
  padding:16px 2px;
  border-bottom:1px solid var(--linha);
  position:relative;
}
.linha:hover{background:var(--papel-alto);}
.linha-principal{flex:1; min-width:0;}
.linha-titulo{
  font-family:'Fraunces', Georgia, serif;
  font-size:18px;
  font-weight:500;
  margin:0 0 3px;
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  min-width:0;
}
.linha-titulo-texto{
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; flex:1;
}
.linha-meta{
  display:flex; flex-wrap:wrap; gap:14px;
  color:var(--tinta-suave); font-size:13.5px;
}
.linha-meta span{display:flex; align-items:center; gap:5px;}
.linha-site{
  font-family:'IBM Plex Mono', monospace;
  font-size:11.5px;
  text-transform:uppercase;
  letter-spacing:0.06em;
  color:var(--tinta-suave);
}
.linha-preco{
  font-family:'IBM Plex Mono', monospace;
  font-size:19px;
  font-weight:600;
  white-space:nowrap;
  text-align:right;
}
.linha-preco small{display:block; font-size:11px; font-weight:400; color:var(--tinta-suave); text-align:right;}

.abrir{
  display:flex; align-items:center; gap:6px;
  font-family:'IBM Plex Mono', monospace;
  font-size:12px; text-transform:uppercase; letter-spacing:0.04em;
  color:var(--tinta-suave);
  text-decoration:none;
  border:1px solid var(--linha);
  border-radius:3px;
  padding:7px 10px;
  white-space:nowrap;
}
.abrir:hover{border-color:var(--tinta); color:var(--tinta);}

.carimbo{
  font-family:'IBM Plex Mono', monospace;
  font-size:11px;
  font-weight:700;
  letter-spacing:0.09em;
  color:var(--carimbo);
  border:1.5px solid var(--carimbo);
  background:var(--carimbo-fundo);
  border-radius:2px;
  padding:2px 7px;
  transform:rotate(-4deg);
  display:inline-block;
}
.queda{
  font-family:'IBM Plex Mono', monospace;
  font-size:11px; font-weight:700; letter-spacing:0.06em;
  color:#205C4F; background:#d4edda; border:1.5px solid #205C4F;
  border-radius:2px; padding:2px 7px; display:inline-block;
}
.sparkline{display:inline-block;vertical-align:middle;margin-left:6px;}

.vazio{
  padding:60px 10px; text-align:center; color:var(--tinta-suave);
}
.vazio .icone{width:30px;height:30px;opacity:0.5;margin-bottom:10px;}

.rodape{
  margin-top:30px; padding-top:16px; border-top:1px solid var(--linha);
  color:var(--tinta-suave); font-size:12.5px;
  font-family:'IBM Plex Mono', monospace;
}

@media (max-width:640px){
  .mastro h1{font-size:26px;}
  .linha{flex-wrap:wrap;}
  .linha-preco{text-align:left; margin-left:auto;}
  #f-busca{width:120px;}
}

@media (prefers-reduced-motion: no-preference){
  .linha{transition:background 0.12s ease;}
  .btn{transition:background 0.12s ease;}
}
"""


def _formatar_preco(preco):
    if preco is None:
        return "—"
    return f"R$ {preco:,.0f}".replace(",", ".")


def gerar_dashboard(itens: list[dict]) -> str:
    """Gera o arquivo em config.ARQUIVO_DASHBOARD a partir dos itens
    (já devem vir com 'novo' e 'primeiro_visto' preenchidos por db.py)."""

    urls = [i.get("url", "") for i in itens]
    historico_map = db.obter_historico_todos(urls)

    dados_js = []
    for i in itens:
        url = i.get("url", "#")
        hist = historico_map.get(url, [])
        preco_atual = i.get("preco")

        queda_preco = False
        queda_valor = None
        if len(hist) >= 2 and preco_atual is not None:
            preco_anterior = next((h[1] for h in reversed(hist[:-1]) if h[1] is not None), None)
            if preco_anterior and preco_anterior > preco_atual:
                queda_preco = True
                queda_valor = round(preco_anterior - preco_atual, 2)

        dados_js.append({
            "titulo": i.get("titulo") or "Apartamento",
            "site": i.get("site", ""),
            "cidade": i.get("cidade") or "",
            "bairro": i.get("bairro") or "",
            "preco": preco_atual,
            "precoFmt": _formatar_preco(preco_atual),
            "quartos": i.get("quartos"),
            "area": i.get("area_m2"),
            "url": url,
            "novo": bool(i.get("novo")),
            "historico": hist,
            "quedaPreco": queda_preco,
            "quedaValor": queda_valor,
        })

    novos_hoje = sum(1 for i in itens if i.get("novo"))

    json_dados = json.dumps(dados_js, ensure_ascii=False).replace("</", "<\\/")

    data_hoje_fmt = date.today().strftime("%d %b %y").upper()
    filtros = config.FILTROS
    subtitulo_cidades = " · ".join(
        f"{cidade} ({perfil['quartos_min']}+ qtos, {perfil['area_min']}m²+)"
        for cidade, perfil in config.FILTROS_POR_CIDADE.items()
    )

    html_final = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diário de Busca — Apartamentos em Recife</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="pagina">

  <header class="mastro">
    <div class="mastro-topo">
      <h1>Diário de Busca</h1>
      <div class="data">{html.escape(data_hoje_fmt)}</div>
    </div>
    <div class="subtitulo">Apartamentos para alugar · {html.escape(subtitulo_cidades)} · R$ {filtros['preco_min']:,.0f} – R$ {filtros['preco_max']:,.0f}</div>

    <div class="barra-filtros">
      <div class="campo">
        {ICONES_SVG['quarto']}
        <select id="f-quartos"><option value="0">Quartos: todos</option><option value="1">1+</option><option value="2">2+</option><option value="3">3+</option><option value="4">4+</option></select>
      </div>
      <div class="campo">
        {ICONES_SVG['bairro']}
        <select id="f-cidade" class="largo"><option value="">Cidade: todas</option></select>
      </div>
      <div class="campo">
        {ICONES_SVG['bairro']}
        <select id="f-bairro"><option value="">Bairro: todos</option></select>
      </div>
      <div class="campo">
        <select id="f-fonte" class="largo"><option value="">Fonte: todas</option></select>
      </div>
      <div class="campo valor">
        {ICONES_SVG['valor']}
        <input type="number" id="f-min" placeholder="mín" inputmode="numeric">
        <span class="til">–</span>
        <input type="number" id="f-max" placeholder="máx" inputmode="numeric">
      </div>
      <div class="campo" style="flex:1; min-width:150px;">
        {ICONES_SVG['busca']}
        <input type="text" id="f-busca" placeholder="Buscar por título ou site" style="width:100%;">
      </div>
      <div class="campo">
        <select id="f-ordem" class="largo">
          <option value="novo_preco">Novos + Menor preço</option>
          <option value="preco_asc">Menor preço</option>
          <option value="preco_desc">Maior preço</option>
          <option value="area_desc">Maior área</option>
          <option value="custo_m2">Melhor custo/m²</option>
        </select>
      </div>
      <button class="btn" id="btn-buscar">{ICONES_SVG['busca']} Buscar</button>
      <button class="btn fantasma" id="btn-limpar">{ICONES_SVG['limpar']} Limpar</button>
    </div>

    <div class="resumo" id="resumo"></div>
  </header>

  <main class="lista" id="lista"></main>

  <template id="tpl-vazio">
    <div class="vazio">
      {ICONES_SVG['vazio']}
      <div>Nenhum imóvel corresponde a esses filtros.</div>
    </div>
  </template>

  <footer class="rodape">
    Gerado localmente pelo Monitor de Apartamentos · {len(dados_js)} imóveis no total · {novos_hoje} novos hoje
  </footer>
</div>

<script>
const DADOS = {json_dados};

const ICONE_AREA = `{ICONES_SVG['area']}`;
const ICONE_QUARTO = `{ICONES_SVG['quarto']}`;
const ICONE_BAIRRO = `{ICONES_SVG['bairro']}`;
const ICONE_EXTERNO = `{ICONES_SVG['externo']}`;

const elLista = document.getElementById('lista');
const elResumo = document.getElementById('resumo');
const selCidade = document.getElementById('f-cidade');
const selBairro = document.getElementById('f-bairro');
const selQuartos = document.getElementById('f-quartos');
const selFonte = document.getElementById('f-fonte');
const selOrdem = document.getElementById('f-ordem');
const inpMin = document.getElementById('f-min');
const inpMax = document.getElementById('f-max');
const inpBusca = document.getElementById('f-busca');

const cidades = [...new Set(DADOS.map(i => i.cidade).filter(Boolean))].sort();
cidades.forEach(c => {{
  const op = document.createElement('option');
  op.value = c; op.textContent = c;
  selCidade.appendChild(op);
}});

// bairro é atrelado à cidade escolhida: sem isso a lista mistura bairro de
// Recife com o de Olinda (ex: tem "Carmo" nas duas), confuso pra filtrar.
function atualizarBairros(){{
  const cidadeAtual = selCidade.value;
  const bairroSelecionado = selBairro.value;
  const escopo = cidadeAtual ? DADOS.filter(i => i.cidade === cidadeAtual) : DADOS;
  const bairrosDaCidade = [...new Set(escopo.map(i => i.bairro).filter(Boolean))].sort();

  selBairro.innerHTML = '<option value="">Bairro: todos</option>';
  bairrosDaCidade.forEach(b => {{
    const op = document.createElement('option');
    op.value = b; op.textContent = b;
    selBairro.appendChild(op);
  }});
  // mantém o bairro escolhido se ele ainda existir na cidade nova
  if (bairrosDaCidade.includes(bairroSelecionado)) selBairro.value = bairroSelecionado;
}}
atualizarBairros();

const fontes = [...new Set(DADOS.map(i => i.site))].sort();
fontes.forEach(f => {{
  const op = document.createElement('option');
  op.value = f; op.textContent = f;
  selFonte.appendChild(op);
}});

function escapeHtml(s){{
  return (s || '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}

function sparkline(historico){{
  if (!historico || historico.length < 2) return '';
  const precos = historico.map(h => h[1]).filter(v => v !== null && v !== undefined);
  if (precos.length < 2) return '';
  const mn = Math.min(...precos), mx = Math.max(...precos);
  const rng = mx - mn || 1;
  const W = 64, H = 22, n = precos.length;
  const pts = precos.map((p, i) => `${{(i / (n - 1) * W).toFixed(1)}},${{(H - (p - mn) / rng * (H - 2) - 1).toFixed(1)}}`).join(' ');
  const cor = precos[precos.length - 1] < precos[0] ? '#205C4F' : '#8B2020';
  return `<span class="sparkline"><svg width="${{W}}" height="${{H}}" viewBox="0 0 ${{W}} ${{H}}"><polyline points="${{pts}}" fill="none" stroke="${{cor}}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span>`;
}}

function limparTitulo(s){{
  s = (s || 'Apartamento')
    .replace(/[\\r\\n]+/g, ' ')
    .replace(/chevron_left|chevron_right/g, '')
    .replace(/\\s{{2,}}/g, ' ')
    .trim();
  if (s.length > 90) s = s.slice(0, 87) + '…';
  return s;
}}

function renderizar(){{
  const quartosMin = parseInt(selQuartos.value || '0', 10);
  const cidade = selCidade.value;
  const bairro = selBairro.value;
  const fonte = selFonte.value;
  const ordem = selOrdem.value;
  const min = inpMin.value ? parseFloat(inpMin.value) : null;
  const max = inpMax.value ? parseFloat(inpMax.value) : null;
  const busca = (inpBusca.value || '').trim().toLowerCase();

  const filtrados = DADOS.filter(item => {{
    if (quartosMin > 0 && (!item.quartos || item.quartos < quartosMin)) return false;
    if (cidade && item.cidade !== cidade) return false;
    if (bairro && item.bairro !== bairro) return false;
    if (fonte && item.site !== fonte) return false;
    if (min !== null && (item.preco === null || item.preco < min)) return false;
    if (max !== null && (item.preco === null || item.preco > max)) return false;
    if (busca) {{
      const alvo = (item.titulo + ' ' + item.site + ' ' + item.bairro + ' ' + item.cidade).toLowerCase();
      if (!alvo.includes(busca)) return false;
    }}
    return true;
  }});

  filtrados.sort((a, b) => {{
    if (ordem === 'preco_asc') return (a.preco || 99999) - (b.preco || 99999);
    if (ordem === 'preco_desc') return (b.preco || 0) - (a.preco || 0);
    if (ordem === 'area_desc') return (b.area || 0) - (a.area || 0);
    if (ordem === 'custo_m2') {{
      const ra = a.preco && a.area ? a.preco / a.area : 99999;
      const rb = b.preco && b.area ? b.preco / b.area : 99999;
      return ra - rb;
    }}
    // novo_preco: novos primeiro, depois menor preço
    if (a.novo !== b.novo) return a.novo ? -1 : 1;
    return (a.preco || 99999) - (b.preco || 99999);
  }});

  elResumo.textContent = `${{filtrados.length}} de ${{DADOS.length}} imóveis · ${{filtrados.filter(i => i.novo).length}} novos hoje`;

  elLista.innerHTML = '';
  if (filtrados.length === 0) {{
    elLista.appendChild(document.getElementById('tpl-vazio').content.cloneNode(true));
    return;
  }}

  for (const item of filtrados) {{
    const linha = document.createElement('div');
    linha.className = 'linha';
    const quedaBadge = item.quedaPreco
      ? `<span class="queda">↓ R$ ${{item.quedaValor ? item.quedaValor.toLocaleString('pt-BR') : ''}}</span>`
      : '';
    linha.innerHTML = `
      <div class="linha-principal">
        <p class="linha-titulo">
          <span class="linha-titulo-texto">${{escapeHtml(limparTitulo(item.titulo))}}</span>
          ${{item.novo ? '<span class="carimbo">NOVO</span>' : ''}}
          ${{quedaBadge}}
          ${{sparkline(item.historico)}}
        </p>
        <div class="linha-meta">
          <span class="linha-site">${{escapeHtml(item.site)}}</span>
          ${{(item.bairro || item.cidade) ? `<span>${{ICONE_BAIRRO}} ${{escapeHtml([item.bairro, item.cidade].filter(Boolean).join(', '))}}</span>` : ''}}
          ${{item.quartos ? `<span>${{ICONE_QUARTO}} ${{item.quartos}} quartos</span>` : ''}}
          ${{item.area ? `<span>${{ICONE_AREA}} ${{item.area}} m²</span>` : ''}}
        </div>
      </div>
      <div class="linha-preco">${{escapeHtml(item.precoFmt)}}<small>/mês</small></div>
      <a class="abrir" href="${{item.url}}" target="_blank" rel="noopener">Abrir ${{ICONE_EXTERNO}}</a>
    `;
    elLista.appendChild(linha);
  }}
}}

document.getElementById('btn-buscar').addEventListener('click', renderizar);
document.getElementById('btn-limpar').addEventListener('click', () => {{
  selQuartos.value = '0'; selCidade.value = ''; selFonte.value = '';
  selOrdem.value = 'novo_preco'; inpMin.value = ''; inpMax.value = ''; inpBusca.value = '';
  atualizarBairros();
  renderizar();
}});
inpBusca.addEventListener('keydown', e => {{ if (e.key === 'Enter') renderizar(); }});
selCidade.addEventListener('change', () => {{ atualizarBairros(); renderizar(); }});
[selQuartos, selBairro, selFonte, selOrdem].forEach(el => el.addEventListener('change', renderizar));

renderizar();
</script>
</body>
</html>
"""

    with open(config.ARQUIVO_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html_final)
    log.info(f"Dashboard gerado em {config.ARQUIVO_DASHBOARD}")
    return config.ARQUIVO_DASHBOARD
