# Estado Atual

**Atualizado em:** 2026-08-20
**Branch:** `main` (limpa, sem PR aberto)
**No ar:** https://jlfig13.github.io/busca-imovel/

---

## O que acabou de entrar

| PR | O quê |
|---|---|
| [#3](https://github.com/jlfig13/busca-imovel/pull/3) | Catálogo em cards + dashboard responsivo (Poco X6 Pro / iPhone 11) |
| [#4](https://github.com/jlfig13/busca-imovel/pull/4) | Cron 07:00 → 07:13 BRT, fora da hora cheia |
| [#5](https://github.com/jlfig13/busca-imovel/pull/5) | `historico_precos` aposentada, aba "Fontes" com rendimento, filtros na URL |
| [#6](https://github.com/jlfig13/busca-imovel/pull/6) | CLAUDE.md + este arquivo, `.claude/progress/` versionado |

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
- [ ] Favoritos / descartados no dashboard — precisa de armazenamento local,
      já que o arquivo é regerado a cada rodada.
- [ ] Alerta ativo — hoje é preciso abrir o dashboard para saber que algo
      baixou de preço.

---

## Estado da operação

- Cron 2x/dia: 11:13 e 21:13 UTC (08:13 e 18:13 BRT) + disparo manual.
- 130 testes, ~3s.
- Banco: poda diária de inativos com 180+ dias, VACUUM aos domingos.
- REMAX reativado e produzindo (64 coletados, 4 no filtro, 1 exclusivo).
- `saida/apartamentos.db` e `.xlsx` são commitados pelo workflow a cada
  rodada — evitar mexer neles localmente para não conflitar com o `git pull`.
