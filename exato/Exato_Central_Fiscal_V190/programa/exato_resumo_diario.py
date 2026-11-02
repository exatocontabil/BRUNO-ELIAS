"""Resumo diário por e-mail (V182). Sem Tkinter.

Uma vez por dia, de manhã, o Exato manda um e-mail com uma linha por empresa: o que está em dia, o que atrasou, notas canceladas sem o XML do cancelamento
e numeração faltando. Usa o e-mail já configurado no Box-e. Só um computador envia por dia (marca atômica na pasta do servidor).
"""
from __future__ import annotations
import json, os, re, socket
from datetime import date, datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path

import exato_numeracao as numeracao
import exato_situacao_busca as situacao
import exato_repositorio as repo

SUBPASTA = 'Resumo diario'
HORA_MINIMA = 7


def montar(db_path, config, indice_repo=None, hoje=None, canceladas_sem_evento=None, **extra):
    """Devolve {'assunto','texto','html','empresas': [...], 'pendencias': n}. `canceladas_sem_evento(cnpj) -> n` e `conectar_db()` vêm do programa."""
    import sqlite3
    hoje = hoje or date.today(); linhas = situacao.linhas(db_path, config, indice_repo, hoje=hoje, **extra); itens = []; pend = 0
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        mes_ini = hoje.replace(day=1).isoformat()
        for l in linhas:
            falta = []
            for fam in ('nfe', 'nfce'):
                rows = conn.execute("SELECT series, number FROM documents WHERE cnpj=? AND family=? AND direction='Saída' AND COALESCE(status,'')<>'Evento' AND substr(issued_at,1,10)>=?",
                                    (l['cnpj'], fam, mes_ini)).fetchall()
                for serie, faixas in numeracao.lacunas([{'serie': a, 'numero': b} for a, b in rows]).items():
                    falta.append(f"{fam.upper().replace('NFE', 'NF-e').replace('NFCE', 'NFC-e')} série {serie}: {numeracao.texto_faixas(faixas, 6)}")
            try: sem_evento = int(canceladas_sem_evento(l['cnpj'])) if canceladas_sem_evento else 0
            except Exception: sem_evento = 0
            estado = {'em_dia': 'em dia', 'atraso': 'atrasada', 'nunca': 'ainda não buscada'}.get(l['resumo'], l['resumo'])
            problemas = []
            if l['resumo'] != 'em_dia': problemas.append(estado)
            if sem_evento: problemas.append(f'{sem_evento} cancelada(s) sem o XML do cancelamento')
            problemas += [f'numeração faltando ({x})' for x in falta]
            pend += 1 if problemas else 0
            itens.append({'cnpj': l['cnpj'], 'nome': l['nome'], 'estado': estado, 'problemas': problemas})
    finally:
        conn.close()
    total = len(itens); ok = sum(1 for i in itens if not i['problemas'])
    assunto = f'Exato: resumo de {hoje.strftime("%d/%m/%Y")} — ' + ('tudo em dia' if not pend else f'{pend} empresa(s) para conferir')
    texto = [f'Resumo do Exato Central Fiscal — {hoje.strftime("%d/%m/%Y")}', f'{total} empresa(s): {ok} em dia, {pend} para conferir.', '']
    for i in sorted(itens, key=lambda x: (not x['problemas'], x['nome'].casefold())):
        texto.append(f"{'⚠' if i['problemas'] else '✓'} {i['nome']}: " + ('em dia' if not i['problemas'] else '; '.join(i['problemas'])))
    linhas_html = ''.join(f"<tr><td style='padding:4px 8px'>{'⚠' if i['problemas'] else '✓'}</td><td style='padding:4px 8px'><b>{escape(i['nome'])}</b></td>"
                          f"<td style='padding:4px 8px;color:{'#B91C1C' if i['problemas'] else '#15803D'}'>{escape('em dia' if not i['problemas'] else '; '.join(i['problemas']))}</td></tr>"
                          for i in sorted(itens, key=lambda x: (not x['problemas'], x['nome'].casefold())))
    html = (f"<p>Resumo do Exato Central Fiscal — {hoje.strftime('%d/%m/%Y')}<br>{total} empresa(s): {ok} em dia, {pend} para conferir.</p>"
            f"<table style='border-collapse:collapse;font-family:Segoe UI,Arial;font-size:13px'>{linhas_html}</table>")
    return {'assunto': assunto, 'texto': '\n'.join(texto), 'html': html, 'empresas': itens, 'pendencias': pend}


def _marca(base, dia):
    return repo._pasta_repo(base) / SUBPASTA / f'{dia}.json'


def reivindicar_dia(base, dia, computador=''):
    """Marca atômica: só o primeiro computador que chegar no dia envia. True = pode enviar."""
    if not repo.pasta_acessivel(base, 4): return False
    caminho = _marca(base, dia); os.makedirs(repo._longo(caminho.parent), exist_ok=True)
    try:
        fd = os.open(repo._longo(caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError:
        return False
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump({'por': computador or socket.gethostname(), 'em': datetime.now().isoformat(timespec='seconds')}, f)
    return True


def liberar_dia(base, dia):
    try: os.remove(repo._longo(_marca(base, dia)))
    except OSError: pass


def enviar(cfg_email, destino, resumo, conectar=None):
    """Manda o resumo (texto + HTML). `cfg_email`: a mesma configuração do Box-e (servidor, porta, usuário, senha, remetente). `conectar` injetável nos testes."""
    import exato_boxe as boxe
    msg = EmailMessage(); msg['From'] = cfg_email['remetente']; msg['To'] = destino; msg['Subject'] = resumo['assunto']
    msg.set_content(resumo['texto']); msg.add_alternative(resumo['html'], subtype='html')
    smtp = (conectar or boxe._conectar)(cfg_email)
    try: smtp.send_message(msg)
    finally:
        try: smtp.quit()
        except Exception: pass


def deve_enviar(config_resumo, agora=None):
    """Ligado, com destino, depois das 7h e ainda não enviado hoje (neste computador)."""
    agora = agora or datetime.now()
    return bool(config_resumo.get('ativo') and config_resumo.get('destino') and agora.hour >= HORA_MINIMA and config_resumo.get('ultimo') != agora.strftime('%Y-%m-%d'))
