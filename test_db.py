# -*- coding: utf-8 -*-
"""Testes do registro de execução e da guarda de sanidade (P-04 da auditoria).

Usa um banco temporário: config.ARQUIVO_DB é reapontado antes de importar db,
para não tocar em saida/apartamentos.db (que é o histórico versionado).
"""
import os
import sqlite3
import tempfile

import pytest

import config


@pytest.fixture
def banco(monkeypatch):
    fd, caminho = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "ARQUIVO_DB", caminho)
    import db as _db
    yield _db
    try:
        os.unlink(caminho)
    except OSError:
        pass


def test_execucao_abre_e_encerra(banco):
    eid = banco.abrir_execucao("abc123")
    assert eid > 0
    banco.encerrar_execucao(eid, banco.OK)
    conn = banco.conectar()
    row = conn.execute("SELECT status, versao_codigo, encerrada_em FROM execucao WHERE id=?", (eid,)).fetchone()
    conn.close()
    assert row[0] == banco.OK
    assert row[1] == "abc123"
    assert row[2] is not None


def test_registrar_fonte_e_resumo(banco):
    eid = banco.abrir_execucao()
    banco.registrar_fonte(eid, "Zap", banco.OK, brutos=30, aprovados=8, indeterminados=2)
    resumo = banco.resumo_fontes(eid)
    assert len(resumo) == 1
    assert resumo[0]["fonte"] == "Zap"
    assert resumo[0]["brutos"] == 30
    assert resumo[0]["indeterminados"] == 2


def test_sanidade_sem_historico_nao_rebaixa(banco):
    # primeira vez que a fonte roda: não há com o que comparar
    status, motivo = banco.avaliar_sanidade("Nova", 5, banco.OK)
    assert status == banco.OK
    assert motivo is None


def test_sanidade_rebaixa_queda_abrupta(banco):
    # três rodadas saudáveis com ~30 anúncios...
    for _ in range(3):
        eid = banco.abrir_execucao()
        banco.registrar_fonte(eid, "Zap", banco.OK, brutos=30)
    # ...e agora a fonte devolve 2 sem erro técnico: layout mudou
    status, motivo = banco.avaliar_sanidade("Zap", 2, banco.OK)
    assert status == banco.PARCIAL
    assert "60%" in motivo


def test_sanidade_rebaixa_zero_anuncios(banco):
    eid = banco.abrir_execucao()
    banco.registrar_fonte(eid, "Zap", banco.OK, brutos=30)
    status, motivo = banco.avaliar_sanidade("Zap", 0, banco.OK)
    assert status == banco.PARCIAL
    assert "zero" in motivo


def test_sanidade_aceita_volume_normal(banco):
    eid = banco.abrir_execucao()
    banco.registrar_fonte(eid, "Zap", banco.OK, brutos=30)
    assert banco.avaliar_sanidade("Zap", 28, banco.OK)[0] == banco.OK


def test_sanidade_nao_mexe_em_status_ja_degradado(banco):
    # BLOQUEADO não vira PARCIAL: o motivo real já é conhecido
    assert banco.avaliar_sanidade("Zap", 0, banco.BLOQUEADO)[0] == banco.BLOQUEADO


def test_fonte_nao_confiavel_preserva_visto_na_ultima_execucao(banco):
    """O coração do P-04: se o Zap bloquear, seus imóveis não podem ser
    marcados como ausentes -- do contrário o sistema anuncia que sumiram."""
    itens = [
        {"url": "u1", "site": "Zap", "titulo": "a", "bairro": "Boa Viagem",
         "cidade": "Recife", "preco": 2000, "quartos": 3, "area_m2": 80},
        {"url": "u2", "site": "OLX", "titulo": "b", "bairro": "Pina",
         "cidade": "Recife", "preco": 2100, "quartos": 3, "area_m2": 75},
    ]
    banco.salvar_execucao(itens, fontes_confiaveis={"Zap", "OLX"})

    # rodada seguinte: só o OLX responde; o Zap falhou e não devolveu nada
    banco.salvar_execucao(
        [{"url": "u2", "site": "OLX", "titulo": "b", "bairro": "Pina",
          "cidade": "Recife", "preco": 2100, "quartos": 3, "area_m2": 75}],
        fontes_confiaveis={"OLX"},
    )

    conn = banco.conectar()
    vistos = dict(conn.execute(
        "SELECT url, visto_na_ultima_execucao FROM imoveis").fetchall())
    conn.close()
    assert vistos["u1"] == 1, "imóvel de fonte que falhou não pode virar 'sumiu'"
    assert vistos["u2"] == 1


def test_fonte_confiavel_marca_ausente_corretamente(banco):
    itens = [
        {"url": "u1", "site": "Zap", "titulo": "a", "bairro": "Boa Viagem",
         "cidade": "Recife", "preco": 2000, "quartos": 3, "area_m2": 80},
        {"url": "u2", "site": "Zap", "titulo": "b", "bairro": "Pina",
         "cidade": "Recife", "preco": 2100, "quartos": 3, "area_m2": 75},
    ]
    banco.salvar_execucao(itens, fontes_confiaveis={"Zap"})
    # u1 saiu do ar de verdade, com a fonte respondendo bem
    banco.salvar_execucao([itens[1]], fontes_confiaveis={"Zap"})

    conn = banco.conectar()
    vistos = dict(conn.execute(
        "SELECT url, visto_na_ultima_execucao FROM imoveis").fetchall())
    conn.close()
    assert vistos["u1"] == 0, "com a fonte saudável, ausência significa que saiu"
    assert vistos["u2"] == 1


def test_nenhuma_fonte_confiavel_nao_esvazia_o_dashboard(banco):
    itens = [{"url": "u1", "site": "Zap", "titulo": "a", "bairro": "Boa Viagem",
              "cidade": "Recife", "preco": 2000, "quartos": 3, "area_m2": 80}]
    banco.salvar_execucao(itens, fontes_confiaveis={"Zap"})
    # rodada catastrófica: nenhuma fonte respondeu
    banco.salvar_execucao([], fontes_confiaveis=set())

    conn = banco.conectar()
    visto = conn.execute(
        "SELECT visto_na_ultima_execucao FROM imoveis WHERE url='u1'").fetchone()[0]
    conn.close()
    assert visto == 1, "falha geral não pode zerar o dashboard"


# ---------------------------------------------------------------------------
# Fase 3 -- histórico por evento e ciclo de vida
# ---------------------------------------------------------------------------

def _item(url="u1", site="Zap", preco=2000.0, **kw):
    base = {"url": url, "site": site, "titulo": "t", "bairro": "Boa Viagem",
            "cidade": "Recife", "preco": preco, "custo_mensal_total": preco,
            "quartos": 3, "area_m2": 80}
    base.update(kw)
    return base


def test_evento_criado_na_primeira_vez(banco):
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    conn = banco.conectar()
    tipos = [r[0] for r in conn.execute("SELECT tipo FROM evento")]
    conn.close()
    assert banco.EV_CRIADO in tipos


def test_evento_de_preco_so_quando_muda(banco):
    banco.salvar_execucao([_item(preco=2000.0)], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([_item(preco=2000.0)], fontes_confiaveis={"Zap"})
    conn = banco.conectar()
    n = conn.execute("SELECT COUNT(*) FROM evento WHERE tipo=?",
                     (banco.EV_PRECO,)).fetchone()[0]
    conn.close()
    # preço igual não gera evento -- era esse o desperdício do snapshot diário
    assert n == 0


def test_evento_de_preco_registra_delta(banco):
    banco.salvar_execucao([_item(preco=2000.0)], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([_item(preco=1800.0)], fontes_confiaveis={"Zap"})
    conn = banco.conectar()
    row = conn.execute(
        "SELECT valor_antes, valor_depois, delta, delta_pct FROM evento WHERE tipo=?",
        (banco.EV_PRECO,)).fetchone()
    conn.close()
    assert float(row[0]) == 2000.0 and float(row[1]) == 1800.0
    assert row[2] == -200.0
    assert row[3] == -10.0


def test_ausencia_uma_vez_e_suspeito_nao_inativo(banco):
    """Uma falta não basta: portal grande reordena resultado e às vezes
    omite um anúncio de uma página."""
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([], fontes_confiaveis={"Zap"})
    r = banco.aplicar_ciclo_de_vida({"Zap"})
    assert r["suspeitos"] == 1 and r["inativos"] == 0
    conn = banco.conectar()
    st = conn.execute("SELECT status FROM imoveis WHERE url='u1'").fetchone()[0]
    conn.close()
    assert st == banco.SUSPEITO


def test_duas_ausencias_marcam_inativo_e_geram_evento(banco):
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([], fontes_confiaveis={"Zap"})
    banco.aplicar_ciclo_de_vida({"Zap"})
    banco.aplicar_ciclo_de_vida({"Zap"})
    conn = banco.conectar()
    st = conn.execute("SELECT status FROM imoveis WHERE url='u1'").fetchone()[0]
    n = conn.execute("SELECT COUNT(*) FROM evento WHERE tipo=?",
                     (banco.EV_SUMIU,)).fetchone()[0]
    conn.close()
    assert st == banco.INATIVO
    assert n == 1


def test_fonte_nao_confiavel_nao_gera_ciclo_de_vida(banco):
    """O coração do P-04 aplicado ao ciclo de vida: se o Zap falhou, seus
    imóveis não podem virar SUSPEITO."""
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([], fontes_confiaveis={"OLX"})
    r = banco.aplicar_ciclo_de_vida({"OLX"})
    assert r["suspeitos"] == 0
    conn = banco.conectar()
    st = conn.execute("SELECT COALESCE(status,'ATIVO') FROM imoveis WHERE url='u1'").fetchone()[0]
    conn.close()
    assert st == banco.ATIVO


def test_reaparecimento_gera_evento(banco):
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([], fontes_confiaveis={"Zap"})
    banco.aplicar_ciclo_de_vida({"Zap"})
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    conn = banco.conectar()
    n = conn.execute("SELECT COUNT(*) FROM evento WHERE tipo=?",
                     (banco.EV_REAPARECEU,)).fetchone()[0]
    st = conn.execute("SELECT status FROM imoveis WHERE url='u1'").fetchone()[0]
    conn.close()
    assert n == 1
    assert st == banco.ATIVO


def test_descricao_alterada_gera_evento(banco):
    banco.salvar_execucao([_item(descricao="a" * 80)], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([_item(descricao="b" * 80)], fontes_confiaveis={"Zap"})
    conn = banco.conectar()
    n = conn.execute("SELECT COUNT(*) FROM evento WHERE tipo=?",
                     (banco.EV_DESCRICAO,)).fetchone()[0]
    conn.close()
    assert n == 1


# ---------------------------------------------------------------------------
# Onda 1 -- série de preço vinda de evento, e manutenção
# ---------------------------------------------------------------------------

def test_criado_grava_o_preco_inicial(banco):
    """Sem o preço no CRIADO, imóvel que nunca mudou de valor não teria
    ponto nenhum na série."""
    banco.salvar_execucao([_item(preco=2000.0)], fontes_confiaveis={"Zap"})
    serie = banco.obter_serie_precos(["u1"])
    assert serie["u1"] == [[serie["u1"][0][0], 2000.0]]


def test_serie_acumula_mudancas_de_preco(banco):
    banco.salvar_execucao([_item(preco=2000.0)], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([_item(preco=1800.0)], fontes_confiaveis={"Zap"})
    banco.salvar_execucao([_item(preco=1800.0)], fontes_confiaveis={"Zap"})
    valores = [p for _, p in banco.obter_serie_precos(["u1"])["u1"]]
    # preço repetido não gera ponto novo -- era o desperdício do snapshot
    assert valores == [2000.0, 1800.0]


def _banco_legado(banco, linhas=(("2026-07-01", 2000.0), ("2026-07-02", 2000.0),
                                 ("2026-07-03", 1900.0))):
    """Recria a tabela aposentada, como num banco anterior à Fase 3."""
    conn = banco.conectar()
    conn.execute("""CREATE TABLE IF NOT EXISTS historico_precos (
        url TEXT NOT NULL, data TEXT NOT NULL, preco REAL, PRIMARY KEY (url, data))""")
    for data, preco in linhas:
        conn.execute("INSERT INTO historico_precos (url, data, preco) VALUES (?,?,?)",
                     ("u9", data, preco))
    conn.commit(); conn.close()


def test_migracao_do_historico_e_idempotente(banco):
    _banco_legado(banco)
    n1 = banco.migrar_historico_para_evento()
    n2 = banco.migrar_historico_para_evento()
    assert n1 == 2      # CRIADO 2000 + PRECO_ALTERADO 1900; o repetido é descartado
    assert n2 == 0      # reexecutar não duplica
    assert [p for _, p in banco.obter_serie_precos(["u9"])["u9"]] == [2000.0, 1900.0]


def test_migracao_e_no_op_sem_a_tabela_antiga(banco):
    # banco novo nasce sem historico_precos: migrar não pode explodir
    assert banco.migrar_historico_para_evento() == 0


def test_aposentadoria_migra_antes_de_derrubar(banco):
    """A série de julho existe SÓ no snapshot: derrubar sem migrar a perde."""
    _banco_legado(banco)
    assert banco.aposentar_historico_precos() is True

    conn = banco.conectar()
    assert not banco._tabela_existe(conn, "historico_precos")
    conn.close()
    # a série sobreviveu à queda da tabela
    assert [p for _, p in banco.obter_serie_precos(["u9"])["u9"]] == [2000.0, 1900.0]
    # segunda chamada não tem o que fazer
    assert banco.aposentar_historico_precos() is False


def test_rendimento_separa_exclusivo_de_redundante(banco):
    """Fonte redundante (outro portal traz o mesmo imóvel) tem exclusivos=0."""
    execucao = banco.abrir_execucao()
    itens = [
        _item(url="ex1", site="Zap", preco=2000.0),
        _item(url="ex2", site="Viva Real", preco=2000.0),
        _item(url="ex3", site="Só Aqui", preco=3100.0, area_m2=95.0),
    ]
    banco.salvar_execucao(itens, fontes_confiaveis={"Zap", "Viva Real", "Só Aqui"})
    for fonte in ("Zap", "Viva Real", "Só Aqui"):
        banco.registrar_fonte(execucao, fonte, "OK", brutos=5, aprovados=1,
                              duracao_s=10.0)
    # Zap e Viva Real anunciam o MESMO imóvel; Só Aqui é a única do dela
    banco.consolidar_imoveis(itens)

    por_fonte = {r["fonte"]: r for r in banco.rendimento_por_fonte()}
    assert por_fonte["Só Aqui"]["exclusivos"] == 1
    assert por_fonte["Zap"]["exclusivos"] == 0
    assert por_fonte["Viva Real"]["exclusivos"] == 0
    assert por_fonte["Zap"]["s_por_util"] == 10.0
    # pior rendimento primeiro: quem não tem exclusivo encabeça a lista
    assert banco.rendimento_por_fonte()[-1]["fonte"] == "Só Aqui"


def test_manutencao_preserva_anuncio_ativo(banco):
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    r = banco.manutencao()
    assert r["podados"] == 0
    conn = banco.conectar()
    assert conn.execute("SELECT COUNT(*) FROM imoveis").fetchone()[0] == 1
    conn.close()


def test_manutencao_poda_inativo_antigo(banco):
    from datetime import date, timedelta
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    velho = (date.today() - timedelta(days=banco.DIAS_PARA_PODA + 200)).isoformat()
    conn = banco.conectar()
    conn.execute("UPDATE imoveis SET status=?, ultima_confirmacao=? WHERE url='u1'",
                 (banco.INATIVO, velho))
    conn.commit(); conn.close()

    r = banco.manutencao()
    assert r["podados"] == 1
    conn = banco.conectar()
    assert conn.execute("SELECT COUNT(*) FROM imoveis").fetchone()[0] == 0
    # eventos do anúncio removido também saem
    assert conn.execute("SELECT COUNT(*) FROM evento WHERE url='u1'").fetchone()[0] == 0
    conn.close()


def test_manutencao_nao_poda_inativo_recente(banco):
    from datetime import date, timedelta
    banco.salvar_execucao([_item()], fontes_confiaveis={"Zap"})
    recente = (date.today() - timedelta(days=10)).isoformat()
    conn = banco.conectar()
    conn.execute("UPDATE imoveis SET status=?, ultima_confirmacao=? WHERE url='u1'",
                 (banco.INATIVO, recente))
    conn.commit(); conn.close()
    assert banco.manutencao()["podados"] == 0
