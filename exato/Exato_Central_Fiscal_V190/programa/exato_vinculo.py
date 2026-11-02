"""V188: cliente recém-vinculado ao contador na SEFAZ. A SEFAZ pode levar horas para liberar o download das notas; o Exato faz a primeira busca sozinho e
repete de hora em hora nos primeiros dias (sem tocar na tela, sem pedir nada). Sem Tkinter; só decide QUEM buscar agora."""
import re
import sqlite3
from datetime import datetime, timedelta

JANELA_DIAS = 3          # por quantos dias repetir
INTERVALO_H = 1          # de quanto em quanto tempo (a SEFAZ limita consultas seguidas)
GRUPO_XML = ('nfe', 'nfce', 'cte')


def _dig(x):
    return re.sub(r'\D', '', str(x or ''))


def _iso(texto):
    try: return datetime.fromisoformat(str(texto))
    except (TypeError, ValueError): return None


def _situacao(db_path):
    """[(cnpj, nome, criada_em, notas_xml, ultimo_codigo_xml)] por empresa."""
    saida = []
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        try:
            notas = {_dig(c): int(n) for c, n in conn.execute("SELECT cnpj, COUNT(*) FROM documents WHERE family IN ('nfe','nfce','cte') AND COALESCE(status,'')<>'Evento' GROUP BY cnpj")}
            try:
                cod = {}
                for cnpj, tipo, codigo, quando in conn.execute("SELECT cnpj,tipo,codigo,quando FROM busca_ocorrencias WHERE id IN (SELECT MAX(id) FROM busca_ocorrencias GROUP BY cnpj,tipo)"):
                    if tipo in GRUPO_XML: cod.setdefault(_dig(cnpj), []).append((str(quando), codigo))
            except sqlite3.Error:
                cod = {}
            for cnpj, nome, criada in conn.execute("SELECT cnpj, name, created_at FROM companies"):
                c = _dig(cnpj)
                if len(c) != 14: continue
                ult = sorted(cod.get(c, []))[-1][1] if cod.get(c) else ''
                saida.append((c, str(nome or ''), _iso(criada), notas.get(c, 0), ult, bool(cod.get(c))))
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return saida


def decidir(db_path, estado, agora=None, janela_dias=JANELA_DIAS, intervalo_h=INTERVALO_H):
    """(buscar, avisar): `buscar` = [cnpj, ...] (no máximo uma empresa por vez, a mais antiga na fila); `avisar` = [(cnpj, nome)] cuja janela acabou e continuam sem acesso
    (avisa uma vez só). `estado` é um dict que o chamador guarda na configuração: {cnpj: {'desde','ultima','tentativas','avisou'}}."""
    agora = agora or datetime.now(); buscar = []; avisar = []
    for cnpj, nome, criada, notas, ult, tem_oc in _situacao(db_path):
        recente = bool(criada) and agora - criada <= timedelta(days=janela_dias) and notas == 0
        pendente = ult == 'vinculo_pendente' and notas == 0
        acompanhada = bool((estado.get(cnpj) or {}).get('desde')) and notas == 0          # já estava na fila: segue até a janela acabar (e avisar)
        if not (recente or pendente or acompanhada): continue
        e = estado.setdefault(cnpj, {}); desde = _iso(e.get('desde')) or agora
        if not e.get('desde'): e['desde'] = desde.isoformat(timespec='seconds')
        if agora - desde > timedelta(days=janela_dias):
            if not e.get('avisou'): e['avisou'] = True; avisar.append((cnpj, nome))
            continue
        ultima = _iso(e.get('ultima'))
        if ultima and agora - ultima < timedelta(hours=intervalo_h): continue
        buscar.append(cnpj)
    return buscar[:1], avisar


def registrar_tentativa(estado, cnpj, agora=None):
    e = estado.setdefault(cnpj, {}); e['ultima'] = (agora or datetime.now()).isoformat(timespec='seconds'); e['tentativas'] = int(e.get('tentativas') or 0) + 1
