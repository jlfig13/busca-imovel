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

  --sans:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,'Helvetica Neue',Arial,sans-serif;
  --mono:ui-monospace,'SF Mono','Cascadia Mono','Segoe UI Mono',Menlo,Consolas,monospace;

  --r:6px;
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
}
a{color:inherit;}
:focus-visible{outline:2px solid var(--foco); outline-offset:2px; border-radius:3px;}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;}}

.pagina{max-width:1080px; margin:0 auto; padding:0 24px 80px;}

/* ---------- cabeçalho ---------- */
.topo{
  position:sticky; top:0; z-index:20;
  background:color-mix(in srgb, var(--fundo) 88%, transparent);
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

/* ---------- filtros ---------- */
.filtros{
  display:flex; flex-wrap:wrap; gap:8px; align-items:center;
  padding:0 0 14px; border-bottom:1px solid var(--linha);
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

/* ---------- lista de imóveis ---------- */
/* Sem caixas: divisor de 1px e fundo no hover. Caixa dentro de caixa é o
   visual de dashboard corporativo que a direção pede para evitar.

   Flex (e não grid com row-span) porque row-span estica as linhas até a
   altura da coluna do preço, criando um vão vertical enorme entre os
   imóveis -- o oposto do ritmo compacto que a referência (Linear) pede. */
.imovel{
  display:flex; align-items:flex-start; gap:24px;
  padding:14px 12px; margin:0 -12px;
  border-bottom:1px solid var(--linha); border-radius:var(--r);
}
.imovel:hover{background:var(--superficie);}
.imovel.abrivel{cursor:pointer;}
.imovel-corpo{flex:1; min-width:0;}
.imovel-lado{
  display:flex; flex-direction:column; align-items:flex-end; gap:5px;
  flex-shrink:0; text-align:right;
}

.imovel-cab{display:flex; align-items:center; gap:8px; min-width:0;}
.seta{
  width:10px; flex-shrink:0; color:var(--tinta-fraca); font-size:9px;
  transition:transform .15s ease;
}
.imovel[aria-expanded="true"] .seta{transform:rotate(90deg);}
.imovel-titulo{
  font-size:15.5px; font-weight:590; letter-spacing:-.012em; margin:0;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.imovel-local{
  color:var(--tinta-suave); font-size:12.5px; margin-top:3px;
  display:flex; align-items:center; gap:5px; min-width:0;
}
.imovel-local svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:1.7;flex-shrink:0;}
.imovel-local .rua{color:var(--tinta-fraca);}
/* nome específico de propósito: '.vazio' genérico colidia com o
   estado-vazio da lista (padding 64px) e inflava a linha do endereço */
.imovel-local .rua-ausente{font-style:italic; opacity:.7;}

/* Ficha técnica em linha: números tabulares, separador discreto. */
.ficha{
  display:flex; flex-wrap:wrap; gap:0 0;
  font-size:12.5px; color:var(--tinta-media); margin-top:5px;
}
.ficha span{
  padding-right:10px; margin-right:10px; border-right:1px solid var(--linha);
  font-variant-numeric:tabular-nums;
}
.ficha span:last-child{border-right:0; padding-right:0; margin-right:0;}
.ficha b{font-weight:600; color:var(--tinta);}

.preco-val{
  font-size:19px; font-weight:640; letter-spacing:-.03em;
  font-variant-numeric:tabular-nums; white-space:nowrap; line-height:1.2;
}
.preco-un{font-size:11px; color:var(--tinta-fraca); font-weight:400; display:block;}
.preco-m2{
  font-family:var(--mono); font-size:11px; color:var(--tinta-suave);
  font-variant-numeric:tabular-nums; white-space:nowrap;
}

/* ---------- sinais ---------- */
/* Um selo só ganha cor quando exige AÇÃO. O resto é monocromático, para o
   olho encontrar o que importa sem varrer tudo. */
.selos{display:flex; flex-wrap:wrap; gap:5px; margin-top:7px;}
.selo{
  font-family:var(--mono); font-size:10px; letter-spacing:.05em;
  text-transform:uppercase; font-weight:600;
  padding:2px 6px; border-radius:3px;
  background:var(--superficie-2); color:var(--tinta-suave);
  white-space:nowrap;
}
.selo-novo{background:var(--mar-lavado); color:var(--mar);}
.selo-queda{background:var(--ocre-lavado); color:var(--ocre);}
.selo-fontes{background:var(--bom-lavado); color:var(--bom);}
.selo-alerta{background:var(--atencao-lavado); color:var(--atencao);}
.selo-fonte{
  text-transform:none; letter-spacing:0; font-weight:500;
  background:transparent; color:var(--tinta-fraca);
  border:1px solid var(--linha);
}

/* ---------- ofertas (expansão) ---------- */
.ofertas{
  margin:10px 0 2px;
  background:var(--superficie-2); border-radius:var(--r); overflow:hidden;
}
.ofertas table{border-collapse:collapse; width:100%; font-size:12.5px;}
.ofertas th{
  font-family:var(--mono); font-size:10px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--tinta-fraca); font-weight:600;
  text-align:left; padding:8px 12px 6px;
}
.ofertas td{
  padding:8px 12px; border-top:1px solid var(--linha);
  font-variant-numeric:tabular-nums;
}
.ofertas .of-preco{text-align:right; font-weight:600; font-family:var(--mono);}
.ofertas .of-obs{color:var(--tinta-fraca); font-size:11.5px;}
.ofertas .of-link{text-align:right;}
.ofertas .of-link a{
  color:var(--mar); text-decoration:none; font-size:11.5px; font-weight:500;
}
.ofertas .of-link a:hover{text-decoration:underline;}
.ofertas tr.melhor td{background:var(--bom-lavado);}
.ofertas tr.melhor .of-preco{color:var(--bom);}
.ofertas .marca-melhor{
  font-family:var(--mono); font-size:9.5px; letter-spacing:.06em;
  color:var(--bom); text-transform:uppercase; margin-left:6px;
}

.abrir{
  display:inline-flex; align-items:center; gap:5px;
  font-size:12px; font-weight:550; color:var(--mar);
  text-decoration:none; padding:4px 0; white-space:nowrap;
}
.abrir:hover{text-decoration:underline;}
.abrir svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2;}

.faixa{width:56px;height:20px;vertical-align:-4px;margin-left:2px;}

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
.saude-rolagem{overflow-x:auto; margin-top:12px;}
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
@media (max-width:720px){
  .pagina{padding:0 16px 60px;}
  .topo{padding:0 16px;}
  .pulso{gap:14px 0;}
  .pulso-item{padding:0 14px;}
  .imovel{flex-direction:column; gap:8px; padding:14px 8px; margin:0 -8px;}
  .imovel-lado{align-items:flex-start; text-align:left; flex-direction:row;
               align-items:baseline; gap:10px; flex-wrap:wrap;}
  .preco-un{display:inline; margin-left:3px;}
  .pulso-item{padding-right:20px; margin-right:20px;}
  .pulso-val{font-size:21px;}
  .campo.busca input{width:120px;}
  .ofertas{overflow-x:auto;}
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
    "sol": '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="3.6"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M15.7 4.3l-1.4 1.4M5.7 14.3l-1.4 1.4"/></svg>',
    "lua": '<svg viewBox="0 0 20 20"><path d="M16.5 11.8A6.8 6.8 0 0 1 8.2 3.5a6.8 6.8 0 1 0 8.3 8.3Z"/></svg>',
    "vazio": '<svg viewBox="0 0 20 20"><circle cx="8.8" cy="8.8" r="5.4"/><path d="m16.5 16.5-3.9-3.9"/></svg>',
}
