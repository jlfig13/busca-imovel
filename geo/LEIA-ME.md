# Contornos de bairro

`bairros.json` é o cache de geometria da aba **Mapa**. Chave `"Cidade|Bairro"`,
valor `{"anel": [[lon, lat], ...], "centro": [lon, lat]}`.

**Por que fica versionado.** Fronteira de bairro não muda. Consultar o
Overpass 12 vezes por dia para receber o mesmo polígono seria carga gratuita
num serviço voluntário da OpenStreetMap — e este projeto acabou de gastar uma
fase inteira sendo cuidadoso com carga alheia (robots.txt, Crawl-delay). Cada
bairro é buscado **uma vez na vida do projeto**. É a mesma forma de
`triagem.json`: dado que muda devagar mora no repositório.

**Como se preenche.** Sozinho, na rodada (`geo.atualizar` em `main.py`), no
máximo 25 bairros por vez — o que não couber hoje entra amanhã. O workflow
commita o arquivo junto com o banco.

`{"anel": null}` é ausência registrada de propósito: bairro que o OSM não tem
não pode ser perguntado de novo a cada rodada.

**Atribuição.** Os dados vêm da OpenStreetMap sob **ODbL**, que exige crédito
de quem redistribui. O dashboard credita no rodapé da aba Mapa. Não é
formalidade: é a mesma postura que fez o projeto respeitar robots.txt.
