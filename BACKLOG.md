# Backlog de Melhorias — Monitor de Apartamentos

Documento vivo. Cada item tem **prioridade** (P0 = necessário para o novo
modelo de operação, P1 = alto valor, P2 = incremental), um **porquê** e uma
**definição de pronto** enxuta.

**Nova direção do produto:**
- Hospedado no **GitHub** (código + dashboard estático).
- **Sem e-mail.** O produto é a consulta online (dashboard publicado).
- Roda **1× por semana**, de forma automática.
- Foco contínuo em **refino de busca/filtros** e **UX**.

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
