# Monitor de Apartamentos — Recife e Olinda

Robô que busca apartamentos para alugar em Recife e Olinda em ~20 sites
(portais grandes tipo OLX/Zap/Viva Real/Imovelweb/REMAX + imobiliárias
locais), roda **2x por dia no GitHub Actions** e publica o resultado
num **dashboard online** (GitHub Pages) — sem e-mail, é consulta direta.

**Filtros atuais** (`config.py`):
- Preço: R$ 1.500 – 2.500
- Recife: 2+ quartos, 60m²+
- Olinda: 3+ quartos, 70m²+

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
| OLX Imóveis | Recife/Olinda/Jaboatão (busca região inteira, cidade detectada por anúncio) | Playwright |
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
