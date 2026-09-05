# Estado Atual

**Atualizado em:** 2026-09-05
**Branch:** `claude/remote-control-hgauah`
**No ar:** https://jlfig13.github.io/busca-imovel/

---

## O que acabou de entrar

| PR | O quê |
|---|---|
| [#3](https://github.com/jlfig13/busca-imovel/pull/3) | Catálogo em cards + dashboard responsivo (Poco X6 Pro / iPhone 11) |
| [#4](https://github.com/jlfig13/busca-imovel/pull/4) | Cron 07:00 → 07:13 BRT, fora da hora cheia |
| [#5](https://github.com/jlfig13/busca-imovel/pull/5) | `historico_precos` aposentada, aba "Fontes" com rendimento, filtros na URL |
| [#6](https://github.com/jlfig13/busca-imovel/pull/6) | CLAUDE.md + este arquivo, `.claude/progress/` versionado |

**05/09:** relato de imóveis faltando (8 URLs, 7 delas nunca vistas). A causa
era grande e estava calada.

**Paginação: todas as fontes de Playwright traziam só a p1.** O laço montava
a página seguinte como `{base}&pagina={n}`. O OLX pagina por `?o=`, e os
portais do Grupo ZAP também ignoram `pagina` nessa posição -- os três
devolviam a MESMA primeira página, o scraper via "0 links novos" e concluía
"acabaram os imóveis". Medido na rodada #51: Viva Real 30/0, Zap 30/0, OLX
49/0.

A correção foi em duas etapas, e a segunda só apareceu porque a primeira foi
instrumentada:

1. Seguir o link de "próxima página" que o site publica (`rel="next"` ou o
   botão), em vez de adivinhar parâmetro. Cada avanço registra por onde foi.
2. A rodada #52 mostrou que **não bastava**: Zap e Viva Real ACHARAM o link e
   navegaram (`p2 via ir`), e a lista repetiu -- são SPA, o `?pagina=2` só
   vale no cliente e nós líamos o HTML da p1. Agora o scraper espera o
   primeiro href da lista TROCAR; se não trocar, tenta o clique no controle,
   que é o que dispara o roteador do site. O OLX não publica link legível
   nenhum: para ele ficou a reserva por parâmetro (`param_pagina: "o"`).

Junto, quatro pedidos:

- **OLX Olinda** como fonte nova. A busca de Recife é do MUNICÍPIO, não da
  região: anúncio de Casa Caiada só entrava quando vazava, e sumia quando
  não -- o caso do "aluguel-apt-casa-caiada", visto uma vez em 03/08.
- **Cadência de 2 em 2 horas** (12x/dia). Consequência a vigiar: 12 commits
  diários do banco binário. A poda diária e o VACUUM de domingo passam a ser
  o que segura o tamanho do repositório.
- **Hora da última rodada** no cabeçalho e no rodapé, em BRT (o runner é UTC;
  sem o desconto, a rodada das 08:13 apareceria como 11:13). Fora do pulso de
  propósito: "atualizado" não é métrica para virar número grande, e três
  lugares com a mesma informação é redundância.
- **Fotos.** Não era coleta: 54 dos 62 anúncios TÊM url de foto no banco. É
  hotlink recusado -- servidas de jlfig13.github.io, os CDNs dos portais
  veem o Referer de outra origem e negam. Agora vai `<meta name="referrer"
  content="no-referrer">` e `referrerpolicy="no-referrer"` na tag.

**Verificado na rodada #53:**

- **Paginação da OLX: resolvida.** A reserva `?o=` levou de 1 para 5 páginas:
  47 → **235 anúncios**, 4 → **35 dentro do filtro**. No total, 73 → 131
  anúncios e 41 → **73 imóveis**; no recorte de bairros, 12 → **19**.
- **OLX Olinda: revertida no mesmo dia.** A cidade no caminho da URL é
  ignorada pela busca -- a entrada "de Olinda" devolveu Recife 15, Jaboatão 8,
  Paulista 5, Olinda 3, Ipojuca 2, Igarassu 1, Camaragibe 1, e os MESMOS 235
  anúncios da entrada de Recife. Como `imoveis` é chaveada por URL, a segunda
  fonte só sobrescrevia a coluna `site` e fazia a primeira aparecer com zero.
  O comentário no config já avisava que a busca cobre a região metropolitana
  inteira; eu não dei o peso devido. Olinda já vinha pela entrada existente --
  o que faltava era paginação. A lição ficou escrita no `config.py`, no lugar
  onde a próxima pessoa vai procurar.
- **Zap e Viva Real: ainda na p1.** O fallback de clique existia e não
  disparou, porque reusava `_proxima_pagina`, que prefere âncora -- e a
  âncora é justamente a que não funciona. Agora há `_proxima_pagina_botao`,
  que ignora âncoras, mais rolagem até o controle e log de por que falhou.
  Pendente de nova validação.

**Pendente de verificação em produção:** paginação do Grupo ZAP e as fotos. Nada disso é testável aqui -- este ambiente não alcança olx.com.br,
zapimoveis.com.br nem os CDNs de imagem. A validação é a rodada do Actions.

**22/08:** persistência da triagem. Relato: "marco favorito ou descarto e na
próxima atualização tudo é desfeito".

**O que foi descartado por medição, antes de mexer em qualquer coisa:**
- Não é o mecanismo. Reproduzido o cenário exato (marcar → reescrever o HTML
  com uma rodada nova → recarregar): sobreviveu.
- Não é rotatividade de URL. Comparando o banco da rodada #19 com o atual, 34
  de 35 apartamentos presentes nas duas mantêm ao menos uma URL de anúncio; só
  1 troca por completo. E nenhuma URL muda apenas na query string.

Sobra o navegador do celular não guardando os dados do site — e o defeito
real é nosso: o `catch` vazio engolia a falha, então a marcação era aceita na
tela e perdida na recarga, sem uma palavra. **Falha silenciosa em persistência
é pior que funcionalidade ausente**: a pessoa confia na marcação e refaz a
triagem inteira no dia seguinte.

Três camadas, da mais durável para a mais imediata:

1. **`triagem.json` na raiz, versionado.** `dashboard.py` lê e embute como
   `SEMENTE`; é o único pedaço da triagem que sobrevive a limpeza de dados do
   navegador e a troca de aparelho, porque mora no repositório. Arquivo
   ausente ou quebrado não derruba a rodada (a triagem é conveniência, o
   catálogo é o produto). Aceita `{url: data}` e também lista de urls.
2. **Backup/restaurar** em Favoritos e na Lixeira. O arquivo baixado tem
   exatamente a forma do `triagem.json`, então o backup não é consolo: é o
   caminho para tornar a triagem permanente — basta o arquivo entrar no repo.
   Restaurar faz UNIÃO, nunca substituição.
3. **`localStorage`** segue por cima, para a marcação do dia valer na hora.
   Agora com sonda de escrita real na carga: se o armazenamento estiver
   bloqueado, um aviso aparece na tela em vez de nada acontecer.

Achado de brinde: `display:flex` do autor vence o `[hidden]` do navegador —
terceira vez que essa armadilha morde neste projeto (já havia regra para
`.filtros` e `.ofertas`). O aviso e a barra de backup nasciam visíveis.

**21/08 (2):** triagem no dashboard — favoritar, descartar e lixeira, mais o
conserto de dois números que mentiam.

- **Descartar e favoritar**, persistidos em `localStorage`. A chave é a **URL
  do anúncio**, não o id do imóvel: `db.consolidar_imoveis()` apaga e recria a
  tabela `imovel` a cada rodada, então o id de hoje não é o de amanhã e uma
  lista chaveada por ele esqueceria tudo em 12 horas. O imóvel conta como
  marcado se QUALQUER anúncio dele estiver na lista — assim sobrevive a
  regrupamento e a anúncio que sai de um portal e volta por outro.
- **Lixeira** como quarto escopo, ao lado de Favoritos. Descartado sai das
  listas de bairro e das contagens; favorito continua onde está, com a
  estrela acesa. "Desfazer" aparece no lugar do card que saiu.
- **Contagem dos chips era fixa e global** (interpolada em Python sobre a
  lista inteira): com "Minhas preferências" ligado, o chip dizia "Novos 4"
  numa tela com 1, enquanto o pulso dizia 1. Agora sai do mesmo cálculo do
  pulso. Era este o pedido de "o filtro precisa seguir o botão dos
  preferidos" — os *filtros* já seguiam (`filtrar()` chama `noEscopo`
  primeiro); o que mentia era o número.
- **"Novos hoje" e "Baixaram" viraram botões.** O número existia no topo e o
  filtro correspondente morava dentro do painel recolhido: dava para ver que
  três baixaram e não havia como chegar nos três. Clicar liga o chip e rola
  até a lista.
- **`queda` entrou na ordenação** (logo depois de `novo`) e o selo passou a
  levar o percentual junto do valor. Sobre a foto agora cabem **no máximo
  dois selos**, por prioridade (queda > novo > melhor achado): três
  empilhados em 412px não destacavam nada.
- Achado no caminho, com a tela na mão: quatro botões de escopo estouravam a
  largura no Poco X6 Pro e "Lixeira" saía pela direita. Agora quebram em 2x2
  abaixo de 430px. E "1 imóveis" na contagem virou concordância de verdade.

Limite aceito (decisão do usuário): triagem é **por aparelho**. Sem servidor
não há como sincronizar, e commitar a lista no repositório daria conflito a
cada rodada.

Verificado em Chromium real (412px, `is_mobile`), não só em teste unitário:
descartar → desfazer → lixeira → restaurar, favoritar dentro e fora do
escopo, persistência após reload, e nenhuma rolagem horizontal.

**21/08 (1):** postura de coleta alinhada ao que o projeto diz fazer, antes
de falar do projeto em público. Quatro mudanças:

- **`Crawl-delay` virou espera de verdade.** O `robots.py` já extraía a
  diretiva e gravava no banco, e nada esperava — inclusive na Eduardo
  Feitosa, onde o próprio config registra que o site "pede Crawl-delay: 5, o
  que precisa ser respeitado". Agora `utils.aguardar_vez()` enfileira por
  **domínio** (Zap/Viva Real/Imovelweb/CRECI aparecem duas vezes cada no
  config), com teto de 30s e sem inventar pausa para quem não declarou nada.
  Vale para `requests` e para o Playwright.
- **Integração com "web unlocker" comercial removida** (`utils.py`,
  `config.py`, README). Nunca foi ligada — as variáveis viviam vazias e
  nenhum scraper pedia o caminho —, mas era um contorno explícito de
  Cloudflare/DataDome no código de um projeto que decide o que raspar pelo
  robots.txt. Incoerente de manter, e indefensável de explicar.
- **README ganhou escopo e limites de verdade** (seção "Escopo, uso e
  limites"): projeto pessoal, não comercial, sem dado pessoal, sem
  redistribuir descrição de anúncio, com o que o robô deliberadamente não
  faz. A "Observação sobre Termos de Uso" que existia era vaga e dizia
  "não passe de 1x/semana" enquanto o cron roda 2x/dia.
- **README destravado da realidade:** cadência corrigida na tabela de
  arquivos e a linha do `scraper_portais.py` (arquivo que não existe mais)
  trocada pelo `scraper_chavesnamao.py`.

Levantamento que motivou tudo isso, para não refazer: o dashboard público
**não** publica descrição de anúncio (só fato estruturado + link para a
origem, foto por hotlink na fonte), e `telefone`/`imobiliaria` existem no
schema mas estão **vazias nos 327 imóveis** do banco commitado e não são
referenciadas em `dashboard.py`. Ou seja: não há dado pessoal em tratamento
hoje. Fica registrado porque a pergunta volta toda vez.

**Pendência conhecida:** o UA. O `robots.py` avalia as regras contra
`"apt-scraper (monitor pessoal de aluguel)"`, mas as requisições saem com
`HEADERS` de Chrome 126 (`utils.py`). Se identifica como robô para decidir
se pode, e como navegador para buscar. Defensável tecnicamente (site devolve
403 a UA desconhecido), frágil de sustentar em público — decisão de produto,
não foi mexido.

**20/08 (8):** galeria cheia na vitrine — busca a página do anúncio quando
o imóvel do recorte tem menos de 5 fotos (antes era "nenhuma foto", que
deixou de disparar quando toda fonte passou a trazer a miniatura do card).

**20/08 (7):** corrigidas as fotos que não carregavam (a do card era
descartada no acúmulo da rolagem, e "primeira img" pegava ícone). Botões
viraram "Minhas preferências" / "Outros bairros" (complemento).

**20/08 (6):** botão "Meus bairros / Todos os bairros" no dashboard — o
arquivo leva os 54 imóveis coletados e mostra 16 por padrão. Selo ★ segue
restrito aos preferidos.

**20/08 (5):** Chaves na Mão (Recife e Olinda) incluído, com custo total
lido da página do imóvel; selo "Melhor achado" restrito aos bairros
preferidos (agora 10, com Encruzilhada, Torreão, Rosarinho e Campo Grande).

**20/08 (4):** fotos em todas as fontes (card + galeria da página do
anúncio, até 12, com carrossel) e nota de afinidade com selo "Melhor
achado" — perfil respondido pelo usuário em `config.PERFIL`.

**20/08 (3):** barra de filtros recolhida atrás de botão com contador,
chevron SVG no lugar de "▶", sparkline só com 3+ pontos e variação real.
Cadência passou a 2x/dia (08:13 e 18:13 BRT).

**20/08 (2):** custo real do CTI (visita à página do anúncio), botão
"Observações" no topo no lugar do rodapé, e correção do "Limpar" (não zerava
o bairro). Fotos: já eram URLs no banco desde sempre — nunca houve imagem
salva, são 50 KB de texto em 676 KB de banco.

**20/08:** preço passou a 0–2.500 e entrou o recorte de bairros na
apresentação (`config.BAIRROS_EXIBIDOS`). A coleta segue cobrindo a cidade
inteira; só a exibição é restrita. Medido no banco do dia: 19 de 49 imóveis
ficam visíveis (26 em outros bairros, 4 sem bairro informado).

Detalhe e racional de cada um: [BACKLOG.md](../../BACKLOG.md), seção
"Fase 4".

Rodada disparada em 19/08 após o merge do #5 — é ela que publica a aba
"Fontes" e o filtro na URL no Pages. Mudança de layout só aparece no ar
depois de uma rodada.

---

## Decisão pendente com o usuário

**Quais fontes desligar.** Os dados existem agora na aba "Fontes" do
dashboard. Leitura das últimas 10 execuções:

- 9 fontes não passaram **nenhum** anúncio no filtro, gastando 121s por rodada.
- Piores: Imovelweb e Imovelweb Olinda — 37s cada, status `SEM_ESTOQUE`.
- Também sem retorno: Josinildo, Rogério Corretor, Sérgio Rodrigues, Cristina
  Mirele, Luiza Parizi, Belchior Alvarez, Newville.

**Antes de cortar**, checar se o filtro de preço da busca não está apertando
demais nas fontes pequenas (o CRECI já mostrou esse padrão). Volume baixo não
basta: a coluna "só ela" é o que mede a perda real.

Critério de destaque em âmbar na tabela: gastou 20s+ e não passou nada no
filtro. **Não** é "zero exclusivos" — isso pegaria Zap e Viva Real, que têm
zero só porque duplicam uma à outra e sustentam o catálogo inteiro.

---

## Aberto no backlog

- [ ] Decidir o corte de fontes (acima).
- [ ] Alerta ativo — hoje é preciso abrir o dashboard para saber que algo
      baixou de preço.

---

## Estado da operação

- Cron de 2 em 2 horas (13 */2 * * *, UTC) + disparo manual.
- 201 testes, ~4s.
- Banco: poda diária de inativos com 180+ dias, VACUUM aos domingos.
- REMAX reativado e produzindo (64 coletados, 4 no filtro, 1 exclusivo).
- `saida/apartamentos.db` e `.xlsx` são commitados pelo workflow a cada
  rodada — evitar mexer neles localmente para não conflitar com o `git pull`.
