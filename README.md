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

Sem chave de API nem segredo obrigatório para o funcionamento básico
(Bright Data é opcional — ver seção abaixo).

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

## Bright Data (opcional)

Alguns portais têm proteção anti-bot forte; hoje contornamos via
Playwright headless com flags anti-detecção, que cobre a maioria dos
casos. Se algum voltar a falhar, dá pra configurar Bright Data Web
Unlocker via `BRIGHTDATA_API_KEY`/`BRIGHTDATA_UNLOCKER_ZONE` (variáveis de
ambiente, ou secrets do repositório se rodando via Actions).

## Estrutura dos arquivos

```
config.py                     -> filtros por cidade, lista de sites
utils.py                      -> HTTP e parsing de texto (preço/área/quartos)
db.py                         -> SQLite: histórico e detecção de "novo"
scraper_playwright.py         -> scraper principal (Chromium headless) -- maioria dos sites
scraper_pratica_internet.py   -> scraper p/ sites HTML estático (Luiza Parizi, Belchior Alvarez)
scraper_cards_inline.py       -> scraper genérico p/ sites c/ dados no card (Âncora, Abasol, ...)
scraper_portais.py            -> scraper JSON via Bright Data (fallback, não usado por padrão hoje)
report.py                     -> gera a planilha Excel
dashboard.py                  -> gera o dashboard.html
main.py                       -> roda tudo (chamado pelo workflow)
test_*.py                     -> testes de regressão do parsing
.github/workflows/scrape.yml  -> agendamento semanal + publicação no Pages
saida/                        -> gerado automaticamente (dashboard, Excel, banco, log)
```

## Observação sobre Termos de Uso

Scraping de sites públicos para uso pessoal (buscar seu próprio
apartamento) geralmente não é problema, mas evite aumentar a frequência
além de 1x/semana para não sobrecarregar os servidores das imobiliárias
menores.
