# Monitor de Apartamentos — Recife e Olinda

Robô que busca apartamentos para alugar em Recife e Olinda em ~20 sites
(portais grandes tipo OLX/Zap/Viva Real/Imovelweb/REMAX + imobiliárias
locais), roda **2x por dia no GitHub Actions** e publica o resultado
num **dashboard online** (GitHub Pages) — sem e-mail, é consulta direta.

**Duas camadas de filtro, e a diferença importa:**

- **Envelope de coleta** (`config.FILTROS` + `FILTROS_POR_CIDADE`): o que entra
  no banco. Hoje R$ 800–6.000, 1+ quarto, 30m²+. Nada fora dele pode aparecer
  no dashboard, porque nunca foi coletado.
- **Preferências** (no dashboard, salvas no navegador): o recorte de quem está
  olhando — faixa de preço, quartos, área mín/máx, cidades e bairros. Abrem no
  padrão de `config.PREFERENCIAS_PADRAO` e mudam com um toque, sem esperar a
  próxima rodada. É o que permite que outra pessoa use o mesmo dashboard com o
  critério dela.

**Recorte geográfico:** Recife, Olinda e a Região Metropolitana (Jaboatão,
Paulista, Camaragibe, Igarassu, Ipojuca, Cabo, Abreu e Lima, São Lourenço da
Mata, Moreno). Quem manda é `FILTROS_POR_CIDADE`: ter perfil ali é o que
autoriza a cidade a entrar. Cidade fora disso é rejeitada com motivo, e cidade
não identificada fica indeterminada — nunca é completada com "Recife".

**Preferência inicial** (`config.PREFERENCIAS_PADRAO`, editável na tela):
- Preço: R$ 1.500 – 2.500
- 2+ quartos, 60m²+
- Recife e Olinda, nos bairros preferidos

Veja [BACKLOG.md](BACKLOG.md) para o roadmap de melhorias em andamento.

## Como funciona

```
.github/workflows/scrape.yml   -> roda 08:13 e 18:13 (BRT), + botão manual
        │
        ├─ python main.py             (raspa todos os sites, aplica filtro)
        ├─ commita saida/apartamentos.db + .xlsx de volta no repo
        │  (é assim que o histórico de preço sobrevive entre rodadas)
        └─ publica saida/dashboard.html no GitHub Pages
```

Não tem envio de e-mail nem tarefa agendada na sua máquina — depois de
publicado no GitHub, o dashboard é só um link.

## Configurar o repositório (uma vez)

1. Suba este código para um repositório no GitHub (`git init`, `git remote
   add origin ...`, `git push`).
2. Em **Settings → Pages**, em "Build and deployment", escolha
   **Source: GitHub Actions**.
3. Rode o workflow uma vez manualmente: aba **Actions** →
   "Monitor de Apartamentos" → **Run workflow**. Depois disso ele roda
   sozinho às 08:13 e 18:13 (BRT).
4. O link do dashboard fica em **Settings → Pages** (formato
   `https://SEU_USUARIO.github.io/SEU_REPO/`).

Sem chave de API nem segredo: o robô roda só com o que está no repositório.

## Rodar localmente (para testar mudanças)

1. [Python 3.11+](https://www.python.org/downloads/) instalado.
2. Nesta pasta:
   ```powershell
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Rodar:
   ```powershell
   python main.py
   ```
   Gera dentro de `saida/`:
   - `dashboard.html` — abra com duplo clique. Filtros de cidade
     (encadeado com bairro), quartos, faixa de valor, fonte e busca livre;
     carimbo "NOVO" pro que apareceu pela primeira vez.
   - `apartamentos.xlsx` — mesma informação em planilha.
   - `apartamentos.db` — SQLite com o histórico (o que já foi visto,
     preço ao longo do tempo). **Isso é versionado no git de propósito**
     (ver `.gitignore`) — é a memória entre rodadas semanais.
   - `scraper.log` — log da execução (não versionado).

4. Testes:
   ```powershell
   python -m pytest -q
   ```

Na primeira execução (banco vazio) tudo aparece como "novo" — é esperado.

## Sites cobertos

| Fonte | Cidade | Tipo |
|---|---|---|
| OLX Imóveis | busca muito além da RMR (chega a Caruaru/Garanhuns); cidade detectada por anúncio, fora do recorte é rejeitado | Playwright |
| Viva Real / Viva Real Olinda | Recife / Olinda | Playwright |
| Zap Imóveis / Zap Imóveis Olinda | Recife / Olinda | Playwright |
| REMAX Recife / REMAX Olinda | Recife / Olinda | Playwright |
| Imovelweb / Imovelweb Olinda | Recife / Olinda | Playwright |
| CTI Imobiliária | Recife | Playwright |
| Josinildo Imóveis | Recife | Playwright |
| Luiza Parizi Imóveis | Recife | HTML estático |
| Belchior Alvarez Corretor | Recife | HTML estático |
| Âncora / Abasol / Camila Melo / Moradasol / Rede Imóveis PE / Sérgio Rodrigues / Rogério Corretor / Newville | Recife | Cards inline |
| Nogueira Corretores / Paulo Miranda Imóveis | — | 🚫 robots.txt proíbe scraping — não implementado, por respeito à política do site |

A lista completa com URLs está em `config.py` (`SITES`). Ver
`BACKLOG 5.1` para o guia de como adicionar um site novo.

## Estrutura dos arquivos

```
config.py                     -> filtros por cidade, lista de sites
utils.py                      -> HTTP e parsing de texto (preço/área/quartos)
db.py                         -> SQLite: histórico e detecção de "novo"
scraper_playwright.py         -> scraper principal (Chromium headless) -- maioria dos sites
scraper_pratica_internet.py   -> scraper p/ sites HTML estático (Luiza Parizi, Belchior Alvarez)
scraper_cards_inline.py       -> scraper genérico p/ sites c/ dados no card (Âncora, Abasol, ...)
scraper_chavesnamao.py        -> scraper do Chaves na Mão (HTML + detalhe de custo)
report.py                     -> gera a planilha Excel
dashboard.py                  -> gera o dashboard.html
main.py                       -> roda tudo (chamado pelo workflow)
test_*.py                     -> testes de regressão do parsing
.github/workflows/scrape.yml  -> agendamento 2x/dia + publicação no Pages
saida/                        -> gerado automaticamente (dashboard, Excel, banco, log)
```

## Triagem: favoritos e descartes

No dashboard, cada card tem ⭐ (favoritar) e ✕ (descartar) sobre a foto. O
descartado sai da lista e vai para a **Lixeira**, de onde volta com um clique.

A triagem vive em três camadas, da mais durável para a mais imediata:

1. **`triagem.json`** na raiz do repositório, versionado. É lido a cada
   geração e embutido no dashboard. Sobrevive a limpeza de dados do navegador
   e a troca de aparelho — é a única camada que sobrevive.
2. **Backup/restaurar**, na barra que aparece em Favoritos e na Lixeira. O
   arquivo baixado tem exatamente a forma do `triagem.json`: para tornar a
   triagem permanente, baixe o backup e commite o arquivo na raiz.
3. **`localStorage`**, para a marcação do dia valer na hora. É por navegador:
   o que você marcar no celular não aparece no computador. Se o navegador
   estiver bloqueando dados do site, o dashboard avisa em vez de perder a
   marcação em silêncio.

Formato do `triagem.json`:

```json
{
  "favoritos":   {"https://portal.com/imovel/123": "2026-08-22"},
  "descartados": {"https://portal.com/imovel/456": "2026-08-22"}
}
```

A chave é a **URL do anúncio** (não o id do imóvel, que é reconstruído a cada
rodada). Um imóvel conta como marcado se qualquer um dos seus anúncios estiver
na lista.

## Escopo, uso e limites

**Projeto pessoal e não comercial.** Existe para uma finalidade só: achar um
apartamento para alugar em Recife ou Olinda. Não é produto, não é serviço,
não vende nem revende dado, e não há qualquer relação com os portais e
imobiliárias monitorados.

O que o robô faz, e o que ele deliberadamente não faz:

- **Respeita `robots.txt`.** `robots.py` consulta a política de cada domínio,
  guarda o veredito com data e revalida a cada 30 dias; `main.py` pula a fonte
  quando a política proíbe. Quatro fontes estão desativadas em `config.py` por
  esse motivo — a checagem custa fonte, e é para isso que ela serve.
- **Respeita `Crawl-delay`.** Quando o site declara um intervalo, ele é
  cumprido por domínio, inclusive entre as coletas paralelas.
- **Não contorna proteção anti-bot de propósito.** Fonte que bloqueia é
  registrada como bloqueada e some da rodada; não existe serviço de contorno
  no código (ver a nota em `config.py`).
- **Não coleta nem publica dado pessoal.** O que entra é fato do imóvel:
  preço, endereço, área, quartos, vagas, andar. Nome, telefone e contato de
  anunciante ficam de fora.
- **Não redistribui conteúdo dos anúncios.** O dashboard publica dado factual
  e um link para o anúncio na origem; a foto é carregada da própria fonte, e
  a descrição do anúncio não vai para a página pública.

**Cadência:** duas rodadas por dia (08:13 e 18:13 BRT), poucas páginas por
fonte. Se for reaproveitar este código, mantenha a frequência baixa — boa
parte das fontes são imobiliárias pequenas, com servidor à altura.
