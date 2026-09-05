# Backlog de Melhorias — Monitor de Apartamentos

---

## Fase 9 — Recorte geográfico (05/09/2026)

Relato: anúncios rotulados como Recife que, ao abrir, eram Garanhuns e
Gravatá. Três causas independentes, todas nossas.

- [x] **`grande-recife` está em toda URL do OLX.** É o nome da REGIÃO no
  caminho, e `cidade_do_slug` casava com "recife" -- devolvendo "Recife" para
  o catálogo inteiro do portal, Caruaru incluído. Era o mecanismo principal, e
  é o tipo de defeito que só aparece quando alguém clica no anúncio.

- [x] **A cidade era inventada quando a detecção falhava.** `_parse_card`
  completava com `cidade_padrao`. Agora só fonte de cidade única usa o padrão;
  o OLX é `multi_cidade: True` e fica com cidade vazia -- que o filtro trata
  como INDETERMINADO. *Princípio:* completar com o valor mais provável é pior
  que não saber, porque o palpite passa no filtro e o desconhecido não.

- [x] **O filtro não tinha recorte geográfico.** `avaliar_filtro` recebia
  `cidade` e só a usava para escolher o perfil: cidade sem perfil caía no de
  Recife e podia ser APROVADA. Agora cidade fora de `CIDADES_MONITORADAS` é
  REPROVADA com motivo.

- [x] **`CIDADES_FORA_DA_REGIAO`**: 19 cidades do agreste, sertão e zona da
  mata. Não estão lá para serem monitoradas -- estão para serem RECONHECIDAS.
  Reconhecer é o que permite rejeitar com motivo em vez de rotular errado.

- [x] **Recorte decidido com o usuário: Recife, Olinda e a RMR.** As 9 cidades
  da região entram com o perfil de Recife (2+ quartos, 60m²+) e ficam fora de
  `BAIRROS_EXIBIDOS`, então caem em "Outros bairros" em vez de disputar a
  lista do dia. Medido sobre a rodada #53: sai 1 anúncio de 105.
  *Descartado:* recorte estrito Recife+Olinda, que era o que o README dizia --
  tiraria 17 anúncios de cidades vizinhas legítimas para resolver um problema
  que era do agreste.

---

## Fase 8 — Cobertura: paginação, OLX Olinda, cadência (05/09/2026)

- [x] **Todas as fontes de Playwright traziam só a primeira página.** O laço
  montava a seguinte como `{base}&pagina={n}`; o OLX pagina por `?o=` e os
  portais do Grupo ZAP ignoram `pagina` nessa posição. Os três devolviam a
  mesma p1, o scraper lia "0 links novos" e concluía "acabaram os imóveis" --
  semanas de catálogo truncado sem nenhum sinal. Medido na #51: Viva Real
  30/0, Zap 30/0, Zap Olinda 13/0, Viva Real Olinda 13/0, OLX 49/0.
  *Correção em duas etapas, e a segunda só existiu porque a primeira foi
  instrumentada:* (1) seguir o link que o site publica, com log de por onde
  avançou; (2) a rodada #52 revelou que Zap e Viva Real ACHAM o link, navegam
  e a lista repete -- SPA, o parâmetro só vale no cliente. Agora espera o
  primeiro href TROCAR e, se não trocar, clica no controle. Para o OLX, que
  não publica link legível, ficou `param_pagina: "o"` como reserva.
  *Resultado medido na #53:* OLX de 47 para **235 anúncios** (5 páginas), e de
  4 para **35** dentro do filtro. No total: 73 → 131 anúncios, 41 → 73
  imóveis, 12 → 19 no recorte. Zap e Viva Real seguiram na p1 -- o fallback de
  clique não disparava porque reusava a busca que prefere âncora, e a âncora é
  a que não funciona; corrigido com um localizador só de botão.
  *Descartado:* tabela de parâmetro por portal como solução principal.
  Parâmetro de paginação é detalhe de implementação alheia -- vira dívida na
  primeira mudança de qualquer um dos três.

- [x] **Zero links novos depois de uma página cheia virou WARNING.** Zero na
  p1 é fonte vazia; zero na p3 é truncamento. Mesma regra de "não achar não é
  não olhar", aplicada dentro da fonte -- e foi esse aviso que apontou a
  etapa 2 acima.

- [~] **OLX Olinda: adicionada e revertida no mesmo dia.** A hipótese era que
  a busca de Recife fosse do município. É falso: a cidade no caminho da URL é
  ignorada, e a entrada "de Olinda" devolveu os MESMOS 235 anúncios, com
  Recife 15, Jaboatão 8, Paulista 5, Olinda 3, Ipojuca 2. Pior que inútil:
  `imoveis` é chaveada por URL, então a segunda fonte só sobrescrevia a coluna
  `site` e zerava a atribuição da primeira, além de dobrar a carga num site
  que já devolve 403 nas páginas de detalhe. O comentário no config já dizia
  que a busca cobre a região metropolitana; a lição agora está escrita como
  aviso explícito ("NÃO adicione uma segunda entrada OLX"), no lugar onde a
  próxima pessoa vai procurar. O que faltava para Olinda era paginação, e era
  o mesmo defeito de sempre.

- [x] **Cadência de 2 em 2 horas.** *A vigiar:* 12 commits/dia de um banco
  binário. Se o repositório crescer demais, o próximo passo é parar de
  versionar o `.db` a cada rodada e guardar só o histórico de eventos.

- [x] **Hora da rodada no dashboard**, em BRT. Com 12 rodadas/dia, "05/09"
  não diz se o dado é de agora ou de dez horas atrás.

- [x] **Fotos não carregavam, e não era coleta.** 54 de 62 anúncios têm URL
  de foto no banco. É hotlink recusado: servidas de jlfig13.github.io, os
  CDNs dos portais recebem Referer de outra origem e negam. `<meta
  name="referrer" content="no-referrer">` mais `referrerpolicy` na tag. O
  `onerror` que cai no marcador cinza continua -- a degradação offline é
  premissa do projeto.

---

## Fase 7 — Persistência da triagem (22/08/2026)

Relato de uso: favorito e descarte sumiam "na próxima atualização".

- [x] **Duas causas prováveis eliminadas por medição, antes de tocar no
  código.** (1) O mecanismo persiste: reproduzido o cenário exato -- marcar,
  reescrever o HTML com uma rodada nova, recarregar -- e as marcações
  sobreviveram. (2) Não é rotatividade de URL: comparando o banco da rodada
  #19 com o atual, 34 dos 35 apartamentos presentes nas duas mantêm ao menos
  uma URL de anúncio, e nenhuma URL muda só na query string. Fica registrado
  para não refazer a investigação: a chave por URL de anúncio está correta.

- [x] **A falha era silenciosa, e isso era o defeito.** O `catch` vazio do
  `localStorage` fazia o navegador que bloqueia dados de site aceitar a
  marcação na tela e perdê-la na recarga, sem aviso. Agora há sonda de escrita
  de verdade na carga (grava, lê, apaga) e um aviso visível quando falha.
  *Princípio:* falha silenciosa em persistência é pior que funcionalidade
  ausente -- sem funcionalidade a pessoa não confia; com falha muda, ela
  confia e perde o trabalho.

- [x] **`triagem.json` versionado como semente.** Lido por `dashboard.py` e
  embutido no HTML; é a única camada que sobrevive a limpeza de dados e a
  troca de aparelho, porque mora no repositório e não no telefone. O
  `localStorage` entra por cima (união), para a marcação do dia valer na hora
  sem esperar rodada. Arquivo ausente ou ilegível volta vazio e a rodada
  segue.
  *Descartado de novo, agora com o motivo mais claro:* fazer a página gravar
  direto no repositório. Página estática não tem como, e um token de escrita
  no HTML público seria pior que o problema.

- [x] **Backup/restaurar** na barra de Favoritos e Lixeira. O arquivo baixado
  tem exatamente a forma do `triagem.json`, então serve de ponte para a camada
  durável. Restaurar faz união, nunca substituição -- restaurar num aparelho
  que já tem marcação não pode zerá-la.

- [x] **`display:flex` vence `[hidden]`** — terceira ocorrência no projeto
  (já havia regra para `.filtros` e `.ofertas`). Aviso e barra de backup
  nasciam visíveis.

---

## Fase 6 — Triagem no dashboard (21/08/2026)

Fecha o item que estava aberto desde a Fase 4 ("Favoritos / descartados no
dashboard — precisa de armazenamento local, já que o arquivo é regerado a
cada rodada").

- [x] **Descartar, favoritar e lixeira.** A decisão que define o resto:
  a chave é a **URL do anúncio**, não o id do imóvel. `db.consolidar_imoveis()`
  faz `DELETE FROM imovel` e reconstrói a tabela a cada rodada — os
  agrupamentos mudam quando anúncios entram e saem —, então o id não
  sobrevive 12 horas. Um imóvel conta como marcado quando QUALQUER anúncio
  dele está na lista, o que resolve de graça dois casos que quebrariam a
  versão ingênua: ganhar uma segunda fonte depois de descartado, e sumir de
  um portal para voltar por outro.
  *Descartado:* guardar a lista no repositório. Daria sincronia entre
  aparelhos, e daria conflito de merge a cada rodada — o banco já é binário
  e commitado 2x/dia. Aceito o limite: triagem é por navegador.
  Descartado sai das listas de bairro E das contagens; favorito continua na
  lista, com a estrela acesa. "Desfazer" no lugar do card que saiu, não em
  toast de canto: é onde o olho já está, e sem rede de segurança ninguém
  descarta na dúvida — que era o objetivo da funcionalidade.

- [x] **A contagem dos chips seguia a lista inteira, não o escopo.** "Novos",
  "Baixaram" e "Confirmados" tinham o número interpolado em Python sobre
  todos os imóveis e nunca mudavam, enquanto o pulso recalculava por escopo.
  Com "Minhas preferências" ligado, um dizia 4 e o outro 1. Agora saem do
  mesmo cálculo. Nota para quem for ler o pedido original: os *filtros* já
  respeitavam o escopo (`filtrar()` chama `noEscopo()` antes de tudo) — o
  defeito era só no número exibido.

- [x] **O número que informava não agia.** "Novos hoje" e "Baixaram" ficavam
  no pulso, no topo, e o chip que filtra por eles dentro do painel recolhido:
  dava para ler "3 baixaram" e não havia caminho até os três. Viraram botões
  que ligam o chip e rolam para a lista.

- [x] **Destaque do que mudou.** `queda` entrou no desempate da ordenação,
  logo depois de `novo` — antes um imóvel que caiu R$ 300 podia parar no meio
  da lista com o selo que ninguém rolava para ver. O selo passou a mostrar o
  percentual junto do valor (R$ 100 em 1.500 é outra conversa que em 2.500).
  E os selos sobre a foto foram limitados a **dois**, por prioridade
  (queda > novo > melhor achado): três empilhados em 412px viram uma faixa de
  etiquetas que o olho pula inteira.

- [x] **Dois defeitos achados só com a tela na mão** (Chromium a 412px, com
  `is_mobile` para o `@media (hover:none)` valer): os quatro botões de escopo
  estouravam a largura e "Lixeira" saía pela direita — agora quebram em 2x2
  abaixo de 430px; e a contagem dizia "1 imóveis", que passava despercebido
  numa lista de 19 e é a regra na lixeira.

---

## Fase 5 — Postura de coleta (21/08/2026)

Motivada por uma pergunta simples: dá para falar deste projeto em público sem
que o código desminta o texto? A auditoria achou três lugares onde desmentia.

- [x] **`Crawl-delay` aplicado, não só lido.** O `robots.py` extraía a
  diretiva desde a Fase 3 e gravava em `robots_veredito.crawl_delay`, e
  nenhum ponto do código esperava esse tempo — a diretiva era lida e
  ignorada. O caso mais constrangedor estava escrito no próprio `config.py`:
  a Eduardo Feitosa "pede `Crawl-delay: 5`, o que precisa ser respeitado".
  Não era.
  Agora `utils.aguardar_vez()` enfileira as requisições por **domínio**, não
  por fonte: Zap, Viva Real, Imovelweb e Portal CRECI aparecem duas vezes
  cada no config (Recife e Olinda), e contar por fonte deixaria dois dos três
  workers batendo no mesmo servidor sem intervalo nenhum. A marca de último
  acesso é gravada *antes* do sleep, com a trava tomada — gravar depois faria
  dois workers lerem a mesma marca velha, dormirem o mesmo intervalo e saírem
  juntos, que é exatamente a rajada que a diretiva existe para evitar.
  *Descartado:* pausa global fixa entre requisições. Multiplicaria o tempo da
  rodada para respeitar uma regra que a maioria das fontes não declarou.
  Teto de 30s (`ATRASO_MAXIMO`) porque existe site anunciando `Crawl-delay:
  3600`: acima disso a fonte não é viável, e o lugar de decidir isso é o
  config, desativando-a — não um worker dormindo uma hora.
  Cobertura: `test_crawl_delay.py` (7 testes), incluindo o caso de dois
  workers concorrentes no mesmo domínio.

- [x] **Integração com "web unlocker" comercial removida.** `utils.py` tinha
  uma função cuja docstring dizia, com todas as letras, que contornava
  Cloudflare/DataDome, mais duas variáveis em `config.py` e uma seção no
  README. Nunca foi ligada — as variáveis viviam vazias e nenhum scraper
  passava `prefer_brightdata=True`.
  *Por que remover código morto:* o projeto decide o que raspar pelo
  robots.txt e desativa fonte que proíbe (quatro estão fora por isso). Manter
  ao lado disso um contorno explícito de controle técnico de acesso é
  incoerente, e é o primeiro item que qualquer leitor usaria para dizer que a
  postura declarada é fachada. Se um portal protegido parar de funcionar, a
  resposta é desativar a fonte, não furar a proteção.

- [x] **README: escopo, uso e limites.** A seção "Observação sobre Termos de
  Uso" dizia que scraping pessoal "geralmente não é problema" e pedia para
  não passar de 1x/semana — enquanto o cron roda 2x/dia desde a Fase 4. Foi
  trocada por uma declaração verificável: projeto pessoal e não comercial,
  robots.txt respeitado (com as fontes que isso custou), `Crawl-delay`
  cumprido, sem contorno de anti-bot, sem dado pessoal, sem redistribuir
  conteúdo de anúncio. Cada linha corresponde a algo que existe no código.

- [x] **README alinhado ao repositório.** Tabela de arquivos dizia
  "agendamento semanal" e listava `scraper_portais.py`, que não existe mais.

### Levantado e deliberadamente não mexido

- **Não há dado pessoal em tratamento.** As colunas `telefone` e
  `imobiliaria` existem no schema de `db.py`, mas estão vazias nos 327
  imóveis do banco commitado e não são referenciadas em `dashboard.py`. O
  dashboard público leva fato estruturado (preço, bairro, m², quartos) mais
  link para a origem; a descrição do anúncio **não** vai para a página, e a
  foto é `<img src>` apontando para a fonte, não cópia rehospedada. Fica
  registrado aqui porque a pergunta volta toda vez que alguém olha o projeto
  de fora.

- **O User-Agent é inconsistente, e continua.** O `robots.py` avalia as
  regras contra `"apt-scraper (monitor pessoal de aluguel)"` — a identidade
  honesta, que faz o scraper cair na regra do `*` e foi o que pegou o Harry
  Fernandes. Mas as requisições saem com `HEADERS` de Chrome 126, porque site
  demais devolve 403 a agente desconhecido (o OLX faz isso até no
  `/robots.txt`). Ou seja: se identifica como robô para decidir se pode, e
  como navegador para buscar. Sustentável tecnicamente, frágil de defender em
  público. Mudar é decisão de produto — pode custar fontes — e não foi
  tomada.

- **`_ANTI_BOT_SCRIPT` no `scraper_playwright.py`** segue no lugar. É
  mascaramento de automação, mesma família do item removido acima, mas ao
  contrário dele está em uso e sustenta a maior parte do catálogo. Removê-lo
  é uma decisão com custo real, não uma limpeza.

---

## Fase 4 — Celular, catálogo e operação (19/08/2026)

### Dashboard no celular (Poco X6 Pro / iPhone 11)

- [x] **Cards de verdade** — a lista separava imóveis por um divisor de 1px:
  lia como jornal e, na tela estreita, não dava para dizer onde um anúncio
  terminava e o outro começava. Agora cada imóvel é uma caixa com borda,
  sombra e foto de capa, no espírito dos portais (Zap/Viva Real).
- [x] **Foto de capa** — vem do campo `fotos` do banco (`db._primeira_foto`).
  Sem foto na fonte ou sem rede, cai num marcador cinza: o dashboard tem de
  continuar legível offline, que é a premissa dele.
- [x] **Campos de 16px no celular** — abaixo disso o Safari do iPhone dá zoom
  ao focar e prende o usuário num layout deslocado. Era o pior dos bugs
  móveis, e invisível no desktop.
- [x] **Alvos de toque de 40–44px** (eram 32–34px) e `env(safe-area-inset-*)`
  para o notch em paisagem e a barra de gestos.
- [x] **Hover atrás de `(hover:none)`** — no toque o estado grudava no card
  até o próximo tap.
- [x] **Expansão de ofertas** — virou botão explícito dentro do card, e o
  painel virou lista de blocos. A tabela de 4 colunas era a origem da
  rolagem horizontal no celular. Bug achado no caminho: `display:grid` vence
  o atributo `[hidden]` e o painel nascia aberto.
- [x] **Inter** com a fonte do sistema como reserva.

### Operação e análise

- [x] **`historico_precos` aposentada** — `evento` já era a fonte da série
  desde a Fase 3 e as rodadas diárias confirmaram a equivalência (375
  snapshots → 202 eventos, zero divergência em 195 URLs).
  `aposentar_historico_precos()` migra o que restar ANTES de derrubar a
  tabela: num banco que nunca rodou a migração, derrubar direto apagaria a
  série de julho, que não pode ser recoletada.
- [x] **Aba "Fontes" com rendimento** (`db.rendimento_por_fonte`) — saúde
  responde "quebrou?"; rendimento responde "entrega?". Colunas: coletados,
  no filtro, **só ela** (imóveis ativos que nenhuma outra fonte anuncia),
  tempo e segundos por anúncio útil. Marca em âmbar quem gastou 20s+ e não
  passou nada no filtro.
  **Primeira leitura real:** 9 fontes sem nenhum anúncio no filtro, 121s por
  rodada. Imovelweb e Imovelweb Olinda são as piores (37s cada, `SEM_ESTOQUE`).
  O corte por "zero exclusivos" foi descartado de propósito: pegaria Zap e
  Viva Real, que têm zero só porque duplicam uma à outra — e são o catálogo.
- [x] **Filtros na URL** — o recorte vira link compartilhável e sobrevive ao
  fechar a página (`?cidade=&bairro=&quartos=&min=&max=&q=&ordem=&sinais=&aba=`).
  `replaceState` em `try/catch`: abrir por duplo clique (`file://`) dá origem
  nula e a exceção derrubava o render inteiro — o link não pode custar o
  dashboard.
- [x] **REMAX reativado** — rota nova `/listings?...&TransactionTypeUID=260`.
  Na primeira rodada: 64 coletados, 4 no filtro, 1 imóvel exclusivo.

### Parâmetros de busca (20/08/2026)

- [x] **Preço 0–2.500** — o piso de 1.500 escondia oportunidade real; quem
  julga anúncio barato demais é o olho, no dashboard. `ps=0` NÃO vai para a
  URL do OLX: zero ali é piso literal, e portal que o trata como valor
  válido pode devolver busca vazia — sem o parâmetro, a listagem
  simplesmente não tem piso.
- [x] **Recorte de bairros na apresentação** (`config.BAIRROS_EXIBIDOS`) —
  25 bairros em Recife, 2 em Olinda (Casa Caiada, Bairro Novo). A COLETA
  segue cobrindo a cidade inteira: filtrar na coleta faria o histórico de um
  imóvel recomeçar do zero toda vez que a lista mudasse, e o dedupe entre
  portais perderia o par que mora fora do recorte.
  Imóvel sem bairro não é exibido — "não sei onde fica" não é o mesmo que
  "fica num bairro escolhido". O rodapé mostra quantos ficaram de fora, por
  motivo: filtro silencioso é indistinguível de fonte quebrada.
  Primeira medição: 19 de 49 imóveis visíveis (26 fora, 4 sem bairro).
- [x] **Gazetteer completado** — Paissandu, Hipódromo, Torreão, Jaqueira,
  Santana e "Bairro do Recife" (mesma coisa que Recife Antigo) faltavam em
  `BAIRROS_CANONICOS`; sem eles o imóvel chegaria sem bairro e sumiria da
  apresentação justamente nos bairros pedidos.

### Custo real e UI (20/08/2026)

- [x] **Custo no detalhe** (`detalhe_custo.py`) — a CTI mostra "R$ 1.850" no
  card e só na página do imóvel revela condomínio de R$ 953 e IPTU de R$ 194:
  **R$ 2.997 reais**. O anúncio entrava no dashboard fingindo caber no teto —
  não é um imóvel a menos, é um imóvel errado ocupando a lista.
  Opt-in por fonte (`"custo_no_detalhe": True`), com dois cortes para não
  virar varredura: não visita quem já tem custo completo nem quem já estourou
  o teto (somar encargos só aumenta). Teto de 40 visitas por rodada.
  Verificado contra a página real: 1.850 → 2.997, veredito REPROVADO.
- [x] **Botão "Observações" no topo** — filtros, bairros e contagem de
  ocultos saíram do rodapé. No celular, rodapé significa rolar a lista
  inteira para descobrir por que um imóvel não aparece; ou seja, ninguém lia.
- [x] **"Limpar" não limpava o bairro** — `preencherBairros()` preserva a
  seleção quando ela ainda existe entre as opções, então o filtro de bairro
  ficava de pé e a tela seguia mostrando poucos imóveis, com cara de botão
  quebrado.
- [x] **Fotos: nada a fazer** — já são URLs no banco (campo `fotos`, JSON),
  nunca imagem salva. 5 URLs por anúncio, 50 KB no total = 7,4% do banco. O
  dedupe usa o hash de todas elas (`resolucao.comp_fotos`), então cortar para
  uma só enfraqueceria o agrupamento sem ganho real de tamanho.

### Ajustes de leitura no celular (20/08/2026)

- [x] **Barra de filtros recolhida** — três chips mais seis campos comiam
  meia tela antes do primeiro imóvel. Abre por botão, com contador de
  filtros ativos: esconder filtro sem dizer que existe filtro faria uma
  busca estreita parecer fonte vazia. Abre de saída quando o link já traz
  recorte (quem abre link filtrado precisa ver o que está filtrado) e no
  desktop, onde a barra cabe numa linha.
- [x] **Chevron no lugar do triângulo** — "▶" chegava em tamanho e
  alinhamento diferentes em cada aparelho (no Android às vezes como emoji
  colorido). Agora é SVG: ">" fechado, "v" expandido.
- [x] **Sparkline só com 3+ pontos e variação real** — com dois pontos a
  "tendência" é uma reta ligando início e fim, que é o que o selo "Baixou
  R$ X" já diz; solta ao lado do título, lia como risco atravessando o card.
  Foi para o bloco de preço, onde tem a que se referir.

### Fotos e sugestão (20/08/2026)

- [x] **Foto do card em toda fonte** — o Playwright já tem a imagem no DOM
  da listagem; custo zero de rede. Resolve REMAX (página renderizada por JS)
  e OLX (403 em requisição direta), que não entregam galeria de outro jeito.
- [x] **Galeria da página do anúncio** (`galeria.py`) — parte de uma âncora
  que a página declara como sua (JSON-LD `image` ou `og:image`) e recolhe o
  resto da MESMA pasta do CDN. Recolher todo `<img>` traria logo, ícone de
  WhatsApp e selo de CRECI — medido no Portal CRECI, onde o primeiro `<img>`
  é o logotipo. Até 12 fotos: o banco é commitado a cada rodada.
  Roda só para os imóveis EXIBIDOS, depois do recorte de bairros.
  Medição: 7 → 11 de 16 imóveis com foto; CTI e Camila Melo entregam 12,
  Moradasol 7, Rede Imóveis 6.
  Desiste do host após 2 falhas: OLX gastava 9 requisições (3 anúncios × 3
  retries) para nenhuma foto.
- [x] **Carrossel no card** — uma `<img>` trocando de `src`, não as 12 no
  DOM: com 19 cards seriam ~230 imagens pedidas de uma vez, e a lista
  levaria segundos para ficar utilizável no celular.
- [x] **Nota de afinidade** (`afinidade.py`, perfil em `config.PERFIL`) — o
  filtro responde "cabe?", a nota responde "é o melhor?". Perguntado ao
  usuário: pesam custo mensal, área pelo preço e bairro preferido (Casa
  Amarela, Casa Forte, Graças, Espinheiro, Aflitos, Jaqueira); mínimo de 3
  quartos é requisito; selo "Melhor achado" nos até 3 primeiros.
  A nota é RELATIVA à lista do dia — nota absoluta exigiria recalibrar
  constante toda vez que o mercado ou o filtro mudasse.
  Requisito não descontava o suficiente: um 2 quartos barato e espaçoso
  marcava 38 contra 16 de um 3 quartos caro. Virou chave de ordenação
  (`atende`), não só desconto.

### Chaves na Mão e sugestão restrita (20/08/2026)

- [x] **Selo restrito aos bairros escolhidos** — a primeira versão sugeriu
  Arruda e Bairro Novo, que estão na lista mas não são onde se quer morar:
  a nota media preço, área e localização, e barato o bastante vencia a
  localização. Fora dos preferidos o imóvel mantém nota e tags de mérito,
  só não ganha selo. O piso de nota saiu quando a restrição está ligada —
  os dois juntos deixavam a tela sem sugestão nenhuma (melhores em bairro
  preferido marcavam 40 e 34 contra piso de 45).
- [x] **Chaves na Mão (Recife e Olinda)** — `scraper_chavesnamao.py`. A
  listagem embute os dados estruturados no HTML (payload do Next.js): rua,
  área, quartos, banheiros, vagas, bairro, cidade, foto e aluguel. É o
  coletor mais confiável do projeto: nada é adivinhado do texto do card.
  `price` é só o ALUGUEL. Condomínio e IPTU existem apenas na página do
  imóvel, renderizada por JS — daí a segunda visita com Playwright, só para
  quem ainda cabe no teto de R$ 2.500 só de aluguel.
  **Armadilha:** a página escreve "Aluguel + Condomínio R$ X", e esse rótulo
  contém a palavra "Condomínio". O `utils.decompor_custo` genérico lia o
  total como se fosse a taxa e somava de novo — um apartamento de R$ 1.800
  saiu como R$ 3.601. Leitor próprio (`_custo_do_texto`), que também trata
  "R$ -" e "R$ --" como ausência, não como zero.
  Paginação para em 5 porque é o que o robots.txt libera: bloqueia query
  string e abre exatamente `?pg=2` a `?pg=5`. robots consultado: PERMITIDO
  para o nosso agente (os `Disallow: /` são para bots de IA nomeados).
  Primeira coleta: Recife 63 brutos → 1 aprovado (mercado caro), Olinda 38 →
  7 aprovados.

### Escopo de bairros no dashboard (20/08/2026)

- [x] **Botão "Meus bairros" / "Todos os bairros"** — o recorte deixou de ser
  decisão do robô. O arquivo carrega TODOS os imóveis coletados e mostra por
  padrão só os bairros escolhidos; um toque troca para o resto. Regerar o
  dashboard para ver o resto significaria esperar a próxima rodada, e o
  interesse muda com o que aparece no dia.
  O selo ★ NÃO muda de regra: continua só nos preferidos, mesmo em "todos".
  Pulso, contagem e contador da aba passaram a ser desenhados em JS — número
  fixo diria "16 imóveis" numa tela mostrando 54.
  A lista de bairros do filtro acompanha o escopo (9 opções em "meus", 23 em
  "todos"), senão sobraria opção que não seleciona nada.
  Galeria e planilha seguem no recorte: foto custa uma requisição por imóvel,
  e a planilha é a lista de trabalho, não o inventário da cidade.

### Fotos que não carregavam e recorte por complemento (20/08/2026)

- [x] **Foto do card era jogada fora** — `_coletar_rolando` acumulava só o
  texto por href e remontava o card no fim, descartando em silêncio a foto
  que `_extrair_cards` tinha colhido. O CTI, que traz 9 imagens dentro do
  próprio link, chegava ao dashboard com zero.
- [x] **"Primeira `<img>`" era o ícone de favorito** — no CTI a primeira
  imagem do card é `assets/icons/icon-favorito.svg`. Agora o critério é a
  MAIOR imagem raster do card (ícone é pequeno e costuma ser SVG).
- [x] **Fontes sem `<img>` no card** — a Âncora usa `background-image` no
  style inline e o Portal CRECI esconde a foto num `data-info` com JSON
  dentro. `galeria.foto_de_card` procura nos três lugares, subindo até 4
  níveis (no quinto já se alcança a lista e a foto seria a do card vizinho).
- [x] **`cards_inline` e `html_estatico` passaram a capturar foto** — antes
  só o coletor Playwright fazia isso. No `pratica_internet` a página do
  anúncio já está baixada, então sai a galeria inteira sem custo de rede.
  Medição depois da correção: CTI 17/17, OLX 40/42, REMAX 21/21,
  Âncora 2/3, CRECI 2/2, Camila Melo 6 fotos por imóvel.
- [x] **Recorte virou complemento** — os botões passaram a ser "Minhas
  preferências" e "Outros bairros", e o segundo mostra o COMPLEMENTO (o que
  ficou de fora do filtro), não o conjunto todo. Um botão "todos" obrigaria
  a procurar os bairros conhecidos no meio da lista inteira para descobrir o
  que há de novo fora dela. Medido: 16 preferências, 38 outros, sem
  sobreposição; selo continua saindo só nas preferências.

### Galeria cheia na vitrine (20/08/2026)

- [x] **`MIN_FOTOS_VITRINE = 5`** — o critério para visitar a página do
  anúncio era "imóvel sem foto nenhuma", e ele parou de disparar quando a
  coleta passou a trazer a miniatura do card em TODAS as fontes: todo imóvel
  chegava com exatamente uma foto, o que contava como resolvido. Cinco é o
  que dá para ver o apartamento sem sair do dashboard.
  Medido: média de 5,8 → 6,5 fotos por imóvel do recorte; 9 de 16 com 5+.
  Os que continuam com uma foto são de fontes que bloqueiam requisição
  direta (OLX, Zap, Viva Real) — ali a miniatura do card é o teto.

### Ainda aberto

- [ ] **Decidir o corte de fontes** — os dados agora existem na aba Fontes.
  Candidatas: Imovelweb, Imovelweb Olinda (74s/rodada, zero estoque),
  Josinildo, Rogério, Newville, Sérgio Rodrigues, Cristina Mirele, Luiza
  Parizi, Belchior Alvarez. Antes de cortar, checar se o filtro de preço da
  busca está apertando demais nas pequenas.
- [x] **Favoritos / descartados** — feito na Fase 6, chaveado pela URL do
  anúncio (o id do imóvel não sobrevive à rodada seguinte).
- [ ] **Alerta ativo** — hoje é preciso abrir o dashboard para saber que algo
  baixou de preço. Uma notificação no dia da queda é o que fecha o ciclo.

---

## Fase 3 + auditoria + design system (19/08/2026)

### Fase 3 — Histórico e operação diária

- [x] **Tabela `evento`** (P-07) — grava só quando ALGO MUDA, com timestamp.
  `historico_precos` regravava o mesmo preço todo dia com `INSERT OR IGNORE`
  e descartava em silêncio uma segunda mudança no mesmo dia: 261 linhas,
  zero variação observada. Tipos: `CRIADO`, `PRECO_ALTERADO`,
  `DESCRICAO_ALTERADA`, `ANUNCIANTE_ALTERADO`, `SUMIU`, `REAPARECEU`.
- [x] **Ciclo de vida com dupla confirmação** — ausência marca `SUSPEITO`;
  só a segunda falta consecutiva marca `INATIVO` e gera evento `SUMIU`.
  Uma falta não basta: portal grande reordena resultado e às vezes omite um
  anúncio de uma página, e declarar "sumiu" na primeira falta geraria alarme
  falso justamente nos imóveis que interessam.
- [x] **Ciclo respeita o P-04** — só anúncio de fonte confiável entra no
  ciclo. Se o Zap falhou, seus imóveis não "sumiram": não foram olhados.
- [x] **Rodada diária** — cron passou de semanal (`0 12 * * 1`) para diário
  (`0 10 * * *`). Aluguel gira rápido.
- [x] **`git pull --rebase` com retry** (P-10) — 3 tentativas com espera
  progressiva antes do push, e `concurrency` sem `cancel-in-progress` no
  workflow. O banco é binário: sem isso, uma rodada concorrente fazia o push
  ser rejeitado e a rodada inteira perdia o histórico **sem falhar
  visivelmente**, porque o passo anterior já tinha passado.

### Débitos da Fase 1, resolvidos

- [x] **OLX reativado** (P-02) — o diagnóstico anterior apontava para o
  payload RSC (`window.__next_f`), mas ele vem VAZIO na leitura. O caminho
  certo era o DOM. Três causas reais, todas medidas:
  1. Card usa números NUS (`42m² / 2 / 1 / 1`), sem a palavra "quarto" que
     `parse_quartos` procura → `_RE_OLX_NUMEROS`.
  2. A subida na árvore parava no primeiro `R$` (103 chars), mas o bairro só
     aparece no pai (SECTION, 185 chars) → sobe um nível a mais.
  3. **A lista é virtualizada**: o link existe no DOM desde o início mas o
     `innerText` fica vazio até o card entrar na viewport, e é descartado de
     novo quando sai. 44 de 49 anúncios chegavam sem texto → `_coletar_rolando`
     extrai a cada passo da rolagem, acumulando o melhor texto por href.

  Resultado: **1 → 13 imóveis úteis**, 44 → 1 indeterminado.
- [x] **Guarda de container compartilhado** — contar `R$` não serve (um card
  legítimo tem três: aluguel, IPTU, condomínio) e contar `<a>` também não (o
  card do OLX tem dois links para o mesmo anúncio). O teste certo é **hrefs
  distintos** dentro do elemento.
- [x] **Faixa de preço na URL do OLX** (P-09) — templates `{preco_min}` /
  `{preco_max}` resolvidos a partir de `config.FILTROS` na carga, em vez de
  hardcode. No OLX `ps` é o piso e `pe` o teto (invertidos, devolve zero).
- [x] **Mapa bairro → cidade** — anúncio de Casa Caiada ou Rio Doce entrava
  como Recife (o padrão do site) e era avaliado pelo perfil errado.
- [x] **Checador de `robots.txt`** (P-17) — `robots.py`, veredito datado e
  revalidado a cada 30 dias, rodando como guarda em cada rodada.
  **Achou 4 fontes ativas que PROIBIAM scraping**: Abasol, Moradasol, Rede
  Imóveis PE e Morada Real — todas Kenlo, com `User-agent: *` →
  `Disallow: /`. Estavam sendo raspadas sem ninguém ter conferido.
  Desativadas. Distingue três casos que o config confundia: `SEM_ROBOTS`
  (404 ou HTML — não é proibição), `PROIBIDO`, `PERMITIDO`.
- [ ] **REMAX** — segue desativado. Site reestruturado; a rota é
  `/listings?City=<id>&TransactionTypeUID=<id>` e os IDs internos não são
  deriváveis de fora. Mesma resolução de 1 minuto do CRECI Olinda: buscar no
  site e copiar a URL.

### Design system "Atlântico"

- [x] **`design.py`** — tokens e CSS com o racional de cada decisão.
  Fundo branco + modo noturno em três estados (escolha explícita, `data-tema`,
  e o padrão "sistema" via `prefers-color-scheme`).
  Cores do lugar: **Azul-Atlântico #10495B** (mar de Boa Viagem, Capibaribe)
  como institucional e **Ocre-Olinda #C2703D** (fachadas do Sítio Histórico)
  como acento único. As cores do frevo ficariam saturadas e brincalhonas — o
  oposto de "dados confiáveis".
- [x] **Card expansível de ofertas** — imóvel multi-fonte abre a lista de
  anúncios do mais barato ao mais caro, com a fonte de cada um. Resolve duas
  coisas: mostra por onde fechar mais barato E deixa conferir a olho se o
  agrupamento faz sentido (calibração pela interface, em vez de limiar cego).
- [x] **Preço de vitrine é o MENOR** entre as fontes — é o que se paga de
  fato. A mediana consolidada mostraria valor indisponível em portal nenhum.

### Auditoria independente — corrigido

- [x] **Colisão de classe CSS** — o span `.rua.vazio` herdava
  `.vazio{padding:64px}` do estado-vazio da lista: 128px de padding fantasma
  por imóvel. Renomeado para `.rua-ausente` / `.estado-vazio`.
- [x] **Scroll horizontal** — topo com margem negativa fora do container +
  tabela de saúde sem rolagem própria.
- [x] **Item de 291px** — grid com `row-span` esticava a linha até a altura da
  coluna de preço. Trocado por flex: ~120px.
- [x] **Índices** em `imoveis(visto_na_ultima_execucao)`, `imoveis(imovel_id)`,
  `imoveis(site)` e `execucao_fonte(fonte)`. Criados APÓS o `ALTER TABLE` --
  indexar coluna antes de ela existir derrubava a conexão em banco antigo.
- [x] **Código morto** — `scraper_portais.py` (substituído por
  `extracao_jsonld.py`), `db.listar_vistos_na_ultima_execucao` e
  `db.contar_execucoes_anteriores`.

### Auditoria — recomendado (estado atual)

- [x] **Paralelizar fontes Playwright** — feito na Fase 3.5 (PR #2).
- [x] **Aposentar `historico_precos`** — feito na Fase 4.
- [x] **Medir rendimento por fonte** — feito na Fase 4, aba "Fontes".
- [x] **`VACUUM` + poda de inativos** — `db.manutencao()` roda toda rodada;
  o `VACUUM` só no domingo (reescreve o arquivo inteiro, não vale diário).
- [x] **Filtros na URL** — feito na Fase 4.
- [x] **Favoritos / descartados** — feito na Fase 6.

Testes: **111 → 121**. Rodada: 18 fontes ativas, 72 anúncios, 50 imóveis.

---


---

## Fase 1 — Confiabilidade da coleta (18/08/2026)

Executada a partir da auditoria. Estado real, item a item:

- [x] **Veredito de filtro em três estados** (P-01) — `utils.avaliar_filtro`
  devolve `APROVADO` / `INDETERMINADO` / `REPROVADO` com motivos. Antes,
  `passa_no_filtro(None, None, None, None)` devolvia `True` e foi assim que
  56 dos 57 registros do OLX entraram sem nenhum dado. `passa_no_filtro`
  segue existindo como invólucro compatível.
- [x] **Registro de execução** (P-04) — tabelas `execucao` e `execucao_fonte`
  com status, motivo, contagens e duração por fonte.
- [x] **Guarda de sanidade por volume** (P-04) — `db.avaliar_sanidade`
  rebaixa para `PARCIAL` quando o volume cai abaixo de 60% da mediana das
  últimas 5 rodadas, mesmo sem erro técnico.
- [x] **Ausência só conta com fonte saudável** (P-04) — `salvar_execucao`
  recebe `fontes_confiaveis` e só zera `visto_na_ultima_execucao` delas.
  Validado com o banco real: com o Viva Real fora, seus 8 imóveis foram
  preservados em vez de virarem "sumiram".
- [x] **Retry com backoff e classificação de falha** (P-11) —
  `utils.get_html_diag` distingue timeout, 4xx, 5xx, conexão e challenge
  anti-bot; backoff exponencial com jitter no lugar do sleep fixo.
- [x] **Detecção de bloqueio** (P-11) — `utils.detectar_bloqueio` reconhece
  Cloudflare/DataDome/reCAPTCHA. Página de desafio devolve HTTP 200 e zero
  cards: sem isso, bloqueio era lido como "a fonte esvaziou".
- [x] **Painel de saúde das fontes** (backlog 4.1) — tabela no rodapé do
  dashboard, aberta automaticamente quando há fonte degradada.
- [x] **Bairro derivado do slug da URL** (P-18) — `utils.bairro_do_slug`
  validado contra `BAIRROS_CANONICOS` (~70 bairros de Recife/Olinda/Jaboatão).
  Medido: sem bairro caiu de **45,4% para 13%**; sem preço, de 31,9% para 0%.
- [x] **Extração JSON-LD** (P-02) — `extracao_jsonld.py` lê schema.org das
  páginas de listagem e **enriquece** (não substitui: medido, o JSON-LD dos
  portais não traz preço). Cobertura no Viva Real e Zap: quartos, área e
  banheiros 100%, logradouro 90%, fotos 100%. Numa rodada real completou
  132 campos em 29 imóveis. O `logradouro` é inédito na base e é o sinal
  mais forte da deduplicação da Fase 2.
- [x] **Correção das notas de robots.txt** (P-17) — Nogueira e Paulo Miranda
  não têm robots.txt; a proibição registrada não existia. Harry Fernandes
  proíbe de fato (`User-agent: *` → `Disallow: /`) e ficou de fora.

**Pendente da Fase 1:**

- [ ] **OLX via `window.__next_f`** (P-02) — o OLX migrou para Next.js App
  Router e não expõe `__NEXT_DATA__` nem `__APOLLO_STATE__`; os anúncios vêm
  no payload RSC em streaming (`window.__next_f`). O JSON-LD da página só
  traz `WebSite`, `Organization` e um `Product` avulso. É a peça que falta
  para recuperar a maior fonte.
- [ ] **Persistir os campos novos** — `logradouro`, `banheiros`, `andar` e
  `fotos` já são extraídos mas ainda não têm coluna: hoje melhoram o filtro
  (resgatam item que ficaria indeterminado) e são descartados na gravação.
  Entram com o schema da Fase 2.
- [ ] **Checador de robots.txt por fonte**, com veredito datado e revalidação
  periódica — política de acesso muda e nada percebe hoje.

Testes: **42 → 77**, todos passando.

---

## Fase 1b — Qualidade de dados e poda de fontes (18/08/2026)

- [x] **Endereço extraído do texto do card** — `utils.endereco_do_texto`
  cobre os dois formatos que faltavam: Imovelweb (`Av. X\nBairro, Cidade`)
  e Moradasol (`Bairro - Cidade - PE`, colado ao texto anterior). Mais
  `utils.bairro_no_inicio` como último recurso, para sites que abrem o
  título com o bairro (Camila Melo). **Nenhum levantamento manual foi
  necessário: o endereço já estava nos cards, só não era lido.**
  Todos validados contra `BAIRROS_CANONICOS`; menção de proximidade
  ("a 10 minutos de Boa Viagem") é rejeitada de propósito, porque atribuir
  bairro errado é pior que não ter bairro.
- [x] **Filtro de anúncio desatualizado** — `MAX_DIAS_DESDE_ATUALIZACAO = 30`.
  O Portal CRECI carimba "Atualizado em: dd/mm/aaaa" em cada card; medido
  numa rodada real, **11 de 40 anúncios estavam fora do prazo**. Fonte que
  não declara data não é afetada: ausência de carimbo não é prova de
  anúncio velho.
- [x] **Colunas novas** — `logradouro`, `banheiros`, `andar` e `idade_dias`
  na tabela `imoveis`, por migração incremental. O `UPDATE` usa `COALESCE`
  para uma rodada sem o dado não apagar o que já foi capturado.
- [x] **"Não Localizado" na saída** — Excel e dashboard marcam a lacuna
  explicitamente. No banco o ausente continua `NULL`: é `NULL` que permite
  medir completude e alimentar a fila de enriquecimento.
- [x] **Imovelweb: `wait_until` de `networkidle` para `load`** — a página
  mantém requisições abertas indefinidamente e estourava os 45 s. Com
  `load` carrega em ~6 s e devolve os 30 cards.

**Auditoria de bloqueio (as 24 fontes, uma a uma):** **zero bloqueadas.**
Nenhum Cloudflare, DataDome ou reCAPTCHA em nenhuma. Todas responderam
HTTP 200. Não havia o que remover por bloqueio — os problemas eram outros:

- [x] **REMAX Recife e Olinda → `revisar`** — site reestruturado. A URL
  ainda carrega 1,5 MB mas dos 136 links da página **zero** são anúncios;
  a busca migrou para `/listings?City=<id>&TransactionTypeUID=<id>`.
- [x] **OLX → `revisar`** — extração incompatível, não bloqueio. Migrou para
  Next.js App Router e serve os anúncios no payload RSC (`window.__next_f`).
  Era a fonte mais lenta (27,8 s/página) e a que mais injetava lixo.

**Resultado medido em rodada completa (69 imóveis ativos, 21 fontes):**

| Campo | Antes | Depois |
|---|---|---|
| bairro | 54,6% | **100%** |
| preço | 68,1% | **100%** |
| logradouro | 0% | **68,1%** |
| banheiros | 0% | **72,5%** |
| andar | 0% | **20,3%** |

A guarda de sanidade disparou sozinha na rodada real: o Zap veio com 29
anúncios contra mediana histórica de 57, foi rebaixado para `PARCIAL` e,
por isso, seus imóveis **não** foram marcados como desaparecidos.

Testes: **77 → 91**.

---

Documento vivo. Cada item tem **prioridade** (P0 = necessário para o novo
modelo de operação, P1 = alto valor, P2 = incremental), um **porquê** e uma
**definição de pronto** enxuta.

**Nova direção do produto:**
- Hospedado no **GitHub** (código + dashboard estático).
- **Sem e-mail.** O produto é a consulta online (dashboard publicado).
- Roda **1× por semana**, de forma automática.
- Foco contínuo em **refino de busca/filtros** e **UX**.

---

## Fase 2 — Normalização e deduplicação (18/08/2026)

O conceito de **imóvel** passou a existir. `imoveis` continua modelando
ANÚNCIO (uma publicação, chaveada por URL); a tabela `imovel` representa a
unidade física, ligada por `imovel_anuncio` — que guarda o score e a
classificação, para a decisão poder ser conferida e desfeita.

- [x] **`resolucao.py`** — blocking, comparadores, vetos e clusterização.
  - **Blocking** com 6 chaves em união (geo, endereço, bairro+forma,
    condomínio, foto, contato). A chave de forma emite a faixa de área **e
    as vizinhas**: sem isso, Viva Real dizendo 72 m² e Zap dizendo 75 m²
    cairiam em faixas diferentes e o par nunca seria comparado. Só esse
    ajuste dobrou os pares examinados (48 → 94).
  - **9 comparadores** ponderados, cada um devolvendo 0..1 ou `None`. A
    média é calculada só sobre quem pôde opinar.
  - **Vetos**: cidades diferentes, 2+ quartos de diferença, área divergindo
    mais de 25%, e **mesma fonte** — portal sério não duplica o próprio
    anúncio, então dois anúncios do mesmo site quase sempre são unidades
    distintas do mesmo prédio.
  - **Trava de evidência**: com menos de 3 comparadores ativos o teto é
    `PROVAVELMENTE_MESMO`. Dois sinais fracos coincidindo não é o mesmo que
    três independentes concordando.
  - **Trava de transitividade**: um cluster só se forma se TODOS os pares
    internos alcançam o limiar. Sem ela, A~B e B~C arrastariam A e C para o
    mesmo imóvel mesmo sendo claramente diferentes.
- [x] **Consolidação com registro de conflito** — valor vencedor por maioria,
  depois mediana (numérico) ou fonte mais confiável. Divergência **nunca é
  resolvida em silêncio**: vai para a tabela `conflito` e aparece no card.
- [x] **Custo decomposto** (P-08) — `utils.decompor_custo` separa aluguel,
  condomínio e IPTU, com flag `custo_completo`. Sem o condomínio o total é
  um piso, não o custo real.
- [x] **Título gerado** (P-06) — `utils.gerar_titulo` produz
  `Apartamento · 3 quartos · 78 m² · Boa Viagem` a partir dos campos
  normalizados. O texto raspado (que trazia `+6 fotos`, `IMÓVEIS` e string
  vazia) vira `titulo_origem`, guardado para auditoria e para o matching de
  descrição.
- [x] **Dashboard e Excel por imóvel** — um apartamento, um card, N selos de
  fonte. Card ganhou R$/m², dias no mercado, aviso de custo parcial e marca
  de divergência. O histórico de preço é a união das séries dos anúncios do
  mesmo imóvel, então a queda aparece assim que **qualquer** fonte baixa.

**Resultado medido:** 69 anúncios → **47 imóveis**, 21 deles com 2+ fontes.
**Redução de 32%** na lista. Exemplo real agrupado corretamente:
`2 quartos · 85 m² · Boa Viagem` anunciado simultaneamente no Zap, no Viva
Real e na Rede Imóveis Pernambuco — antes eram três linhas para avaliar.

Histórico preservado na migração: `primeiro_visto` mais antigo continua
2026-07-22 e os 272 pontos de preço estão intactos.

Testes: **91 → 111**.

**Pendente da Fase 2:**

- [ ] **Gabarito rotulado à mão** para calibrar os limiares. Os cortes atuais
  (0,88 / 0,72 / 0,55) são um ponto de partida defensável, não medido.
  Rotular os grupos da base e ajustar para precisão ≥ 0,97 na faixa
  `MESMO_IMOVEL` — agrupar errado é o erro caro.
- [ ] **Revisão humana** dos matches na faixa 0,72–0,88, com um clique para
  desfazer no dashboard.
- [ ] **Geocoding**: o comparador `geo` tem peso 0,20 (o maior) e hoje nunca
  opina, porque nenhuma fonte entrega coordenada.

---

## Épico 0 — Migração para operação no GitHub (P0)

Pré-requisito de tudo. Hoje o projeto roda na mão na máquina local e manda
e-mail; o alvo é rodar sozinho no GitHub Actions e servir um site.

- [x] **0.1 — Workflow semanal no GitHub Actions** (P0)
  `.github/workflows/scrape.yml` com `schedule: cron` semanal + trigger
  manual (`workflow_dispatch`). Instala Python, deps e Chromium do
  Playwright, roda `main.py`.
  *Pronto:* rodada semanal executa sem intervenção e falha visível no
  painel do Actions se quebrar. **Falta:** primeiro push pro GitHub +
  ativar Pages em Settings (passo manual do usuário, ver README).

- [x] **0.2 — Remover fluxo de e-mail** (P0)
  Tirado `report.enviar_email`, `EMAIL_CONFIG`, imports SMTP/MIME e a
  chamada em `main.py`. Confirmado por grep + import smoke-test: zero
  referência a smtp/MIME/e-mail no código.

- [x] **0.3 — Publicar dashboard no GitHub Pages** (P0)
  Job `publicar` do workflow copia `saida/dashboard.html` → `_site/index.html`
  e usa `actions/upload-pages-artifact` + `actions/deploy-pages`.
  *Falta validar ao vivo* na primeira rodada real no GitHub.

- [x] **0.4 — Persistir histórico entre rodadas** (P0)
  Decisão: commitar `saida/apartamentos.db` (+ `.xlsx`) de volta no
  repositório a cada rodada (passo "Persistir banco/planilha" no workflow).
  `dashboard.html`/`scraper.log` ficam fora do git (`.gitignore`) por serem
  artefato de build/log, não histórico.

- [ ] **0.5 — Excel deixa de ser saída obrigatória** (P1)
  Decisão parcial: Excel continua sendo gerado e comitado (histórico), mas
  ainda **não tem link no dashboard**. Falta expor o download.

- [x] **0.6 — README reescrito para o novo modelo** (P1)
  README novo descreve operação semanal via Actions, publicação no Pages,
  setup do repositório e lista de sites atual.

---

## Épico 1 — Refino de busca e filtros (P1)

- [ ] **1.1 — Deduplicação entre fontes** (P1)
  O mesmo apartamento aparece no OLX, Zap e Viva Real ao mesmo tempo.
  Agrupar por (bairro + área + preço + nº quartos) aproximados e mostrar
  uma linha com os selos das fontes, em vez de N linhas repetidas.
  *Pronto:* duplicatas óbvias colapsam num card com múltiplas fontes.

- [ ] **1.2 — Excluir tipos indesejados de forma robusta** (P1)
  Flat / apart-hotel / kitnet / temporada / mobiliado-curto poluem a
  lista. Hoje `titulo_aceito` só barra comercial. Adicionar blocklist
  configurável e detectar "apart-hotel/flat" (REMAX já expõe esse tipo).
  *Pronto:* filtro liga/desliga esses tipos; padrão exclui temporada.

- [ ] **1.3 — Filtro de custo por m²** (P1)
  Já ordena por custo/m² no dashboard; falta filtrar por teto de R$/m².
  Melhor sinal de "vale a pena" que preço absoluto.
  *Pronto:* campo de R$/m² máximo funcional no dashboard.

- [ ] **1.4 — Allowlist / blocklist de bairros** (P2)
  Deixar o usuário fixar bairros de interesse (ou excluir bairros ruins)
  por cidade, na config.
  *Pronto:* config aceita listas por cidade e o filtro respeita.

- [ ] **1.5 — Transparência de preço total** (P2)
  `parse_preco_total` já soma aluguel+condomínio+IPTU quando o card expõe.
  Guardar as parcelas separadas (aluguel, condomínio, IPTU) para o card
  mostrar a composição, não só o total.
  *Pronto:* card distingue aluguel de encargos quando o dado existe.

- [ ] **1.6 — Filtros configuráveis por perfil/cidade sem editar código** (P2)
  Mover `FILTROS_POR_CIDADE` e a lista de sites para um `config.yaml`/`json`
  validado, separando "configuração do usuário" de "código".
  *Pronto:* trocar cidade/faixa não exige mexer em `.py`.

---

## Épico 2 — Qualidade de dados (P1)

- [ ] **2.1 — Enriquecer campos faltantes pela página de detalhe** (P1)
  Quando o card de listagem não traz quartos/área (ex: OLX sem rótulo no
  ícone), abrir a página do anúncio só nesses casos e completar. Custo
  controlado por ser sob demanda.
  *Pronto:* taxa de "quartos/área nulos" cai mensuravelmente no OLX.

- [ ] **2.2 — Normalizar nomes de bairro** (P2)
  "Gracas"/"Graças", "Boa Vista"/"Boa vista" viram entradas distintas no
  dropdown. Normalizar acento/caixa/apelidos.
  *Pronto:* dropdown de bairro sem duplicatas por grafia.

- [ ] **2.3 — Flag de confiança no parsing** (P2)
  Marcar campos inferidos por heurística frágil (ex: preço pego do 1º "R$"
  do texto) para o dashboard sinalizar "verificar no anúncio".
  *Pronto:* card mostra aviso quando o preço/área é de baixa confiança.

- [ ] **2.4 — Geocodificar para o mapa** (P2)
  Derivar coordenadas do bairro/endereço para habilitar visão de mapa
  (ver 3.4). Cachear para não geocodificar de novo toda semana.
  *Pronto:* imóveis com bairro conhecido têm lat/long em cache.

---

## Épico 3 — UX do dashboard (P1)

- [ ] **3.1 — Persistir filtros na URL** (P1)
  Estado dos filtros na query string → link compartilhável e refresh não
  perde a busca. Base para "salvar busca".
  *Pronto:* aplicar filtros muda a URL; abrir a URL restaura os filtros.

- [ ] **3.2 — Marcar/ocultar imóveis (favoritos + descartados)** (P1)
  `localStorage` guarda favoritos e "não me mostre mais". Some o ruído de
  anúncios já avaliados.
  *Pronto:* favoritar e descartar persistem entre visitas no mesmo browser.

- [ ] **3.3 — Rastrear imóveis que saíram do ar** (P1)
  O DB já sabe o que foi "visto na última execução". Mostrar aba/seção de
  "saiu do ar esta semana" e há quantos dias cada anúncio está no mercado
  (days-on-market).
  *Pronto:* dashboard distingue novo / ativo / removido e mostra idade.

- [ ] **3.4 — Visão de mapa** (P2)
  Alternar entre lista e mapa (depende de 2.4). Mapa ajuda a filtrar por
  região de fato.
  *Pronto:* toggle lista/mapa com pins por imóvel.

- [ ] **3.5 — Miniaturas / foto do anúncio** (P2)
  Capturar a 1ª imagem do card quando disponível. Lista com foto decide
  muito mais rápido que lista de texto.
  *Pronto:* card mostra thumbnail quando a fonte expõe imagem.

- [ ] **3.6 — Tema claro/escuro + responsivo revisado** (P2)
  Suporte a `prefers-color-scheme` e ajuste fino no mobile.
  *Pronto:* legível e usável em claro, escuro e em tela de celular.

- [ ] **3.7 — Resumo semanal no topo** (P2)
  "X novos, Y sumiram, Z quedas de preço desde a semana passada" — aproveita
  o histórico do DB para dar o pulso da semana de cara.
  *Pronto:* faixa de destaque com os deltas da semana.

---

## Épico 4 — Confiabilidade e observabilidade (P1)

- [ ] **4.1 — Painel de saúde das fontes** (P1)
  Uma fonte que volta com 0 resultados normalmente quebrou (mudou o site).
  Registrar por fonte: nº de anúncios crus, nº dentro do filtro, status.
  Mostrar no rodapé do dashboard e alertar quando uma fonte zera.
  *Pronto:* dá para ver rápido qual scraper quebrou na última rodada.

- [ ] **4.2 — Detecção de regressão de scraper** (P1)
  Comparar contagem crua da rodada com a anterior; queda abrupta (ex: de
  50 para 0) abre issue automática no GitHub / marca o Action como falho.
  *Pronto:* quebra silenciosa de uma fonte vira alerta visível.

- [ ] **4.3 — Ampliar cobertura de testes** (P2)
  Fixar mais textos reais de card por fonte (OLX/REMAX/Imovelweb/CTI) como
  regressão de parsing, e testar o filtro por cidade ponta a ponta.
  *Pronto:* mudar um regex quebra teste se regredir uma fonte conhecida.

- [ ] **4.4 — Robustez anti-bot / retry** (P2)
  Backoff e retry nos portais protegidos; opção de Bright Data já existe
  mas está solta. Documentar quando ligar.
  *Pronto:* falha transitória de rede não zera uma fonte na rodada.

---

## Épico 5 — Manutenibilidade (P2)

- [ ] **5.1 — Guia "como adicionar um site"** (P2)
  Documento curto: achar a URL de listagem certa, escolher o `tipo`,
  descobrir `seletor_href`/paginação. Encurta a próxima inclusão.
  *Pronto:* CONTRIBUTING/README explica o passo a passo com um exemplo.

- [ ] **5.2 — Validação do schema de config** (P2)
  Validar cada entrada de `SITES` na carga (campos obrigatórios por tipo),
  com erro claro em vez de quebrar no meio da rodada.
  *Pronto:* config inválida falha cedo com mensagem útil.

- [ ] **5.3 — Lint + type check no CI** (P2)
  `ruff`/`mypy` num workflow de PR para segurar qualidade.
  *Pronto:* PR roda lint/type check automático.

---

## Ordem sugerida de ataque

1. **Épico 0 inteiro** — sem isso não há "produto no GitHub rodando sozinho".
2. **4.1 + 4.2** — assim que roda sozinho, precisa avisar quando quebra.
3. **1.1, 1.2, 2.1** — qualidade da lista (dedupe, tipos, campos faltando).
4. **3.1, 3.2, 3.3** — UX que mais muda o dia a dia de quem consulta.
5. Resto conforme necessidade.
