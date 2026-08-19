# Estado Atual

**Atualizado em:** 2026-08-19
**Branch:** `main` (limpa, sem PR aberto)
**No ar:** https://jlfig13.github.io/busca-imovel/

---

## O que acabou de entrar

| PR | O quê |
|---|---|
| [#3](https://github.com/jlfig13/busca-imovel/pull/3) | Catálogo em cards + dashboard responsivo (Poco X6 Pro / iPhone 11) |
| [#4](https://github.com/jlfig13/busca-imovel/pull/4) | Cron 07:00 → 07:13 BRT, fora da hora cheia |
| [#5](https://github.com/jlfig13/busca-imovel/pull/5) | `historico_precos` aposentada, aba "Fontes" com rendimento, filtros na URL |

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
- [ ] Favoritos / descartados no dashboard — precisa de armazenamento local,
      já que o arquivo é regerado a cada rodada.
- [ ] Alerta ativo — hoje é preciso abrir o dashboard para saber que algo
      baixou de preço.

---

## Estado da operação

- Cron diário às 10:13 UTC (07:13 BRT) + disparo manual.
- 130 testes, ~3s.
- Banco: poda diária de inativos com 180+ dias, VACUUM aos domingos.
- REMAX reativado e produzindo (64 coletados, 4 no filtro, 1 exclusivo).
- `saida/apartamentos.db` e `.xlsx` são commitados pelo workflow a cada
  rodada — evitar mexer neles localmente para não conflitar com o `git pull`.
