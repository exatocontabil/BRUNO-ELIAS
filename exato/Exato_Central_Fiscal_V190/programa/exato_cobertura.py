"""Busca inteligente (V173): o que o Exato já sabe que buscou, para buscar só o que veio depois.

Sem Tkinter. Para cada empresa e tipo de documento (nfe, nfce, cte, nfse) responde "até que dia já temos as notas?" na ordem:
  1. o registro da última busca que terminou bem (config `busca_cobertura`);
  2. o próprio arquivo fiscal (banco): a última vez que o Web Service devolveu notas daquela empresa/tipo (`last_seen_at`);
  3. o Repositório no servidor (índice por empresa/mês), quando o banco deste computador está vazio (computador novo, banco restaurado).
Buscas por PERÍODO (portal da NFS-e) recomeçam alguns dias antes (margem de segurança: nota que chega atrasada). Buscas por NSU (Web Service,
Emissor Nacional por certificado) continuam do último NSU: nota atrasada ganha um NSU maior, então não perde nada e não precisam de margem.
"""
from __future__ import annotations
import calendar, re, sqlite3
from datetime import date, datetime, timedelta

MARGEM_DIAS = 3
FAMILIAS = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}
FONTES = {'busca': 'registro da última busca', 'banco': 'arquivo fiscal deste computador', 'repositorio': 'repositório no servidor'}


def _digitos(cnpj):
    return re.sub(r'\D', '', str(cnpj or ''))


def _data(texto):
    t = str(texto or '').strip()[:10]
    try: return datetime.strptime(t, '%Y-%m-%d').date()
    except ValueError: return None


def registrar(config, cnpj, familia, ate=None, nsu=None, agora=None):
    """Guarda que a busca de `familia` da empresa foi até `ate` (padrão: hoje). Não grava o arquivo de configuração (quem chama grava)."""
    d = _digitos(cnpj)
    if len(d) != 14 or familia not in FAMILIAS: return None
    ate = ate or (agora or datetime.now()).date()
    item = {'ate': ate.isoformat(), 'em': (agora or datetime.now()).isoformat(timespec='seconds')}
    if nsu not in (None, ''): item['nsu'] = int(nsu)
    config.setdefault('busca_cobertura', {}).setdefault(d, {})[familia] = item
    return item


def do_registro(config, cnpj, familia):
    item = ((config.get('busca_cobertura') or {}).get(_digitos(cnpj)) or {}).get(familia) or {}
    return _data(item.get('ate'))


def do_banco(db_path, cnpj, familia):
    """(até, quantidade, última nota) do arquivo fiscal: `até` = última vez que o Web Service devolveu documentos desse tipo."""
    d = _digitos(cnpj)
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        try:
            row = conn.execute("SELECT MAX(last_seen_at), COUNT(*), MAX(substr(issued_at,1,10)) FROM documents WHERE cnpj=? AND family=? AND status<>'Evento'", (d, familia)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None, 0, None
    if not row or not row[1]: return None, 0, None
    return _data(row[0]), int(row[1]), _data(row[2])


def do_repositorio(indice, cnpj):
    """(até, quantidade) pelo índice do Repositório: fim do último mês que tem arquivos no servidor para a empresa."""
    emp = ((indice or {}).get('empresas') or {}).get(_digitos(cnpj)) or {}
    meses = [(m, int(d.get('no_servidor') or 0)) for m, d in (emp.get('meses') or {}).items() if re.fullmatch(r'\d{4}-\d{2}', str(m)) and int(d.get('no_servidor') or 0) > 0]
    if not meses: return None, 0
    ultimo = max(m for m, _ in meses); ano, mes = int(ultimo[:4]), int(ultimo[5:])
    return date(ano, mes, calendar.monthrange(ano, mes)[1]), sum(n for _, n in meses)


def situacao(db_path, config, cnpj, familia, indice_repo=None, hoje=None, compartilhada=None):
    """{'ate': date|None, 'fonte': 'busca'|'banco'|'repositorio'|None, 'notas': n, 'ultima_nota': date|None, 'inicio': date|None}.
    `inicio` = onde uma busca por período deve recomeçar (até - margem). Nunca depois de hoje."""
    hoje = hoje or date.today()
    reg = do_registro(config, cnpj, familia)
    try:          # V178: o que OUTRO computador já buscou (arquivo compartilhado no servidor) também vale
        import exato_busca_compartilhada as comp
        outro = comp.cobertura_compartilhada(compartilhada, cnpj, familia) if compartilhada else None
    except Exception:
        outro = None
    if outro and (reg is None or outro > reg): reg = outro
    ate_b, notas, ultima = do_banco(db_path, cnpj, familia)
    ate = fonte = None
    if reg: ate, fonte = reg, 'busca'
    elif ate_b: ate, fonte = ate_b, 'banco'
    else:
        ate_r, notas_r = do_repositorio(indice_repo, cnpj)
        if ate_r: ate, fonte, notas = ate_r, 'repositorio', notas_r
    if ate and ate > hoje: ate = hoje
    return {'ate': ate, 'fonte': fonte, 'notas': notas, 'ultima_nota': ultima, 'inicio': (ate - timedelta(days=MARGEM_DIAS)) if ate else None}


def inicio_inteligente(info, quer_de=None, hoje=None):
    """Início da busca por período: o mais tardio entre o início pedido e `inicio` (cobertura - margem); sem cobertura, o pedido."""
    if not info or not info.get('inicio'): return quer_de
    if quer_de and quer_de >= info['inicio']: return quer_de
    return info['inicio']


def formatar(d):
    return d.strftime('%d/%m/%Y') if d else '—'


def aviso(info, familia, quer_de=None):
    """Texto claro (sem siglas) para avisar antes de uma busca que o arquivo já tem notas; '' se não há nada a avisar."""
    if not info or not info.get('ate'): return ''
    nome = FAMILIAS.get(familia, familia)
    fonte = {'busca': 'a última busca', 'banco': 'o arquivo fiscal deste computador', 'repositorio': 'o repositório no servidor'}.get(info.get('fonte'), '')
    notas = f" ({info['notas']:,} nota(s) de {nome})".replace(',', '.') if info.get('notas') else ''
    return f"Esta empresa já tem {nome} guardadas até {formatar(info['ate'])}{notas}, segundo {fonte}."


def precisa_avisar(info, quer_de, hoje=None):
    """Só vale avisar quando a busca pedida vai REPETIR o que já está guardado (início pedido bem antes da cobertura)."""
    if not info or not info.get('inicio'): return False
    if quer_de is None: return False
    return quer_de < info['inicio']
