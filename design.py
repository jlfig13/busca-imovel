# -*- coding: utf-8 -*-
"""
Design system do dashboard.

Direção: inteligência imobiliária + mapa + dados confiáveis. O produto deve
transmitir confiança, precisão, tecnologia, transparência, organização,
velocidade e sensação de premium.

DECISÕES DE COR -- por que estas e não outras
---------------------------------------------
As cores vêm do lugar, não de uma paleta genérica de imobiliária.

  Azul-Atlântico (#10495B) -- o mar de Boa Viagem e a água do Capibaribe.
  É a cor institucional: escura o bastante para ser lida como precisão e
  seriedade, dessaturada o bastante para não competir com o dado.

  Ocre-Olinda (#C2703D) -- as fachadas coloniais do Sítio Histórico. Entra
  SÓ como destaque pontual (oportunidade, queda de preço). Um acento único
  e quente contra um fundo frio é o que dá calor sem virar "carnaval".

O óbvio seria usar as cores do frevo ou da bandeira de Pernambuco. Ficaria
saturado e brincalhão -- o oposto de "dados confiáveis". A referência aqui é
a arquitetura e a água, não a festa.

Neutros têm viés quente (a cal caiada dos casarios), não cinza puro: cinza
neutro em fundo branco lê como "não pensado".

O QUE O SISTEMA EVITA, DE PROPÓSITO
------------------------------------
  - Cards coloridos: a superfície é branca; a cor carrega significado, não
    decoração.
  - Bordas em tudo: separação por divisor de 1px e por espaço. Caixa dentro
    de caixa é o visual de dashboard corporativo.
  - Gradiente: nenhum. Superfície chapada lê como precisão.
  - Informação simultânea: o essencial fica visível, o resto expande.

Referências de linguagem: Linear (hierarquia e ritmo vertical), Vercel
(minimalismo e respiro), Notion (organização da informação), Stripe
(indicadores e números tabulares), Airbnb/Zillow (descoberta de imóveis).
"""

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
CSS_TOKENS = """
:root{
  /* superfícies -- branco puro é o chão; os degraus são quentes */
  --fundo:#FFFFFF;
  --superficie:#FAFAF9;
  --superficie-2:#F4F3F0;
  --superficie-3:#EBE9E5;

  /* linhas: uma só espessura, sempre discreta */
  --linha:#E5E3DE;
  --linha-forte:#CFCCC5;

  /* tinta */
  --tinta:#15191C;
  --tinta-media:#4A535C;
  --tinta-suave:#727C87;
  --tinta-fraca:#9AA2AB;

  /* institucional -- Atlântico */
  --mar:#10495B;
  --mar-claro:#1B6B84;
  --mar-lavado:#EAF2F5;

  /* acento -- ocre de Olinda, usado com parcimônia */
  --ocre:#C2703D;
  --ocre-lavado:#FBF0E8;

  /* semânticas: separadas do acento de propósito */
  --bom:#1B7A5A;      --bom-lavado:#E8F4EF;
  --atencao:#9A6A12;  --atencao-lavado:#FBF1DE;
  --ruim:#A8443A;     --ruim-lavado:#FAECEA;

  --foco:#1B6B84;
  --sombra:0 1px 2px rgba(21,25,28,.05), 0 1px 8px rgba(21,25,28,.04);

  --sans:'Inter','Inter var',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
  --mono:ui-monospace,'SF Mono','Cascadia Mono','Segoe UI Mono',Menlo,Consolas,monospace;

  --r:6px;
  --r-card:14px;
  --gap:16px;
}

/* Modo noturno. Não é inversão: o azul institucional clareia para manter
   contraste, e as superfícies ganham viés frio -- de noite, neutro quente
   fica com aparência de sujo. */
@media (prefers-color-scheme: dark){
  :root:not([data-tema="claro"]){
    --fundo:#0D1114;
    --superficie:#141A1E;
    --superficie-2:#1B2227;
    --superficie-3:#232B31;
    --linha:#242C32;
    --linha-forte:#36414A;
    --tinta:#E9ECEE;
    --tinta-media:#AEB7BF;
    --tinta-suave:#8B959E;
    --tinta-fraca:#69737C;
    --mar:#7FC3D8;
    --mar-claro:#A5D8E7;
    --mar-lavado:#122A33;
    --ocre:#E3A277;
    --ocre-lavado:#2E2018;
    --bom:#6FCFA6;      --bom-lavado:#12291F;
    --atencao:#DCB05A;  --atencao-lavado:#2B2312;
    --ruim:#E8938A;     --ruim-lavado:#2E1B18;
    --foco:#7FC3D8;
    --sombra:0 1px 2px rgba(0,0,0,.4), 0 1px 8px rgba(0,0,0,.25);
  }
}
:root[data-tema="escuro"]{
  --fundo:#0D1114;
  --superficie:#141A1E;
  --superficie-2:#1B2227;
  --superficie-3:#232B31;
  --linha:#242C32;
  --linha-forte:#36414A;
  --tinta:#E9ECEE;
  --tinta-media:#AEB7BF;
  --tinta-suave:#8B959E;
  --tinta-fraca:#69737C;
  --mar:#7FC3D8;
  --mar-claro:#A5D8E7;
  --mar-lavado:#122A33;
  --ocre:#E3A277;
  --ocre-lavado:#2E2018;
  --bom:#6FCFA6;      --bom-lavado:#12291F;
  --atencao:#DCB05A;  --atencao-lavado:#2B2312;
  --ruim:#E8938A;     --ruim-lavado:#2E1B18;
  --foco:#7FC3D8;
  --sombra:0 1px 2px rgba(0,0,0,.4), 0 1px 8px rgba(0,0,0,.25);
}
"""

CSS_BASE = """
*{box-sizing:border-box;}
html{-webkit-text-size-adjust:100%;}
html,body{overflow-x:clip;}
body{
  margin:0; background:var(--fundo); color:var(--tinta);
  font-family:var(--sans); font-size:15px; line-height:1.5;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  -webkit-tap-highlight-color:transparent;
}
a{color:inherit;}
:focus-visible{outline:2px solid var(--foco); outline-offset:2px; border-radius:3px;}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;}}

.pagina{max-width:1080px; margin:0 auto; padding:0 24px 80px;}

/* ---------- cabeçalho ---------- */
.topo{
  position:sticky; top:0; z-index:20;
  background:color-mix(in srgb, var(--fundo) 88%, transparent);
  -webkit-backdrop-filter:saturate(180%) blur(12px);
  backdrop-filter:saturate(180%) blur(12px);
  border-bottom:1px solid var(--linha);
  padding:0 24px;
}
.topo-linha{
  display:flex; align-items:center; gap:14px;
  max-width:1080px; margin:0 auto; height:56px;
}
.marca{display:flex; align-items:center; gap:9px; font-weight:640; letter-spacing:-.015em;}
.marca-glifo{
  width:22px; height:22px; border-radius:5px; flex-shrink:0;
  background:var(--mar); display:grid; place-items:center;
}
.marca-glifo svg{width:13px; height:13px; stroke:#fff; fill:none; stroke-width:2;}
:root[data-tema="escuro"] .marca-glifo svg,
:root:not([data-tema="claro"]) .marca-glifo svg{stroke:#0D1114;}
@media (prefers-color-scheme: light){
  :root:not([data-tema="escuro"]) .marca-glifo svg{stroke:#fff;}
}
.marca-sub{
  font-family:var(--mono); font-size:11px; color:var(--tinta-fraca);
  letter-spacing:.02em; font-weight:400;
}
.topo-dir{margin-left:auto; display:flex; align-items:center; gap:10px;}
.btn-tema{
  width:32px; height:32px; border-radius:var(--r); cursor:pointer;
  border:1px solid var(--linha); background:transparent; color:var(--tinta-suave);
  display:grid; place-items:center; padding:0;
}
.btn-tema:hover{border-color:var(--linha-forte); color:var(--tinta);}
.btn-tema svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:1.7;}

.btn-obs{
  height:32px; padding:0 10px; border-radius:var(--r); cursor:pointer;
  border:1px solid var(--linha); background:transparent; color:var(--tinta-suave);
  display:inline-flex; align-items:center; gap:6px;
  font-family:var(--sans); font-size:12.5px; font-weight:550;
}
.btn-obs:hover{border-color:var(--linha-forte); color:var(--tinta);}
.btn-obs svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.8;}
.btn-obs[aria-expanded="true"]{
  background:var(--superficie-2); color:var(--tinta); border-color:var(--linha-forte);
}

/* ---------- observações ---------- */
/* Estava no rodapé. No celular isso significava rolar a lista inteira para
   descobrir por que um imóvel não aparecia -- ou seja, ninguém lia. */
.obs{
  margin:16px 0 0; padding:14px 16px;
  background:var(--superficie); border:1px solid var(--linha);
  border-radius:var(--r-card);
}
.obs-lista{margin:0; display:grid; gap:10px;}
.obs-lista > div{display:grid; grid-template-columns:150px 1fr; gap:12px;}
.obs-lista dt{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.06em;
  text-transform:uppercase; color:var(--tinta-fraca); padding-top:2px;
}
.obs-lista dd{margin:0; font-size:13px; color:var(--tinta-media); line-height:1.55;}
.obs-lista dd b{color:var(--tinta); font-weight:600;}

/* ---------- pulso: os números que importam ---------- */
.pulso{
  display:grid; grid-template-columns:repeat(auto-fit, minmax(112px, 1fr));
  gap:18px 0; padding:26px 0 22px;
}
.pulso-item{padding:0 20px; border-left:1px solid var(--linha);}
.pulso-item:first-child{padding-left:0; border-left:0;}
.pulso-rot{
  font-family:var(--mono); font-size:10.5px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--tinta-fraca); margin-bottom:4px;
}
.pulso-val{
  font-size:26px; font-weight:620; letter-spacing:-.03em;
  font-variant-numeric:tabular-nums; line-height:1.1;
}
.pulso-val small{font-size:13px; font-weight:400; color:var(--tinta-suave); letter-spacing:0;}
.pulso-item.destaque .pulso-val{color:var(--ocre);}

/* ---------- abas ---------- */
/* Duas leituras diferentes do mesmo banco: o catálogo (o que alugar) e a
   operação (quais fontes ainda valem o tempo de runner). Misturar as duas
   numa página só faria a segunda ser rolada por cima todo dia. */
.abas{
  display:flex; gap:2px; border-bottom:1px solid var(--linha);
  margin-bottom:14px;
}
.aba{
  height:38px; padding:0 14px; cursor:pointer;
  border:0; border-bottom:2px solid transparent; background:transparent;
  color:var(--tinta-suave); font-family:var(--sans); font-size:14px; font-weight:550;
  display:inline-flex; align-items:center; gap:7px;
}
.aba:hover{color:var(--tinta);}
.aba[aria-selected="true"]{color:var(--tinta); border-bottom-color:var(--mar);}
.aba-n{
  font-family:var(--mono); font-size:11px; color:var(--tinta-fraca);
  font-variant-numeric:tabular-nums;
}

/* ---------- rendimento por fonte ---------- */
/* Saúde responde "quebrou?"; rendimento responde "entrega?". A decisão de
   desligar uma fonte se toma na segunda pergunta, e ela precisa de duas
   colunas lado a lado: o que a fonte traz e o que só ela traz. */
.rend{margin:6px 0 10px;}
.rend-nota{
  color:var(--tinta-suave); font-size:13px; line-height:1.6;
  margin:0 0 16px; max-width:62ch;
}
.rend-rolagem{overflow-x:auto; -webkit-overflow-scrolling:touch;}
.rend table{border-collapse:collapse; width:100%; min-width:640px; font-size:12.5px;}
.rend th{
  font-family:var(--mono); font-size:10px; letter-spacing:.07em;
  text-transform:uppercase; color:var(--tinta-fraca); font-weight:600;
  text-align:left; padding:7px 10px; border-bottom:1px solid var(--linha);
  white-space:nowrap;
}
.rend td{
  padding:9px 10px; border-bottom:1px solid var(--linha);
  font-variant-numeric:tabular-nums; vertical-align:middle;
}
.rend td.n{text-align:right;}
.rend tr:hover td{background:var(--superficie);}
.rend .fonte{font-weight:600;}
/* Barra proporcional: comparar 30 com 2 numa coluna de números exige
   contar dígitos; a barra resolve no relance. */
.barra{
  display:block; height:5px; border-radius:3px; background:var(--mar);
  min-width:2px; margin-top:4px;
}
.barra.vazia{background:var(--linha-forte);}
.rend .aviso td{background:var(--atencao-lavado);}
.rend .aviso .fonte{color:var(--atencao);}
.rend-legenda{
  color:var(--tinta-fraca); font-size:11.5px; line-height:1.7;
  margin-top:12px; font-family:var(--mono);
}

/* ---------- barra de filtros ---------- */
.barra-filtros{
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  padding:14px 0 12px;
}
.btn-filtros{
  display:inline-flex; align-items:center; gap:7px;
  height:36px; padding:0 12px; border-radius:9px; cursor:pointer;
  border:1px solid var(--linha-forte); background:var(--fundo);
  color:var(--tinta-media); font-family:var(--sans); font-size:13.5px; font-weight:550;
}
.btn-filtros:hover{color:var(--tinta); background:var(--superficie);}
.btn-filtros svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.8;}
.seta{
  display:inline-flex; color:var(--tinta-fraca);
  transition:transform .16s ease;
}
.seta svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round;}
[aria-expanded="true"] > .seta,
[aria-expanded="true"] .seta{transform:rotate(90deg);}
/* Contador: esconder filtro sem dizer que existe filtro faria uma busca
   estreita parecer fonte vazia. */
.filtros-n{
  min-width:18px; height:18px; padding:0 5px; border-radius:9px;
  background:var(--mar); color:#fff;
  font-family:var(--mono); font-size:10.5px; font-weight:700;
  display:inline-grid; place-items:center;
}
:root[data-tema="escuro"] .filtros-n,
:root:not([data-tema="claro"]) .filtros-n{color:#0D1114;}
@media (prefers-color-scheme: light){
  :root:not([data-tema="escuro"]) .filtros-n{color:#fff;}
}
.barra-filtros .contagem{padding:0; margin-left:auto;}

/* display:flex/grid vence o atributo [hidden] -- sem isto a barra nasce
   aberta e o contador aparece marcando zero */
.filtros[hidden],.filtros-n[hidden],.barra-filtros[hidden]{display:none;}

/* ---------- filtros ---------- */
.filtros{
  display:flex; flex-wrap:wrap; gap:8px; align-items:center;
  padding:0 0 14px;
}
.campo{
  display:inline-flex; align-items:center; gap:6px;
  height:34px; padding:0 10px;
  background:var(--superficie); border:1px solid var(--linha);
  border-radius:var(--r); color:var(--tinta-media); font-size:13.5px;
}
.campo:focus-within{border-color:var(--foco); background:var(--fundo);}
.campo select,.campo input{
  border:0; background:transparent; color:var(--tinta);
  font-family:var(--sans); font-size:13.5px; height:32px; outline:none;
  min-width:0; padding:0;
}
.campo select{cursor:pointer; max-width:170px;}
.campo input{width:74px; font-family:var(--mono); font-variant-numeric:tabular-nums;}
.campo.busca input{width:180px; font-family:var(--sans);}
.campo svg{width:14px;height:14px;stroke:var(--tinta-fraca);fill:none;stroke-width:1.7;flex-shrink:0;}
.sep{color:var(--tinta-fraca); font-size:12px;}

/* Chips de recorte: mostram o modo de leitura ativo. Substituem abas --
   ocupam menos e deixam combinar. */
.chip{
  height:34px; padding:0 12px; border-radius:var(--r); cursor:pointer;
  border:1px solid var(--linha); background:var(--superficie);
  color:var(--tinta-media); font-size:13px; font-weight:500;
  display:inline-flex; align-items:center; gap:6px; font-family:var(--sans);
}
.chip:hover{border-color:var(--linha-forte); color:var(--tinta);}
.chip[aria-pressed="true"]{
  background:var(--mar); border-color:var(--mar); color:#fff;
}
:root[data-tema="escuro"] .chip[aria-pressed="true"],
:root:not([data-tema="claro"]) .chip[aria-pressed="true"]{color:#0D1114;}
@media (prefers-color-scheme: light){
  :root:not([data-tema="escuro"]) .chip[aria-pressed="true"]{color:#fff;}
}
.chip-n{
  font-family:var(--mono); font-size:11px; opacity:.7;
  font-variant-numeric:tabular-nums;
}
.btn-limpar{
  background:transparent; border:0; color:var(--tinta-fraca);
  font-size:12.5px; cursor:pointer; padding:0 4px; font-family:var(--sans);
}
.btn-limpar:hover{color:var(--tinta);}

.contagem{
  font-family:var(--mono); font-size:11.5px; color:var(--tinta-fraca);
  padding:12px 0 4px; letter-spacing:.02em;
}

/* ---------- catálogo ---------- */
/* Card fechado, no espírito dos portais (Zap/Viva Real): foto, dados,
   preço e ação dentro de uma caixa com borda e sombra. A versão anterior
   separava os imóveis só por um divisor de 1px -- lia como jornal e, no
   celular, não dava para dizer onde um anúncio terminava e o outro
   começava. Borda + sombra + espaço entre cards resolvem isso sem cor. */
.lista{display:grid; gap:16px; padding-top:4px;}

.imovel{
  display:grid; grid-template-columns:232px 1fr;
  background:var(--fundo); border:1px solid var(--linha);
  border-radius:var(--r-card); overflow:hidden; box-shadow:var(--sombra);
  transition:box-shadow .16s ease, border-color .16s ease;
}
.imovel:hover{
  border-color:var(--linha-forte);
  box-shadow:0 2px 4px rgba(21,25,28,.06), 0 10px 28px rgba(21,25,28,.08);
}

/* Foto: 4:3 no desktop, 16:10 no celular. object-fit evita distorcer o que
   cada portal entrega em proporção diferente. */
.foto{position:relative; background:var(--superficie-2); aspect-ratio:4/3;}
.foto img{width:100%; height:100%; object-fit:cover; display:block;}
.foto-vazia{
  position:absolute; inset:0; display:grid; place-items:center;
  color:var(--tinta-fraca);
}
/* Sem foto (fonte que não publica imagem, ou link morto) o espaço encolhe:
   manter 16/10 de marcador cinza gastaria meia tela de celular para dizer
   "não temos foto". */
.foto.sem-foto img{display:none;}
.foto.sem-foto{aspect-ratio:auto; min-height:74px;}

/* Setas da galeria: aparecem no hover no desktop e ficam sempre visíveis no
   toque, onde não existe hover para revelar nada. */
.foto-nav{
  position:absolute; top:50%; transform:translateY(-50%);
  width:30px; height:30px; border-radius:50%; cursor:pointer; padding:0;
  border:0; background:rgba(13,17,20,.55); color:#fff;
  display:grid; place-items:center; opacity:0; transition:opacity .15s ease;
}
.foto-nav svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:2.2;
  stroke-linecap:round;stroke-linejoin:round;}
.foto-nav.ant{left:8px;}
.foto-nav.ant svg{transform:rotate(180deg);}
.foto-nav.prox{right:8px;}
.imovel:hover .foto-nav{opacity:1;}
.foto-nav:hover{background:rgba(13,17,20,.78);}
.foto-conta{
  position:absolute; right:8px; bottom:8px;
  background:rgba(13,17,20,.6); color:#fff;
  font-family:var(--mono); font-size:10.5px; padding:2px 7px; border-radius:10px;
}
@media (hover:none){
  .foto-nav{opacity:1; width:34px; height:34px;}
}
.foto-vazia svg{width:26px;height:26px;stroke:currentColor;fill:none;stroke-width:1.4;}
/* Selos de ação sobre a foto -- é o que o olho procura primeiro na grade. */
.foto-selos{
  position:absolute; top:9px; left:9px; right:9px;
  display:flex; flex-wrap:wrap; gap:5px;
}

.imovel-corpo{
  padding:14px 16px 14px; display:flex; flex-direction:column;
  gap:6px; min-width:0;
}
.imovel-cab{display:flex; align-items:flex-start; gap:8px; min-width:0;}
.imovel-titulo{
  font-size:16px; font-weight:600; letter-spacing:-.014em; margin:0;
  line-height:1.35; display:-webkit-box; -webkit-line-clamp:2;
  -webkit-box-orient:vertical; overflow:hidden;
}
.imovel-local{
  color:var(--tinta-suave); font-size:12.5px;
  display:flex; align-items:center; gap:5px; min-width:0; flex-wrap:wrap;
}
.imovel-local svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:1.7;flex-shrink:0;}
.imovel-local .rua{color:var(--tinta-fraca);}
.imovel-local .rua-ausente{font-style:italic; opacity:.7;}

/* Ficha técnica: pastilhas, não texto corrido -- é o padrão que o olho já
   conhece dos portais e sobrevive melhor à quebra de linha no celular. */
.ficha{display:flex; flex-wrap:wrap; gap:6px;}
.ficha span{
  font-size:12px; color:var(--tinta-media);
  background:var(--superficie-2); border-radius:999px; padding:3px 9px;
  font-variant-numeric:tabular-nums; white-space:nowrap;
}
.ficha b{font-weight:650; color:var(--tinta);}

/* Rodapé do card: preço à esquerda, ação à direita. */
/* Por que este imóvel foi sugerido. Recomendação sem motivo é adivinhação:
   sem a linha, o selo vira enfeite e a pessoa não sabe se concorda. */
.porque{
  display:flex; align-items:flex-start; gap:6px;
  font-size:12px; color:var(--ocre); line-height:1.45;
}
.porque svg{width:12px;height:12px;fill:currentColor;stroke:none;flex-shrink:0;margin-top:2px;}

.imovel-rodape{
  margin-top:auto; padding-top:12px;
  display:flex; align-items:flex-end; gap:12px; flex-wrap:wrap;
}
.preco-bloco{min-width:0;}
.preco-val{
  font-size:23px; font-weight:680; letter-spacing:-.035em;
  font-variant-numeric:tabular-nums; white-space:nowrap; line-height:1.15;
}
.preco-un{font-size:12px; color:var(--tinta-suave); font-weight:400; margin-left:4px;}
.preco-m2{
  font-family:var(--mono); font-size:11px; color:var(--tinta-suave);
  font-variant-numeric:tabular-nums; white-space:nowrap;
}
.acoes{margin-left:auto; display:flex; align-items:center; gap:8px; flex-wrap:wrap;}

.btn-abrir{
  display:inline-flex; align-items:center; justify-content:center; gap:6px;
  height:38px; padding:0 14px; border-radius:9px;
  background:var(--mar); color:#fff; font-size:13px; font-weight:600;
  text-decoration:none; white-space:nowrap;
}
:root[data-tema="escuro"] .btn-abrir,
:root:not([data-tema="claro"]) .btn-abrir{color:#0D1114;}
@media (prefers-color-scheme: light){
  :root:not([data-tema="escuro"]) .btn-abrir{color:#fff;}
}
.btn-abrir svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2;}

/* Botão de ofertas: alvo explícito. A versão anterior fazia a linha toda
   virar botão com uma setinha de 10px -- no toque isso disputava com a
   seleção de texto e com o link, e parecia quebrado. */
.btn-ofertas{
  display:inline-flex; align-items:center; gap:6px;
  height:38px; padding:0 12px; border-radius:9px; cursor:pointer;
  border:1px solid var(--linha-forte); background:var(--fundo);
  color:var(--tinta-media); font-family:var(--sans); font-size:13px; font-weight:550;
  white-space:nowrap;
}
.btn-ofertas:hover{color:var(--tinta); background:var(--superficie);}


/* ---------- sinais ---------- */
/* Um selo só ganha cor quando exige AÇÃO. O resto é monocromático, para o
   olho encontrar o que importa sem varrer tudo. */
.selos{display:flex; flex-wrap:wrap; gap:5px;}
.selo{
  font-size:10.5px; letter-spacing:.02em; font-weight:600;
  padding:3px 7px; border-radius:5px;
  background:var(--superficie-2); color:var(--tinta-suave);
  white-space:nowrap;
}
/* O selo da sugestão é o único que usa o acento quente cheio: é a única
   marca da tela que diz "olhe este aqui primeiro". */
.selo-melhor{background:var(--ocre); color:#fff; box-shadow:0 1px 3px rgba(0,0,0,.22);}
.selo-novo{background:var(--mar); color:#fff;}
.selo-queda{background:var(--ocre); color:#fff;}
.foto-selos .selo{box-shadow:0 1px 3px rgba(0,0,0,.22);}
.selo-fontes{background:var(--bom-lavado); color:var(--bom);}
.selo-economia{background:var(--ocre-lavado); color:var(--ocre);}
.selo-alerta{background:var(--atencao-lavado); color:var(--atencao);}
.selo-fonte{
  font-weight:500; background:transparent; color:var(--tinta-fraca);
  border:1px solid var(--linha);
}

/* ---------- ofertas (expansão dentro do card) ---------- */
/* Lista, não tabela: tabela de 4 colunas só cabia com rolagem horizontal,
   que é exatamente o que se quer evitar no celular. */
.ofertas{
  grid-column:1 / -1; border-top:1px solid var(--linha);
  background:var(--superficie); padding:12px 16px 14px;
  display:grid; gap:8px;
}
/* display:grid vence o atributo [hidden]; sem isto o painel nasce aberto */
.ofertas[hidden]{display:none;}
.oferta{
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  padding:10px 12px; border:1px solid var(--linha);
  border-radius:10px; background:var(--fundo);
}
.oferta-fonte{font-size:13px; font-weight:600; min-width:0;}
.oferta-preco{
  margin-left:auto; font-weight:670; font-size:14px;
  font-variant-numeric:tabular-nums; white-space:nowrap;
}
.oferta-obs{flex-basis:100%; font-size:11.5px; color:var(--tinta-fraca);}
.oferta-link{
  font-size:12.5px; font-weight:600; color:var(--mar); text-decoration:none;
  white-space:nowrap;
}
.oferta-link:hover{text-decoration:underline;}
.oferta.melhor{border-color:var(--bom); background:var(--bom-lavado);}
.oferta.melhor .oferta-preco{color:var(--bom);}
.marca-melhor{
  font-size:10px; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
  color:var(--bom); margin-left:6px;
}

.faixa{
  display:block; width:64px; height:16px; margin-top:3px; flex-shrink:0;
  overflow:visible;
}

/* ---------- estado vazio ---------- */
.estado-vazio{
  padding:64px 20px; text-align:center; color:var(--tinta-suave); font-size:14px;
}
.estado-vazio svg{width:26px;height:26px;stroke:var(--tinta-fraca);fill:none;stroke-width:1.5;margin-bottom:10px;}

/* ---------- saúde ---------- */
.saude{margin-top:36px; border-top:1px solid var(--linha); padding-top:14px;}
.saude summary{
  cursor:pointer; font-family:var(--mono); font-size:11px;
  letter-spacing:.07em; text-transform:uppercase; color:var(--tinta-fraca);
  list-style:none; display:flex; align-items:center; gap:7px;
}
.saude summary::-webkit-details-marker{display:none;}
.saude summary:hover{color:var(--tinta);}
.ponto{width:6px;height:6px;border-radius:50%;background:var(--bom);flex-shrink:0;}
.ponto.alerta{background:var(--atencao);}
.saude-rolagem{overflow-x:auto; -webkit-overflow-scrolling:touch; margin-top:12px;}
.saude table{border-collapse:collapse;width:100%;min-width:560px;font-size:12px;}
.saude th{
  font-family:var(--mono); font-size:10px; letter-spacing:.07em;
  text-transform:uppercase; color:var(--tinta-fraca); font-weight:600;
  text-align:left; padding:6px 10px; border-bottom:1px solid var(--linha);
}
.saude td{padding:6px 10px; border-bottom:1px solid var(--linha); font-variant-numeric:tabular-nums;}
.saude td.n{text-align:right;}
.st{font-family:var(--mono);font-size:10px;font-weight:600;padding:1px 6px;border-radius:3px;}
.st-ok{background:var(--bom-lavado);color:var(--bom);}
.st-alerta{background:var(--atencao-lavado);color:var(--atencao);}
.st-erro{background:var(--ruim-lavado);color:var(--ruim);}
.st-neutro{background:var(--superficie-2);color:var(--tinta-fraca);}

.rodape{
  margin-top:22px; color:var(--tinta-fraca); font-size:11.5px;
  font-family:var(--mono); line-height:1.7;
}

/* ---------- responsivo ---------- */
/* Alvos reais: Poco X6 Pro (Chrome Android, ~412px de largura CSS) e
   iPhone 11 (Safari, 414px, com notch). Três regras carregam o peso:

     1. campo de formulário com 16px -- abaixo disso o Safari do iPhone dá
        zoom ao focar e o usuário fica preso num layout deslocado;
     2. alvo de toque de 40-44px -- 34px de mouse erra no polegar;
     3. env(safe-area-inset-*) -- no iPhone em paisagem o notch e a barra
        de gestos comem a lateral e o rodapé.

   Hover fica atrás de (hover:none) invertido: no toque o estado "hover"
   gruda depois do tap e o card fica pintado até o próximo toque. */

@media (hover:none){
  .imovel:hover{border-color:var(--linha); box-shadow:var(--sombra);}
  .chip:hover{border-color:var(--linha); color:var(--tinta-media);}
  .btn-tema:hover{border-color:var(--linha); color:var(--tinta-suave);}
  .btn-ofertas:hover{background:var(--fundo); color:var(--tinta-media);}
  .btn-limpar:hover{color:var(--tinta-fraca);}
  .saude summary:hover{color:var(--tinta-fraca);}
  .oferta-link:hover{text-decoration:none;}
}

/* Cards lado a lado quando sobra largura: aí a foto vai para o topo, como
   na grade dos portais. */
@media (min-width:1000px){
  .lista{grid-template-columns:1fr 1fr;}
  .imovel{grid-template-columns:1fr; align-content:start;}
  .foto{aspect-ratio:16/9;}
}

@media (max-width:720px){
  .pagina{
    padding-left:max(16px, env(safe-area-inset-left));
    padding-right:max(16px, env(safe-area-inset-right));
    padding-bottom:calc(56px + env(safe-area-inset-bottom));
  }
  .topo{
    padding-left:max(16px, env(safe-area-inset-left));
    padding-right:max(16px, env(safe-area-inset-right));
  }
  .topo-linha{height:52px; gap:8px;}
  .btn-obs{height:40px;}
  .obs{padding:12px 14px;}
  .obs-lista > div{grid-template-columns:1fr; gap:2px;}
  .marca{font-size:14.5px; gap:8px; min-width:0;}
  .btn-tema{width:40px; height:40px;}

  /* Pulso em duas colunas: com auto-fit o rótulo "Mediana R$/m²" quebrava
     em três linhas. A faixa de preço ocupa a linha inteira porque é o
     único item com dois números. */
  .pulso{grid-template-columns:1fr 1fr; gap:0; padding:14px 0 16px;}
  .pulso-item{
    padding:10px 0 10px 14px;
    border-left:1px solid var(--linha); border-top:1px solid var(--linha);
  }
  .pulso-item:nth-child(odd){padding-left:0; border-left:0;}
  .pulso-item:nth-child(1),.pulso-item:nth-child(2){border-top:0;}
  .pulso-item:last-child{grid-column:1 / -1; padding-left:0; border-left:0;}
  .pulso-val{font-size:21px;}

  /* Filtros: três chips numa linha, campos em duas colunas. */
  .filtros{gap:8px; padding-bottom:12px;}
  .chip{
    flex:1 1 calc(33.333% - 6px); justify-content:center;
    height:40px; font-size:13.5px; padding:0 8px;
  }
  /* sem flex-grow: campo sozinho na linha não estica para 100% e
     quebra o ritmo de duas colunas */
  .campo{flex:0 1 calc(50% - 4px); height:44px; padding:0 12px;}
  .campo select,.campo input{font-size:16px; height:42px; width:100%; max-width:none;}
  /* rótulo longo ('Todas as cidades') não pode passar por baixo da seta */
  .campo select{text-overflow:ellipsis; padding-right:2px;}
  .campo.preco,.campo.busca{flex:0 1 100%;}
  .campo.preco input,.campo.busca input{width:100%;}
  .btn-limpar{height:40px; padding:0 10px; font-size:13px;}

  /* Card empilhado: foto larga em cima, como nos apps dos portais. */
  .lista{gap:14px;}
  .imovel{grid-template-columns:1fr;}
  .foto{aspect-ratio:16/10;}
  .imovel-corpo{padding:13px 14px 14px;}
  /* Por que este imóvel foi sugerido. Recomendação sem motivo é adivinhação:
   sem a linha, o selo vira enfeite e a pessoa não sabe se concorda. */
.porque{
  display:flex; align-items:flex-start; gap:6px;
  font-size:12px; color:var(--ocre); line-height:1.45;
}
.porque svg{width:12px;height:12px;fill:currentColor;stroke:none;flex-shrink:0;margin-top:2px;}

.imovel-rodape{padding-top:10px;}
  .acoes{margin-left:0; width:100%;}
  .btn-abrir,.btn-ofertas{height:42px; flex:1 1 auto; justify-content:center;}
  .ofertas{padding:12px 14px 14px;}
  .aba{padding:0 10px; font-size:13.5px;}
  .contagem{padding-top:10px;}
}

/* Telas estreitas (o Poco cai aqui com fonte do sistema aumentada). */
@media (max-width:430px){
  .marca-sub{display:none;}
  .btn-obs-txt{display:none;}
  .btn-obs{width:40px; padding:0; justify-content:center;}
  .imovel-titulo{font-size:15.5px;}
  .preco-val{font-size:21px;}
}
"""

# Ícones: traço de 1.7px, 16px de caixa, mesma família geométrica.
ICONES = {
    "marca": '<svg viewBox="0 0 20 20"><path d="M3 9.5 10 3.5l7 6"/><path d="M5 9v7.5h10V9"/><path d="M8.5 16.5v-4h3v4"/></svg>',
    "local": '<svg viewBox="0 0 20 20"><path d="M10 17.5s5.5-4.8 5.5-9a5.5 5.5 0 0 0-11 0c0 4.2 5.5 9 5.5 9Z"/><circle cx="10" cy="8.5" r="1.9"/></svg>',
    "busca": '<svg viewBox="0 0 20 20"><circle cx="8.8" cy="8.8" r="5.4"/><path d="m16.5 16.5-3.9-3.9"/></svg>',
    "externo": '<svg viewBox="0 0 20 20"><path d="M11.5 4H16v4.5"/><path d="M16 4 9.5 10.5"/><path d="M15 12v3.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3.5"/></svg>',
    "filtro": '<svg viewBox="0 0 20 20"><path d="M3.5 5.5h13M6 10h8M8.5 14.5h3"/></svg>',
    "moeda": '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="6.8"/><path d="M10 6v8M12 8.2c0-1-.9-1.7-2-1.7s-2 .7-2 1.6c0 2.2 4 1.2 4 3.4 0 .9-.9 1.6-2 1.6s-2-.7-2-1.7"/></svg>',
    "seta": '<svg viewBox="0 0 20 20"><path d="m8 5 5 5-5 5"/></svg>',
    "estrela": '<svg viewBox="0 0 20 20"><path d="m10 3 2.2 4.5 5 .7-3.6 3.5.9 4.9L10 14.3l-4.5 2.3.9-4.9L2.8 8.2l5-.7z"/></svg>',
    "info": '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7.2"/><path d="M10 9.2v4.3M10 6.6v.1"/></svg>',
    "sol": '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="3.6"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M15.7 4.3l-1.4 1.4M5.7 14.3l-1.4 1.4"/></svg>',
    "lua": '<svg viewBox="0 0 20 20"><path d="M16.5 11.8A6.8 6.8 0 0 1 8.2 3.5a6.8 6.8 0 1 0 8.3 8.3Z"/></svg>',
    "foto": '<svg viewBox="0 0 20 20"><rect x="2.5" y="4" width="15" height="12" rx="2"/><circle cx="7" cy="8.2" r="1.3"/><path d="m3.5 14 4-3.6 3 2.6 2.6-2.2 3.4 3"/></svg>',
    "vazio": '<svg viewBox="0 0 20 20"><circle cx="8.8" cy="8.8" r="5.4"/><path d="m16.5 16.5-3.9-3.9"/></svg>',
}
