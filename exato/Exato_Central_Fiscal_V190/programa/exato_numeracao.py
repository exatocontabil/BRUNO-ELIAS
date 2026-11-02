"""Numeração faltando nas NF-e e NFC-e de SAÍDA (V182). Sem Tkinter.

Para cada série, olha do menor ao maior número que a empresa emitiu e aponta os números que não existem no Exato (nem como nota autorizada, nem como
cancelada). Pode ser nota que nunca chegou, ou número inutilizado na SEFAZ (o Exato não recebe inutilização): por isso é um aviso para conferir.
"""
from __future__ import annotations
import re

MAX_FAIXA = 5000          # faixa maior que isso é resumida (provável troca de numeração, não nota perdida)


def _num(x):
    t = re.sub(r'\D', '', str(x or '')).lstrip('0')
    return int(t) if t else 0


def lacunas(linhas):
    """`linhas`: dicts com 'serie' e 'numero' (qualquer situação conta como existente). Devolve {serie: [(de, ate), ...]} só das séries com falta."""
    por_serie = {}
    for r in linhas or []:
        n = _num(r.get('numero'))
        if n: por_serie.setdefault(str(r.get('serie') or '').strip() or '—', set()).add(n)
    saida = {}
    for serie, nums in por_serie.items():
        ordem = sorted(nums); faixas = []
        for a, b in zip(ordem, ordem[1:]):
            if b - a > 1: faixas.append((a + 1, b - 1))
        if faixas: saida[serie] = faixas
    return saida


def texto_faixas(faixas, limite=40):
    """'120, 125–127, 130' (até `limite` faixas; o resto vira 'e mais N faixa(s)')."""
    partes = [str(a) if a == b else f'{a}–{b}' for a, b in faixas[:limite]]
    extra = len(faixas) - limite
    return ', '.join(partes) + (f' e mais {extra} faixa(s)' if extra > 0 else '')


def total_faltando(faixas):
    return sum(b - a + 1 for a, b in faixas)
