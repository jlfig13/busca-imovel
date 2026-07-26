# -*- coding: utf-8 -*-
import os

import openpyxl
from openpyxl.styles import Font, PatternFill

import config
import db
from utils import log


def marcar_novos(itens: list[dict]) -> list[dict]:
    """Grava a execução no SQLite (db.py) e devolve os itens com o
    campo 'novo': True/False já preenchido."""
    return db.salvar_execucao(itens)


def gerar_excel(itens: list[dict]) -> str:
    os.makedirs(config.PASTA_SAIDA, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Apartamentos"

    colunas = ["Novo?", "Site", "Título", "Bairro", "Preço (R$)", "Quartos", "Área (m²)", "Visto 1ª vez em", "Link"]
    ws.append(colunas)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    fill_novo = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")

    # Novos primeiro, depois por preço crescente
    itens_ordenados = sorted(itens, key=lambda x: (not x.get("novo", False), x.get("preco") or 0))

    for item in itens_ordenados:
        row = [
            "SIM" if item.get("novo") else "",
            item.get("site", ""),
            item.get("titulo", ""),
            item.get("bairro", ""),
            item.get("preco", ""),
            item.get("quartos", ""),
            item.get("area_m2", ""),
            item.get("primeiro_visto", ""),
            item.get("url", ""),
        ]
        ws.append(row)
        if item.get("novo"):
            for cell in ws[ws.max_row]:
                cell.fill = fill_novo

    for col, largura in zip("ABCDEFGHI", [8, 20, 40, 18, 14, 10, 12, 16, 60]):
        ws.column_dimensions[col].width = largura

    wb.save(config.ARQUIVO_EXCEL)
    log.info(f"Excel salvo em {config.ARQUIVO_EXCEL}")
    return config.ARQUIVO_EXCEL
