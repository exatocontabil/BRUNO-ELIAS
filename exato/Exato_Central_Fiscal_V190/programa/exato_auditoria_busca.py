"""V185: da Auditoria para a busca. Quando o SAT tem a nota e a Central não tem o XML, o Exato procura SÓ a faixa de notas em volta das que faltam
(não o período inteiro). Sem Tkinter; só lê o banco."""
import re
import sqlite3
from datetime import datetime, timedelta

MARGEM_DIAS = 3          # a nota atrasada entra na distribuição depois das vizinhas: olha 3 dias para cada lado
NOMES = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e'}


def _digitos(x):
    return re.sub(r'\D', '', str(x or ''))


def familia_da_linha(row, padrao=''):
    """'nfe' | 'nfce' | '' a partir da coluna Modelo da linha da auditoria (ou do tipo auditado)."""
    modelo = str(row.get('modelo') or '').upper().replace(' ', '')
    if 'NFC' in modelo or modelo.endswith('65'): return 'nfce'
    if 'NF-E' in modelo or modelo.endswith('55'): return 'nfe'
    return padrao if padrao in NOMES else ''


def faltantes(display_rows, padrao=''):
    """Linhas do SAT sem XML na Central (não cancelada, com data). Cada item: dict com familia, ator, data, chave, numero."""
    saida = []
    for r in display_rows or []:
        if str(r.get('display_status') or '') != 'Sem correspondência': continue
        if str(r.get('situacao_doc') or 'Autorizada') == 'Cancelada': continue
        fam = familia_da_linha(r, padrao)
        data = str(r.get('data') or '')[:10]
        if not fam or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', data): continue
        direc = str(r.get('direction') or '').strip().lower()
        ator = '' if fam != 'nfe' else ('1' if direc.startswith('s') else '2' if direc.startswith('e') else '')
        saida.append({'familia': fam, 'ator': ator, 'data': data, 'chave': _digitos(r.get('chave')), 'numero': str(r.get('numero') or '')})
    return saida


def agrupar(lista):
    """{(familia, ator): [itens]}; NF-e sem sentido conhecido vira dois grupos (saída e entrada) — a busca confere os dois."""
    grupos = {}
    for it in lista:
        atores = [it['ator']] if it['ator'] or it['familia'] != 'nfe' else ['1', '2']
        for a in atores:
            grupos.setdefault((it['familia'], a), []).append(it)
    return grupos


def texto_resumo(lista):
    """Ex.: '12 NFC-e e 3 NF-e'."""
    cont = {}
    for it in lista: cont[it['familia']] = cont.get(it['familia'], 0) + 1
    partes = [f'{n} {NOMES.get(f, f)}' for f, n in sorted(cont.items())]
    return ' e '.join(partes)


def janela(db_path, cnpj, familia, ator, itens, margem=MARGEM_DIAS):
    """Faixa de busca por NSU em volta das notas que faltam: {'inicio': NSU, 'fim': NSU|None, 'de': data, 'ate': data}.
    início = maior NSU entre as notas JÁ guardadas (do mesmo tipo e sentido) emitidas antes de (primeira que falta - margem); 0 se não houver.
    fim = menor NSU entre as guardadas emitidas depois de (última que falta + margem); None = vai até o fim da distribuição."""
    datas = sorted(i['data'] for i in itens)
    de, ate = datas[0], datas[-1]
    antes = (datetime.strptime(de, '%Y-%m-%d') - timedelta(days=margem)).strftime('%Y-%m-%d')
    depois = (datetime.strptime(ate, '%Y-%m-%d') + timedelta(days=margem + 1)).strftime('%Y-%m-%d')
    cnpj = _digitos(cnpj); inicio = 0; fim = None
    sentido = {'1': 'Saída', '2': 'Entrada'}.get(ator, '')          # NF-e: cada fluxo (emitente/destinatário) tem a sua numeração; NFC-e tem uma só
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        base = ("SELECT {agg}(CAST(source_nsu AS INTEGER)) FROM documents WHERE cnpj=? AND family=? AND source_nsu<>'' AND status<>'Evento' AND issued_at{op}?"
                + (" AND direction=?" if sentido else ""))
        extra = (sentido,) if sentido else ()
        r = conn.execute(base.format(agg='MAX', op='<'), (cnpj, familia, antes) + extra).fetchone()
        if r and r[0]: inicio = int(r[0])
        r = conn.execute(base.format(agg='MIN', op='>='), (cnpj, familia, depois) + extra).fetchone()
        if r and r[0]: fim = int(r[0])
    finally:
        conn.close()
    if fim is not None and fim <= inicio: fim = None
    return {'inicio': inicio, 'fim': fim, 'de': de, 'ate': ate}


def ainda_sem_xml(db_path, cnpj, itens):
    """Itens cuja chave continua sem XML guardado para a empresa (depois da busca dirigida)."""
    cnpj = _digitos(cnpj); chaves = [i['chave'] for i in itens if len(i['chave']) == 44]
    if not chaves: return list(itens)
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        achadas = set()
        for k in range(0, len(chaves), 400):
            lote = chaves[k:k + 400]
            achadas.update(r[0] for r in conn.execute(
                f"SELECT access_key FROM documents WHERE cnpj=? AND status<>'Evento' AND access_key IN ({','.join('?' * len(lote))})", [cnpj] + lote))
    finally:
        conn.close()
    return [i for i in itens if i['chave'] not in achadas]
