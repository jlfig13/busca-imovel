# Monitor de Apartamentos — guia para o Claude Code

Robô que raspa ~20 sites de aluguel em Recife e Olinda, consolida anúncios em
imóveis físicos e publica um dashboard estático no GitHub Pages.

## Antes de começar qualquer sessão

Leia, nesta ordem:

1. **[.claude/progress/current.md](.claude/progress/current.md)** — onde o
   trabalho parou, o que está no ar, o que está aberto agora.
2. **[BACKLOG.md](BACKLOG.md)** — histórico das fases com o *porquê* de cada
   decisão e a lista do que ainda não foi feito.

Os dois juntos evitam refazer análise já feita: o BACKLOG registra decisões
que parecem erradas sem contexto (por exemplo, por que "zero exclusivos" foi
descartado como critério de corte de fonte).

Ao fechar um bloco de trabalho, **atualize o `current.md`** e acrescente ao
BACKLOG o que entrou.

## Comandos

```bash
python main.py                 # rodada completa (raspa, consolida, gera saída)
python -m pytest -q            # 130 testes, ~3s
gh workflow run "Monitor de Apartamentos"   # dispara a rodada no Actions
```

O dashboard local fica em `saida/dashboard.html` (gitignored) e o público em
https://jlfig13.github.io/busca-imovel/ — só atualiza depois de uma rodada.

Para inspecionar layout sem rodar o scraper: gere o HTML a partir de uma
**cópia** do banco (`saida/apartamentos.db`) em diretório temporário.
`db.consolidar_imoveis()` escreve no banco — nunca aponte um teste de layout
para o arquivo versionado.

## Mapa do código

| arquivo | papel |
|---|---|
| `main.py` | orquestra a rodada: triagem, coleta paralela, consolidação, saída |
| `config.py` | fontes, filtros por cidade, caminhos — fonte única de verdade |
| `db.py` | esquema, execuções, eventos, ciclo de vida, consolidação, manutenção |
| `resolucao.py` | dedupe: blocos, comparadores e fusão de anúncios em imóvel |
| `dashboard.py` | HTML autocontido (dados embutidos como JSON) |
| `design.py` | design system: tokens, CSS e o racional de cada decisão |
| `report.py` | planilha .xlsx |
| `robots.py` | veredito de robots.txt, revalidado a cada 30 dias |
| `scraper_*.py`, `extracao_jsonld.py` | coletores por estratégia |

## Invariantes do projeto

- **O dashboard é um arquivo só, sem servidor.** Abre por duplo clique,
  funciona offline. Nada de CDN, framework ou fetch em runtime — só as fotos
  remotas, que degradam para um marcador cinza quando não carregam.
  Corolário: cuidado com API de browser que exige origem — `replaceState` em
  `file://` levanta `SecurityError` e já derrubou o render inteiro uma vez.
- **O banco é commitado a cada rodada.** SQLite é binário: cada commit
  reescreve o arquivo. Por isso existe poda diária e VACUUM aos domingos, e
  por isso tabela redundante é dívida real, não estética.
- **Ausência de anúncio só conta se a fonte estava saudável.** Fonte que
  quebrou não faz imóvel "sumir" — é a diferença entre não achar e não olhar.
- **Divergência entre fontes é registrada, nunca resolvida em silêncio**
  (tabela `conflito`, selo no card).
- **Preço de vitrine é o MENOR entre as fontes** — é o que se paga de fato.

## Convenções

- Código, comentários, commits e PRs em **português**.
- Comentário explica **por que**, não o que. Se uma decisão parece estranha
  sem contexto, o contexto vai junto — inclusive a alternativa descartada.
- Mudança de comportamento vem com teste. `test_*.py` na raiz, pytest puro.
- Nomes de fonte, campo e status seguem o que já existe em `config.py`/`db.py`.
- Nada de trocar filtro, cadência ou fonte sem o usuário pedir: são decisões
  de produto, não de implementação.

## Alvos de UI

O dashboard é lido no celular: **Poco X6 Pro** (Chrome Android, ~412px CSS) e
**iPhone 11** (Safari, 414px, notch). Duas regras que já custaram bug:
campo de formulário abaixo de 16px faz o Safari dar zoom ao focar, e rolagem
horizontal no conteúdo é inaceitável — tabela larga vira lista de blocos.
Referência visual: cards de portal (Zap/Viva Real), não lista de jornal.
