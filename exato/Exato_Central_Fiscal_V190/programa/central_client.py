import base64
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

_SESSION_TOKEN = ''
_LAST_ERROR = ''


def _ecf():
    import exato_central_fiscal as ecf
    return ecf


def _now():
    return datetime.now().isoformat(timespec='seconds')


def get_settings():
    ecf = _ecf()
    cfg = ecf.load_config() or {}
    raw = cfg.get('central_sync') if isinstance(cfg, dict) else None
    if not isinstance(raw, dict):
        raw = {}
    device_id = str(raw.get('device_id') or '').strip()
    if not device_id:
        device_id = str(uuid.uuid4())
        raw['device_id'] = device_id
        cfg['central_sync'] = raw
        try:
            ecf.save_config(cfg)
        except Exception:
            pass
    return {
        'enabled': bool(raw.get('enabled', False)),
        'role': str(raw.get('role') or 'local').strip().lower(),
        'server_url': str(raw.get('server_url') or '').strip().rstrip('/'),
        'token': str(raw.get('token') or '').strip(),
        'device_id': device_id,
        'last_pull_at': str(raw.get('last_pull_at') or '').strip(),
        'last_sync_at': str(raw.get('last_sync_at') or '').strip(),
        'last_sync_message': str(raw.get('last_sync_message') or '').strip(),
        'server_autostart': bool(raw.get('server_autostart', True)),
        'server_autostart_registered': bool(raw.get('server_autostart_registered', False)),
    }


def save_settings(**changes):
    ecf = _ecf()
    cfg = ecf.load_config() or {}
    raw = cfg.get('central_sync') if isinstance(cfg, dict) else None
    if not isinstance(raw, dict):
        raw = {}
    current = get_settings()
    raw.update(changes)
    raw.setdefault('device_id', current['device_id'])
    cfg['central_sync'] = raw
    ecf.save_config(cfg)
    return get_settings()


def is_client_enabled():
    s = get_settings()
    return bool(s['enabled'] and s['role'] == 'client' and s['server_url'] and s['token'])


def is_server_configured():
    s = get_settings()
    return bool(s['enabled'] and s['role'] == 'server')


def session_token():
    return _SESSION_TOKEN


def set_session_token(token):
    global _SESSION_TOKEN
    _SESSION_TOKEN = str(token or '').strip()


def clear_session():
    global _SESSION_TOKEN
    _SESSION_TOKEN = ''


def local_ipv4_candidates():
    out = []
    try:
        host = socket.gethostname()
        for item in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = item[4][0]
            if ip.startswith('127.'):
                continue
            if ip not in out:
                out.append(ip)
    except Exception:
        pass
    if not out:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
            sock.close()
            if ip and not ip.startswith('127.'):
                out.append(ip)
        except Exception:
            pass
    return out


def make_connection_text(port=8765):
    s = get_settings()
    urls = [f'http://{ip}:{port}' for ip in local_ipv4_candidates()]
    if not urls:
        urls = [f'http://127.0.0.1:{port}']
    lines = [
        'EXATO CENTRAL FISCAL — CONEXÃO COM A CENTRAL COMPARTILHADA',
        '',
        'Copie este arquivo para o outro computador e use a opção',
        'CONFIGURAR CENTRAL → IMPORTAR ARQUIVO DE CONEXÃO.',
        '',
        f'Servidor: {socket.gethostname()}',
        f'Porta: {port}',
        'URLs disponíveis:',
        *[f'  {u}' for u in urls],
        '',
        f'Token de conexão: {s["token"]}',
        '',
        'IMPORTANTE: este token permite acesso à Central pela rede local.',
        'Não publique nem envie este arquivo para pessoas não autorizadas.',
        '',
    ]
    return '\n'.join(lines), urls


def write_connection_file(port=8765):
    ecf = _ecf(); ecf.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    text, urls = make_connection_text(port=port)
    path = ecf.APP_DATA_DIR / 'EXATO_CENTRAL_CONEXAO.txt'
    path.write_text(text, encoding='utf-8')
    return path, urls


def parse_connection_file(path):
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    token = ''
    urls = []
    for line in text.splitlines():
        stripped = line.strip()
        low = stripped.casefold()
        if low.startswith('token de conexão:'):
            token = stripped.split(':', 1)[1].strip()
        elif stripped.startswith('http://') or stripped.startswith('https://'):
            urls.append(stripped)
    if not urls or not token:
        raise ValueError('Arquivo de conexão inválido: URL e token não encontrados.')
    return {'server_url': urls[0].rstrip('/'), 'token': token}


def _request(path, method='GET', payload=None, require_session=False, timeout=5, server_url=None, token=None):
    global _LAST_ERROR
    s = get_settings()
    base = str(server_url or s['server_url']).rstrip('/')
    tok = str(token if token is not None else s['token'])
    if not base:
        raise RuntimeError('A Central compartilhada não está configurada.')
    url = base + path
    headers = {'Accept': 'application/json', 'User-Agent': f'Exato-Central-Fiscal/{getattr(_ecf(), "APP_VERSION", "V140")}'}
    if tok:
        headers['X-Exato-Token'] = tok
    if require_session and _SESSION_TOKEN:
        headers['X-Exato-Session'] = _SESSION_TOKEN
    body = None
    if payload is not None and method.upper() == 'GET':
        url += ('&' if '?' in url else '?') + urlencode(payload)
    elif payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8', errors='replace'))
        _LAST_ERROR = ''
        return result
    except HTTPError as exc:
        try:
            detail = exc.read().decode('utf-8', errors='replace')
            obj = json.loads(detail) if detail else {}
            msg = obj.get('error') or obj.get('message') or f'HTTP {exc.code}'
        except Exception:
            msg = f'HTTP {exc.code}'
        _LAST_ERROR = msg
        raise RuntimeError(msg)
    except URLError as exc:
        _LAST_ERROR = f'Central indisponível: {exc.reason}'
        raise RuntimeError(_LAST_ERROR)
    except Exception as exc:
        _LAST_ERROR = str(exc)
        raise RuntimeError(str(exc))


def test_connection(server_url=None, token=None):
    return _request('/api/v140/health', 'GET', timeout=3, server_url=server_url, token=token)

def _server_start_command(port=8765):
    """Build the Windows per-user startup command without opening a console."""
    ecf = _ecf()
    executable = Path(sys.executable).resolve()
    if os.name == 'nt' and executable.name.casefold() == 'python.exe':
        pythonw = executable.with_name('pythonw.exe')
        if pythonw.exists():
            executable = pythonw
    if getattr(ecf, 'FROZEN_EXECUTABLE', False):
        args = [str(executable), '--central-server', '--central-port', str(int(port))]
    else:
        args = [str(executable), str(Path(ecf.__file__).resolve()), '--central-server', '--central-port', str(int(port))]
    return subprocess.list2cmdline(args)


def configure_windows_server_autostart(enabled=True, port=8765):
    """Register/remove the Exato Central Server in the current Windows user Run key."""
    if os.name != 'nt':
        return False
    try:
        import winreg
        path = r'Software\\Microsoft\\Windows\\CurrentVersion\\Run'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
            value_name = 'Exato Central Fiscal Server'
            if enabled:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, _server_start_command(port))
            else:
                try:
                    winreg.DeleteValue(key, value_name)
                except FileNotFoundError:
                    pass
        save_settings(server_autostart=bool(enabled), server_autostart_registered=bool(enabled))
        return True
    except Exception as exc:
        global _LAST_ERROR
        _LAST_ERROR = str(exc)
        try:
            save_settings(server_autostart_registered=False)
        except Exception:
            pass
        return False


def windows_server_autostart_status():
    """Return the current per-user Windows startup registration state."""
    if os.name != 'nt':
        return {'supported': False, 'registered': False, 'detail': 'Inicialização automática do servidor é específica do Windows.'}
    try:
        import winreg
        path = r'Software\\Microsoft\\Windows\\CurrentVersion\\Run'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_QUERY_VALUE) as key:
            value, _ = winreg.QueryValueEx(key, 'Exato Central Fiscal Server')
        return {'supported': True, 'registered': bool(str(value or '').strip()), 'detail': str(value or '')}
    except FileNotFoundError:
        return {'supported': True, 'registered': False, 'detail': 'Não registrado no Windows.'}
    except Exception as exc:
        return {'supported': True, 'registered': False, 'detail': str(exc)}


def _local_outbox_counts():
    try:
        ecf = _ecf(); _ensure_local_sync_schema()
        conn = sqlite3.connect(ecf.DB_PATH, timeout=10)
        counts = {
            'documents': int(conn.execute('SELECT COUNT(*) FROM central_outbox_documents').fetchone()[0] or 0),
            'companies': int(conn.execute('SELECT COUNT(*) FROM central_outbox_companies').fetchone()[0] or 0),
            'exports': int(conn.execute('SELECT COUNT(*) FROM central_outbox_exports').fetchone()[0] or 0),
        }
        conn.close()
        counts['total'] = sum(counts.values())
        return counts
    except Exception:
        return {'documents': 0, 'companies': 0, 'exports': 0, 'total': 0}


def local_central_health():
    """Build a lightweight operational snapshot without changing fiscal state."""
    ecf = _ecf(); s = get_settings()
    pending = _local_outbox_counts()
    result = {
        'ok': True,
        'role': s['role'],
        'enabled': s['enabled'],
        'state': 'local' if not s['enabled'] else ('server' if s['role'] == 'server' else 'offline'),
        'label': 'Central local' if not s['enabled'] else ('Servidor Exato' if s['role'] == 'server' else 'Central indisponível'),
        'detail': 'Sincronização compartilhada desativada.' if not s['enabled'] else '',
        'last_sync_at': s.get('last_sync_at') or '',
        'last_sync_message': s.get('last_sync_message') or '',
        'pending': pending,
        'server_autostart': windows_server_autostart_status(),
    }
    if s['role'] == 'server' and s['enabled']:
        result.update({
            'server_url': '',
            'server_reachable': _local_server_reachable(8765),
        })
        try:
            health = _request('/api/v140/health', 'GET', timeout=1.5, server_url='http://127.0.0.1:8765', token=s['token'])
            result.update(health)
            result['state'] = 'online' if health.get('ok') else 'offline'
            result['label'] = 'Servidor Exato online' if health.get('ok') else 'Servidor Exato indisponível'
        except Exception as exc:
            result['state'] = 'offline'
            result['label'] = 'Servidor Exato indisponível'
            result['detail'] = str(exc)
        return result
    if not s['enabled'] or s['role'] != 'client':
        return result
    if not s['server_url'] or not s['token']:
        result['detail'] = 'Cliente sem endereço/token configurados.'
        return result
    try:
        health = test_connection(s['server_url'], s['token'])
        result.update(health)
        result['state'] = 'online' if health.get('ok') else 'offline'
        result['label'] = 'Central online' if health.get('ok') else 'Central indisponível'
        result['detail'] = str(health.get('server_name') or s['server_url'])
    except Exception as exc:
        result['state'] = 'offline'
        result['label'] = 'Central indisponível'
        result['detail'] = str(exc)
    return result


def _local_server_reachable(port=8765):
    try:
        sock = socket.create_connection(('127.0.0.1', int(port)), timeout=0.35)
        sock.close(); return True
    except Exception:
        return False


def remote_login(email, password):
    result = _request('/api/v140/auth/login', 'POST', {'email': email, 'password': password}, timeout=8)
    token = str(result.get('session_token') or '')
    if not token:
        raise RuntimeError('A Central não retornou uma sessão válida.')
    set_session_token(token)
    return result.get('user') or {}


def remote_get_user(email):
    return (_request('/api/v140/auth/user', 'GET', {'email': email}, timeout=5).get('user'))


def remote_get_user_by_id(user_id):
    return (_request('/api/v140/auth/user_by_id', 'GET', {'id': int(user_id)}, timeout=5).get('user'))


def remote_register_user(name, email, password):
    return (_request('/api/v140/auth/register', 'POST', {'name': name, 'email': email, 'password': password}, timeout=8).get('user') or {})


def remote_set_password(user_id, password):
    return (_request('/api/v140/auth/set_password', 'POST', {'user_id': int(user_id), 'password': password}, require_session=True, timeout=8).get('user') or {})


def remote_list_users():
    return list((_request('/api/v140/auth/users', 'GET', require_session=True, timeout=5).get('users') or []))


def remote_set_status(user_id, status):
    return bool(_request('/api/v140/auth/status', 'POST', {'user_id': int(user_id), 'status': status}, require_session=True, timeout=5).get('changed'))


def remote_request_password_reset(email):
    return bool(_request('/api/v140/auth/reset_request', 'POST', {'email': email}, timeout=8).get('accepted'))


def remote_list_reset_requests(pending_only=True, limit=100):
    return list((_request('/api/v140/auth/reset_requests', 'GET', {'pending_only': 1 if pending_only else 0, 'limit': int(limit)}, require_session=True, timeout=5).get('requests') or []))


def remote_pending_reset_count():
    return int(_request('/api/v140/auth/reset_count', 'GET', require_session=True, timeout=5).get('count') or 0)


def remote_resolve_reset(request_id, status='resolved'):
    return bool(_request('/api/v140/auth/reset_resolve', 'POST', {'request_id': int(request_id), 'status': status}, require_session=True, timeout=5).get('changed'))


def remote_activity(limit=120):
    return list((_request('/api/v140/auth/activity', 'GET', {'limit': int(limit)}, require_session=True, timeout=5).get('activity') or []))


def remote_log(user, action, details=''):
    return bool(_request('/api/v140/auth/log', 'POST', {'action': action, 'details': details}, require_session=True, timeout=5).get('ok'))


def remote_import_local_users():
    ecf = _ecf(); users = []
    try:
        conn = ecf._auth_connect(); conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT id,name,email,password_hash,password_salt,password_iterations,role,status,must_set_password,created_at,updated_at,last_login_at FROM users WHERE password_hash<>\'\' ORDER BY id').fetchall()
        conn.close()
        users = [dict(row) for row in rows]
    except Exception:
        return 0
    if not users:
        return 0
    return int(_request('/api/v140/auth/import_users', 'POST', {'users': users}, timeout=10).get('imported') or 0)


def _next_central_stamp(conn):
    now = datetime.now().isoformat(timespec='microseconds')
    latest = ''
    for table in ('companies', 'documents', 'document_exports'):
        try:
            row = conn.execute(f'SELECT MAX(central_updated_at) FROM {table}').fetchone()
            value = str(row[0] or '') if row else ''
            if value and value > latest:
                latest = value
        except Exception:
            pass
    if latest and now <= latest:
        try:
            now = (datetime.fromisoformat(latest) + timedelta(microseconds=1)).isoformat(timespec='microseconds')
        except Exception:
            pass
    return now


class _Carimbo:
    """V172: carimbos da Central em sequência. O primeiro vem de `_next_central_stamp` (3 consultas); os seguintes são só +1 microssegundo.
    Antes cada documento marcado refazia essas consultas (varrendo o arquivo fiscal inteiro) com o banco travado para escrita: foi a causa do
    "database is locked" ao buscar."""
    def __init__(self, conn):
        self.ultimo = _next_central_stamp(conn); self._primeiro = True
    def proximo(self):
        if self._primeiro:
            self._primeiro = False; return self.ultimo
        try: self.ultimo = (datetime.fromisoformat(self.ultimo) + timedelta(microseconds=1)).isoformat(timespec='microseconds')
        except Exception: pass
        return self.ultimo


_SCHEMA_PRONTO = set()          # bancos cujo esquema da Central já foi conferido neste programa (não regrava a cada chamada)


def _ensure_local_sync_schema(forcar=False):
    ecf = _ecf()
    if not forcar and str(ecf.DB_PATH) in _SCHEMA_PRONTO: return
    ecf.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ecf.DB_PATH, timeout=30)
    conn.execute('PRAGMA busy_timeout=10000')
    for table in ('companies', 'documents', 'document_exports'):
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}
        if 'central_updated_at' not in cols:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN central_updated_at TEXT')
    conn.execute('''CREATE TABLE IF NOT EXISTS central_sync_state (
        id INTEGER PRIMARY KEY CHECK(id=1), device_id TEXT NOT NULL,
        last_pull_at TEXT NOT NULL DEFAULT '', last_sync_at TEXT NOT NULL DEFAULT '',
        last_error TEXT NOT NULL DEFAULT ''
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS central_outbox_documents (
        doc_id TEXT PRIMARY KEY, changed_at TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS central_outbox_exports (
        doc_id TEXT NOT NULL, destination_root TEXT NOT NULL, changed_at TEXT NOT NULL,
        PRIMARY KEY(doc_id,destination_root)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS central_outbox_companies (
        cnpj TEXT PRIMARY KEY, changed_at TEXT NOT NULL
    )''')
    cols_estado = {r[1] for r in conn.execute('PRAGMA table_info(central_sync_state)').fetchall()}
    if 'semeado' not in cols_estado:
        conn.execute('ALTER TABLE central_sync_state ADD COLUMN semeado INTEGER NOT NULL DEFAULT 0')
        # instalação que já sincronizou antes: o arquivo já foi publicado, não precisa semear de novo
        conn.execute("UPDATE central_sync_state SET semeado=1 WHERE COALESCE(last_sync_at,'')<>''")
    device_id = get_settings()['device_id']
    conn.execute("INSERT INTO central_sync_state(id,device_id) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET device_id=excluded.device_id", (device_id,))
    for _t in ('companies', 'documents', 'document_exports'):          # carimbo da Central indexado: o maior valor sai na hora (sem varrer a tabela)
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{_t}_central ON {_t}(central_updated_at)')
    # Semeia o arquivo atual UMA ÚNICA vez (antes: sempre que a fila ficava vazia, o que recolocava TODOS os documentos na fila de envio a cada ciclo)
    semeado = int((conn.execute('SELECT semeado FROM central_sync_state WHERE id=1').fetchone() or [0])[0] or 0)
    counts = [int(conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] or 0) for t in ('central_outbox_documents','central_outbox_companies','central_outbox_exports')]
    if not semeado and sum(counts) == 0:
        now = _now()
        conn.execute("INSERT OR IGNORE INTO central_outbox_documents(doc_id,changed_at) SELECT doc_id,COALESCE(last_seen_at,?) FROM documents", (now,))
        conn.execute("INSERT OR IGNORE INTO central_outbox_companies(cnpj,changed_at) SELECT cnpj,COALESCE(last_sync_at,?) FROM companies", (now,))
        conn.execute("INSERT OR IGNORE INTO central_outbox_exports(doc_id,destination_root,changed_at) SELECT doc_id,destination_root,COALESCE(exported_at,?) FROM document_exports", (now,))
    if not semeado:
        conn.execute('UPDATE central_sync_state SET semeado=1 WHERE id=1')
    conn.commit(); conn.close()
    _SCHEMA_PRONTO.add(str(ecf.DB_PATH))


def prepare_local_schema():
    try: _ensure_local_sync_schema(forcar=True)          # ao abrir o programa (ou depois de restaurar o banco): confere de verdade
    except Exception: pass


def mark_documents_dirty(doc_ids, cnpj=''):
    if not doc_ids and not cnpj: return
    try:
        _ensure_local_sync_schema(); ecf=_ecf(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30); now=_now(); s=get_settings(); server_role=bool(s['enabled'] and s['role']=='server')
        carimbo=_Carimbo(conn) if server_role else None; feitos=0
        for doc_id in doc_ids or []:
            if not doc_id: continue
            conn.execute('INSERT INTO central_outbox_documents(doc_id,changed_at) VALUES(?,?) ON CONFLICT(doc_id) DO UPDATE SET changed_at=excluded.changed_at',(str(doc_id),now))
            if server_role:
                conn.execute('UPDATE documents SET central_updated_at=? WHERE doc_id=?',(carimbo.proximo(),str(doc_id)))
            feitos+=1
            if feitos%200==0: conn.commit()          # lotes curtos: o banco não fica travado para a busca e para as telas
        if cnpj:
            digits=''.join(ch for ch in str(cnpj) if ch.isdigit())
            if digits:
                conn.execute('INSERT INTO central_outbox_companies(cnpj,changed_at) VALUES(?,?) ON CONFLICT(cnpj) DO UPDATE SET changed_at=excluded.changed_at',(digits,now))
                if server_role:
                    conn.execute('UPDATE companies SET central_updated_at=? WHERE cnpj=?',((carimbo or _Carimbo(conn)).proximo(),digits))
        conn.commit(); conn.close()
    except Exception:
        pass


def mark_exports_dirty(exports):
    if not exports: return
    try:
        _ensure_local_sync_schema(); ecf=_ecf(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30); now=_now(); server_role=get_settings()['enabled'] and get_settings()['role']=='server'; carimbo=None
        for row in exports:
            doc_id=str(row.get('doc_id') or ''); root=str(row.get('destination_root') or '')
            if not doc_id or not root: continue
            conn.execute('INSERT INTO central_outbox_exports(doc_id,destination_root,changed_at) VALUES(?,?,?) ON CONFLICT(doc_id,destination_root) DO UPDATE SET changed_at=excluded.changed_at',(doc_id,root,now))
            if server_role:
                carimbo=carimbo or _Carimbo(conn)
                conn.execute('UPDATE document_exports SET central_updated_at=? WHERE doc_id=? AND destination_root=?',(carimbo.proximo(),doc_id,root))
        conn.commit(); conn.close()
    except Exception:
        pass


def _outbox(kind, limit=40):
    ecf=_ecf(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30); conn.row_factory=sqlite3.Row
    table={'documents':'central_outbox_documents','companies':'central_outbox_companies','exports':'central_outbox_exports'}[kind]
    order='changed_at'
    rows=conn.execute(f'SELECT * FROM {table} ORDER BY {order} LIMIT ?', (int(limit),)).fetchall(); conn.close(); return [dict(r) for r in rows]


def _build_push_batch(limit=35):
    ecf=_ecf(); prepare_local_schema(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30); conn.row_factory=sqlite3.Row
    companies=_outbox('companies',100); docs=_outbox('documents',limit); exports=_outbox('exports',100)
    payload={'device_id':get_settings()['device_id'],'companies':[],'documents':[],'exports':[]}
    for item in companies:
        row=conn.execute('SELECT cnpj,name,last_sync_at,created_at,central_updated_at FROM companies WHERE cnpj=?',(item['cnpj'],)).fetchone()
        if row: payload['companies'].append(dict(row))
    for item in docs:
        row=conn.execute('SELECT doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at,central_updated_at FROM documents WHERE doc_id=?',(item['doc_id'],)).fetchone()
        if not row: continue
        obj=dict(row); obj['xml_b64']=base64.b64encode(bytes(obj.pop('xml') or b'')).decode('ascii')
        obj['sources']=[dict(r) for r in conn.execute('SELECT actor_code,actor_label,source_nsu,first_seen_at,last_seen_at FROM document_sources WHERE cnpj=? AND doc_id=? ORDER BY actor_code',(obj['cnpj'],obj['doc_id'])).fetchall()]
        payload['documents'].append(obj)
    for item in exports:
        row=conn.execute('SELECT doc_id,destination_root,exported_path,exported_at,xml_sha256,central_updated_at FROM document_exports WHERE doc_id=? AND destination_root=?',(item['doc_id'],item['destination_root'])).fetchone()
        if row: payload['exports'].append(dict(row))
    conn.close(); return payload


def _ack(payload):
    """Acknowledge exactly the outbox batch that was read, even when a row vanished before push."""
    ecf=_ecf(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30)
    for item in payload.get('documents') or []:
        conn.execute('DELETE FROM central_outbox_documents WHERE doc_id=?',(str(item.get('doc_id') or ''),))
    for item in payload.get('companies') or []:
        conn.execute('DELETE FROM central_outbox_companies WHERE cnpj=?',(str(item.get('cnpj') or ''),))
    for item in payload.get('exports') or []:
        conn.execute('DELETE FROM central_outbox_exports WHERE doc_id=? AND destination_root=?',(str(item.get('doc_id') or ''),str(item.get('destination_root') or '')))
    conn.commit(); conn.close()


def _merge_pull(payload):
    ecf=_ecf(); prepare_local_schema(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30)
    for item in payload.get('companies') or []:
        conn.execute("INSERT INTO companies(cnpj,name,last_sync_at,created_at,central_updated_at) VALUES(?,?,?,?,?) ON CONFLICT(cnpj) DO UPDATE SET name=CASE WHEN excluded.name<>'' THEN excluded.name ELSE companies.name END,last_sync_at=excluded.last_sync_at,central_updated_at=excluded.central_updated_at",(str(item.get('cnpj') or ''),str(item.get('name') or ''),item.get('last_sync_at'),str(item.get('created_at') or _now()),item.get('central_updated_at') or _now()))
    for item in payload.get('documents') or []:
        try: xml=base64.b64decode(str(item.get('xml_b64') or ''),validate=False)
        except Exception: continue
        existing=conn.execute('SELECT doc_id FROM documents WHERE doc_id=?',(str(item.get('doc_id') or ''),)).fetchone()
        if existing:
            conn.execute('UPDATE documents SET source_nsu=?,last_seen_at=?,central_updated_at=? WHERE doc_id=?',(str(item.get('source_nsu') or ''),str(item.get('last_seen_at') or _now()),item.get('central_updated_at') or _now(),str(item.get('doc_id') or '')))
        else:
            conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at,central_updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(str(item.get('doc_id') or ''),str(item.get('cnpj') or ''),str(item.get('family') or ''),str(item.get('doc_type') or ''),str(item.get('direction') or ''),str(item.get('number') or ''),str(item.get('series') or ''),str(item.get('issued_at') or ''),str(item.get('value') or '0.00'),str(item.get('status') or 'Autorizado'),str(item.get('access_key') or ''),str(item.get('source_nsu') or ''),sqlite3.Binary(xml),str(item.get('first_seen_at') or _now()),str(item.get('last_seen_at') or _now()),item.get('central_updated_at') or _now()))
        for src in item.get('sources') or []:
            try:
                conn.execute("INSERT INTO document_sources(cnpj,doc_id,family,actor_code,actor_label,source_nsu,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(cnpj,doc_id,actor_code) DO UPDATE SET actor_label=excluded.actor_label,source_nsu=excluded.source_nsu,last_seen_at=excluded.last_seen_at",(str(item.get('cnpj') or ''),str(item.get('doc_id') or ''),str(item.get('family') or ''),str(src.get('actor_code') or ''),str(src.get('actor_label') or ''),str(src.get('source_nsu') or ''),str(src.get('first_seen_at') or _now()),str(src.get('last_seen_at') or _now())))
            except Exception: pass
    for item in payload.get('exports') or []:
        conn.execute("INSERT INTO document_exports(doc_id,destination_root,exported_path,exported_at,xml_sha256,central_updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(doc_id,destination_root) DO UPDATE SET exported_path=excluded.exported_path,exported_at=excluded.exported_at,xml_sha256=excluded.xml_sha256,central_updated_at=excluded.central_updated_at",(str(item.get('doc_id') or ''),str(item.get('destination_root') or ''),str(item.get('exported_path') or ''),str(item.get('exported_at') or _now()),str(item.get('xml_sha256') or ''),item.get('central_updated_at') or _now()))
    conn.commit(); conn.close()
    # V145: eventos de cancelamento recebidos da Central atualizam a situação das notas locais.
    if any(str(item.get('status') or '')=='Evento' for item in payload.get('documents') or []):
        try: ecf.db_apply_cancellation_events()
        except Exception: pass


def sync_now(max_seconds=18):
    if not is_client_enabled(): return {'ok':False,'skipped':True,'message':'Central compartilhada não configurada como cliente.'}
    start=time.time(); pushed=pulled=0; last_pull=get_settings().get('last_pull_at') or ''
    try:
        while time.time()-start<max_seconds:
            batch=_build_push_batch(35)
            if not (batch['companies'] or batch['documents'] or batch['exports']): break
            result=_request('/api/v140/sync/push','POST',batch,require_session=True,timeout=12); _ack(batch); pushed += int(result.get('received') or 0)
            if not result.get('has_more'): break
    except Exception as exc:
        save_settings(last_sync_message=f'Falha no envio: {exc}'); return {'ok':False,'pushed':pushed,'pulled':pulled,'message':str(exc)}
    try:
        while time.time()-start<max_seconds:
            result=_request('/api/v140/sync/pull','GET',{'since':last_pull,'limit':80},require_session=True,timeout=12)
            payload={'companies':result.get('companies') or [],'documents':result.get('documents') or [],'exports':result.get('exports') or []}
            if not (payload['companies'] or payload['documents'] or payload['exports']): break
            _merge_pull(payload); pulled += len(payload['companies'])+len(payload['documents'])+len(payload['exports'])
            new_since=str(result.get('next_since') or last_pull)
            if new_since==last_pull: break
            last_pull=new_since; save_settings(last_pull_at=last_pull)
            if not result.get('has_more'): break
    except Exception as exc:
        save_settings(last_sync_message=f'Falha na atualização: {exc}'); return {'ok':False,'pushed':pushed,'pulled':pulled,'message':str(exc)}
    now=_now(); save_settings(last_pull_at=last_pull,last_sync_at=now,last_sync_message=f'OK • envio {pushed} • recebimento {pulled}')
    try:
        ecf=_ecf(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30); conn.execute("UPDATE central_sync_state SET last_pull_at=?,last_sync_at=?,last_error='' WHERE id=1",(last_pull,now)); conn.commit(); conn.close()
    except Exception: pass
    return {'ok':True,'pushed':pushed,'pulled':pulled,'message':f'Central sincronizada • enviados {pushed} • recebidos {pulled}','last_pull_at':last_pull}


def central_status():
    s=get_settings()
    if not s['enabled']: return {'state':'local','label':'Central local','detail':'Sincronização compartilhada desativada.'}
    if s['role']=='server': return {'state':'server','label':'Servidor central','detail':f'Este computador hospeda a Central • {socket.gethostname()}'}
    if not s['server_url']: return {'state':'offline','label':'Central não configurada','detail':'Informe o endereço e o token do servidor.'}
    try:
        result=test_connection(); return {'state':'online','label':'Central conectada','detail':str(result.get('server_name') or s['server_url'])}
    except Exception as exc:
        return {'state':'offline','label':'Central indisponível','detail':str(exc)}


def ensure_server_configured(port=8765):
    s=get_settings(); token=s.get('token') or (uuid.uuid4().hex+uuid.uuid4().hex)
    save_settings(enabled=True,role='server',server_url='',token=token,server_autostart=True)
    configure_windows_server_autostart(True, port)
    return write_connection_file(port)


def ensure_server_running(port=8765):
    if not is_server_configured(): return False
    if get_settings().get('server_autostart', True):
        try: configure_windows_server_autostart(True, port)
        except Exception: pass
    try:
        sock=socket.create_connection(('127.0.0.1',int(port)),timeout=0.35); sock.close(); return True
    except Exception: pass
    ecf=_ecf(); script=Path(ecf.__file__).resolve(); args=[str(ecf.sys.executable),str(script),'--central-server','--central-port',str(int(port))]
    kwargs={'cwd':str(ecf.APP_DIR),'stdin':subprocess.DEVNULL,'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL,'start_new_session':True}
    if os.name=='nt': kwargs['creationflags']=getattr(subprocess,'DETACHED_PROCESS',0x00000008)|getattr(subprocess,'CREATE_NO_WINDOW',0x08000000)
    try: subprocess.Popen(args,**kwargs); time.sleep(0.5); return True
    except Exception as exc:
        global _LAST_ERROR; _LAST_ERROR=str(exc); return False


def configure_client(server_url, token):
    url=str(server_url or '').strip().rstrip('/'); tok=str(token or '').strip()
    if not (url.startswith('http://') or url.startswith('https://')): raise ValueError('Informe a URL da Central, por exemplo: http://192.168.0.10:8765')
    if not tok: raise ValueError('Informe o token de conexão da Central.')
    # Ao deixar de ser servidor, nunca mantenha a inicialização automática local registrada.
    try: configure_windows_server_autostart(False, 8765)
    except Exception: pass
    save_settings(enabled=True,role='client',server_url=url,token=tok,server_autostart=False,last_pull_at='',server_autostart_registered=False)
    result=test_connection(url,tok)
    if not result.get('ok',True): raise RuntimeError('A Central respondeu sem confirmação de saúde.')
    return result


def disable_central():
    try: configure_windows_server_autostart(False, 8765)
    except Exception: pass
    clear_session(); save_settings(enabled=False,role='local',server_url='',token='',server_autostart=False,server_autostart_registered=False)
