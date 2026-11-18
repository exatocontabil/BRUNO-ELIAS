"""Perguntas feitas ao Exatinho (para ensiná-lo): o que ele não soube responder e o que a pessoa marcou como "não ajudou". Fica em web.db, só para o administrador ler."""
import sqlite3, threading
from datetime import datetime

from . import config

_trava = threading.Lock()


def _con():
    c = sqlite3.connect(config.DADOS / 'web.db', timeout=15)
    c.execute("CREATE TABLE IF NOT EXISTS exatinho_perguntas(id INTEGER PRIMARY KEY AUTOINCREMENT, quando TEXT, usuario TEXT, pergunta TEXT, topico TEXT, resultado TEXT, util INTEGER)")
    return c


def registrar(usuario, pergunta, topico, resultado):
    with _trava:
        c = _con()
        try:
            cur = c.execute("INSERT INTO exatinho_perguntas(quando, usuario, pergunta, topico, resultado, util) VALUES(?,?,?,?,?,NULL)", (datetime.now().isoformat(timespec='seconds'), str(usuario)[:80], str(pergunta)[:400], str(topico)[:60], str(resultado)[:20]))
            c.commit(); return cur.lastrowid
        finally: c.close()


def feedback(id_, util):
    with _trava:
        c = _con()
        try: c.execute("UPDATE exatinho_perguntas SET util=? WHERE id=?", (1 if util else 0, int(id_))); c.commit()
        finally: c.close()


def para_ensinar(limite=200):
    """Perguntas que ele não soube responder ou que não ajudaram, da mais recente para a mais antiga."""
    with _trava:
        c = _con(); c.row_factory = sqlite3.Row
        try: return [dict(r) for r in c.execute("SELECT * FROM exatinho_perguntas WHERE resultado='desconhecido' OR util=0 ORDER BY id DESC LIMIT ?", (int(limite),))]
        finally: c.close()


def resumo():
    with _trava:
        c = _con()
        try: return {'total': c.execute("SELECT COUNT(*) FROM exatinho_perguntas").fetchone()[0], 'desconhecidas': c.execute("SELECT COUNT(*) FROM exatinho_perguntas WHERE resultado='desconhecido'").fetchone()[0],
                     'uteis': c.execute("SELECT COUNT(*) FROM exatinho_perguntas WHERE util=1").fetchone()[0], 'inuteis': c.execute("SELECT COUNT(*) FROM exatinho_perguntas WHERE util=0").fetchone()[0]}
        finally: c.close()
