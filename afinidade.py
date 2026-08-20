# -*- coding: utf-8 -*-
"""
Nota de afinidade: o quanto cada imóvel combina com o perfil de busca.

O filtro responde "cabe?". Esta nota responde "é o melhor?" -- que é outra
pergunta, e a que interessa quando 19 apartamentos passam no filtro e a
pessoa tem meia hora para escolher qual visitar.

O perfil está em `config.PERFIL` e veio de perguntas diretas ao usuário
(19/08/2026): custo mensal baixo, melhor área pelo preço e bairro certo
pesam junto; menos de 3 quartos desqualifica; o resultado aparece como selo
"Melhor achado" nos três primeiros.

DECISÕES QUE PARECEM ERRADAS SEM CONTEXTO
------------------------------------------
1. A nota é RELATIVA ao que está na tela, não absoluta. Um imóvel de R$ 2.400
   é "caro" numa lista que vai de 1.500 a 2.500 e é "o mais barato" numa que
   começa em 2.400. Nota absoluta obrigaria calibrar constantes toda vez que
   o mercado ou o filtro mudasse.

2. Imóvel sem o dado NÃO ganha nota média por isso. Área desconhecida vale
   zero no critério de espaço. Tratar ausência como "mediano" faria anúncio
   mal preenchido subir por não ter sido conferido -- e é justamente o
   anúncio ruim que costuma vir sem dado.

3. Custo incompleto (sem condomínio informado) entra com desconto. O preço
   ali é piso, não custo: sem o desconto, o anúncio que esconde encargo
   ficaria sempre à frente do que os informa.
"""
import config

# Escala interna dos critérios: cada um devolve 0..1 e entra com seu peso.
# A soma dos pesos não precisa dar 1 -- a nota é normalizada no fim.
PESOS = {
    "custo": 1.0,      # sobrar dinheiro
    "espaco": 1.0,     # R$/m²
    "bairro": 1.0,     # estar num bairro preferido
    "confianca": 0.4,  # custo completo, mais de uma fonte confirmando
    "momento": 0.3,    # entrou agora ou baixou de preço
}

# Quantos recebem o selo. Três porque é o que cabe numa manhã de visitas --
# selo em dez imóveis não é recomendação, é decoração.
DESTAQUES = 3


def _normalizar(valor, menor, maior, invertido=False):
    """Posição de `valor` na faixa observada, em 0..1."""
    if valor is None or maior is None or menor is None or maior == menor:
        return None
    p = (valor - menor) / (maior - menor)
    p = max(0.0, min(1.0, p))
    return 1 - p if invertido else p


def _faixa(valores):
    validos = [v for v in valores if v is not None]
    return (min(validos), max(validos)) if validos else (None, None)


def pontuar(imoveis: list[dict]) -> list[dict]:
    """Anota `score` (0-100), `motivos` e `melhor` em cada imóvel.

    Devolve a mesma lista, para poder encadear. Não reordena: quem ordena é
    o dashboard, e a ordenação escolhida pelo usuário continua mandando."""
    if not imoveis:
        return imoveis

    perfil = config.PERFIL
    preferidos = {b.lower() for b in perfil.get("bairros_preferidos", [])}
    quartos_min = perfil.get("quartos_min_desejado") or 0

    custo_min, custo_max = _faixa([i.get("preco") for i in imoveis])
    m2_min, m2_max = _faixa([i.get("precoM2") for i in imoveis])

    for i in imoveis:
        criterios: dict[str, float] = {}
        motivos: list[str] = []

        # --- custo mensal: mais barato que os concorrentes vale mais
        custo = _normalizar(i.get("preco"), custo_min, custo_max, invertido=True)
        if custo is not None:
            criterios["custo"] = custo
            if custo >= 0.7:
                motivos.append("entre os mais baratos da lista")

        # --- espaço pelo preço
        espaco = _normalizar(i.get("precoM2"), m2_min, m2_max, invertido=True)
        if espaco is not None:
            criterios["espaco"] = espaco
            if espaco >= 0.7:
                motivos.append("melhor área pelo preço")

        # --- bairro
        bairro = (i.get("bairro") or "").lower()
        if bairro and bairro in preferidos:
            criterios["bairro"] = 1.0
            motivos.append(f"bairro preferido ({i['bairro']})")
        else:
            # já passou pelo recorte de exibição, então não é bairro ruim --
            # só não está na lista curta
            criterios["bairro"] = 0.35

        # --- confiança no dado
        confianca = 0.0
        if i.get("custoCompleto"):
            confianca += 0.6
        if (i.get("qtdFontes") or 1) > 1:
            confianca += 0.4
            motivos.append(f"{i['qtdFontes']} fontes confirmam")
        criterios["confianca"] = confianca

        # --- momento
        momento = 0.0
        if i.get("novo"):
            momento += 0.6
            motivos.append("novo hoje")
        if i.get("queda"):
            momento += 0.4
            motivos.append("baixou de preço")
        criterios["momento"] = min(momento, 1.0)

        bruto = sum(PESOS[k] * v for k, v in criterios.items())
        teto = sum(PESOS[k] for k in criterios)
        nota = 100 * bruto / teto if teto else 0

        # Requisito do perfil (3 quartos). Não esconde o imóvel: um 2
        # quartos grande e barato ainda merece ser visto -- mas atrás de
        # QUALQUER um que atenda, e não só com nota menor. Só descontar a
        # nota não bastava: medido, um 2 quartos barato e espaçoso ficava
        # com 38 contra 16 de um 3 quartos caro, ou seja, o "obrigatório"
        # não obrigava nada. Quem ordena usa `atende` como primeira chave.
        quartos = i.get("quartos")
        atende = not (quartos_min and (quartos or 0) < quartos_min)
        if not atende:
            nota *= 0.55
            motivos.append(f"só {quartos or '?'} quartos")

        i["atende"] = atende
        i["score"] = round(nota)
        i["motivos"] = motivos[:3]
        i["melhor"] = False

    # Selo só para quem realmente se destaca: nota alta E acima da média.
    # Numa lista ruim, o "melhor" de todos ainda pode não valer a visita --
    # e um selo dizendo o contrário gasta a confiança do usuário.
    # O piso é relativo à lista (25% acima da média) com um mínimo absoluto
    # baixo: piso alto e fixo fazia o selo sumir em rodada fraca, que é
    # justamente quando a recomendação ajuda mais. O que o selo promete é
    # "melhor do que está no ar hoje", não "bom em termos absolutos".
    media = sum(i["score"] for i in imoveis) / len(imoveis)
    elegiveis = [i for i in imoveis
                 if i["score"] >= max(45, media * 1.25) and i["atende"]]
    for i in sorted(elegiveis, key=lambda x: -x["score"])[:DESTAQUES]:
        i["melhor"] = True

    return imoveis
