import base64
import json
import secrets
import socket
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = '0.0.0.0'
PORT = 8765
SESSION_TTL_HOURS = 12
_SESSIONS = {}
_SESSIONS_LOCK = threading.RLock()


def _ecf():
    import exato_central_fiscal as ecf
    return ecf


def _now():
    return datetime.now().isoformat(timespec='seconds')


def _central_stamp(conn):
    now=datetime.now().isoformat(timespec='microseconds')
    latest=''
    for table in ('companies','documents','document_exports'):
        try:
            row=conn.execute(f'SELECT MAX(central_updated_at) FROM {table}').fetchone()
            val=str(row[0] or '') if row else ''
            if val and val>latest: latest=val
        except Exception: pass
    if latest and now<=latest:
        try: now=(datetime.fromisoformat(latest)+timedelta(microseconds=1)).isoformat(timespec='microseconds')
        except Exception: pass
    return now


def _json(handler, code, payload):
    raw=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type','application/json; charset=utf-8')
    handler.send_header('Content-Length',str(len(raw)))
    handler.send_header('Cache-Control','no-store')
    handler.end_headers(); handler.wfile.write(raw)


def _body(handler):
    length=int(handler.headers.get('Content-Length') or '0')
    if length>30*1024*1024: raise ValueError('Lote de sincronização muito grande.')
    return json.loads((handler.rfile.read(length) if length else b'{}').decode('utf-8',errors='replace'))


def _settings():
    from central_client import get_settings
    return get_settings()


def _token_ok(handler):
    expected=str(_settings().get('token') or '')
    supplied=str(handler.headers.get('X-Exato-Token') or '')
    return bool(expected and secrets.compare_digest(expected,supplied))


def _session_user(handler):
    token=str(handler.headers.get('X-Exato-Session') or '')
    if not token: return None
    with _SESSIONS_LOCK:
        item=_SESSIONS.get(token)
        if not item: return None
        if item['expires_at']<time.time():
            _SESSIONS.pop(token,None); return None
    return _ecf().db_auth_get_user_by_id(item['user_id'])


def _admin_user(handler):
    user=_session_user(handler)
    return user if _ecf()._auth_is_admin(user) else None


def _safe_user(user):
    if not user: return None
    ecf=_ecf(); row=dict(user)
    for key in ('password_hash','password_salt','password_iterations'):
        row.pop(key,None)
    row['password_configured']=bool(row.get('password_configured') or row.get('must_set_password')==0)
    row['role_label']=ecf.AUTH_ROLES.get(row.get('role'),row.get('role') or '')
    row['status_label']=ecf.AUTH_STATUSES.get(row.get('status'),row.get('status') or '')
    return row


def _issue_session(user):
    token=secrets.token_urlsafe(42)
    with _SESSIONS_LOCK:
        _SESSIONS[token]={'user_id':int(user['id']),'expires_at':time.time()+SESSION_TTL_HOURS*3600}
    return token


def _init_shared_columns():
    ecf=_ecf(); ecf.init_database(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30); conn.execute('PRAGMA busy_timeout=10000')
    for table in ('companies','documents','document_exports'):
        cols={r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}
        if 'central_updated_at' not in cols: conn.execute(f'ALTER TABLE {table} ADD COLUMN central_updated_at TEXT')
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_central ON {table}(central_updated_at)')          # V172: o maior carimbo sai na hora (antes varria a tabela a cada documento recebido)
    conn.commit(); conn.close()


def _backfill_central_timestamps():
    """Give legacy server-side records a deterministic first sync position.

    This runs only for rows that predate shared-central activation. Existing
    timestamps are never rewritten, so repeated starts are cheap and stable.
    """
    ecf=_ecf(); _init_shared_columns()
    conn=sqlite3.connect(ecf.DB_PATH,timeout=30); conn.execute('PRAGMA busy_timeout=10000')
    conn.execute('PRAGMA journal_mode=WAL')
    stamp=datetime.now().replace(microsecond=0)
    for table, columns, order_sql in (
        ('companies',('cnpj',),'cnpj'),
        ('documents',('doc_id',),'doc_id'),
        ('document_exports',('doc_id','destination_root'),'doc_id,destination_root'),
    ):
        select_cols=','.join(columns)
        rows=conn.execute(f"SELECT {select_cols} FROM {table} WHERE central_updated_at IS NULL ORDER BY {order_sql}").fetchall()
        for row in rows:
            stamp += timedelta(microseconds=1)
            value=stamp.isoformat(timespec='microseconds')
            if table=='companies':
                conn.execute('UPDATE companies SET central_updated_at=? WHERE cnpj=? AND central_updated_at IS NULL',(value,str(row[0])))
            elif table=='documents':
                conn.execute('UPDATE documents SET central_updated_at=? WHERE doc_id=? AND central_updated_at IS NULL',(value,str(row[0])))
            else:
                conn.execute('UPDATE document_exports SET central_updated_at=? WHERE doc_id=? AND destination_root=? AND central_updated_at IS NULL',(value,str(row[0]),str(row[1])))
    conn.commit(); conn.close()


def _push(payload):
    ecf=_ecf(); _init_shared_columns(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30); conn.row_factory=sqlite3.Row; conn.execute('PRAGMA busy_timeout=10000')
    received=changed=0
    try:
        for company in payload.get('companies') or []:
            cnpj=str(company.get('cnpj') or ''); name=str(company.get('name') or '')
            if not cnpj: continue
            existing=conn.execute('SELECT name,last_sync_at,created_at FROM companies WHERE cnpj=?',(cnpj,)).fetchone()
            incoming=(name,str(company.get('last_sync_at') or ''))
            if existing and (str(existing['name'] or ''),str(existing['last_sync_at'] or ''))==incoming:
                received+=1; continue
            conn.execute("INSERT INTO companies(cnpj,name,last_sync_at,created_at,central_updated_at) VALUES(?,?,?,?,?) ON CONFLICT(cnpj) DO UPDATE SET name=CASE WHEN excluded.name<>'' THEN excluded.name ELSE companies.name END,last_sync_at=excluded.last_sync_at,central_updated_at=excluded.central_updated_at",(cnpj,name,incoming[1],str(company.get('created_at') or _now()),_central_stamp(conn)))
            received+=1; changed+=1
        for doc in payload.get('documents') or []:
            doc_id=str(doc.get('doc_id') or '')
            if not doc_id: continue
            try: xml=base64.b64decode(str(doc.get('xml_b64') or ''),validate=False)
            except Exception: continue
            existing=conn.execute('SELECT xml,source_nsu,last_seen_at,central_updated_at FROM documents WHERE doc_id=?',(doc_id,)).fetchone()
            incoming_nsu=str(doc.get('source_nsu') or ''); incoming_seen=str(doc.get('last_seen_at') or '')
            if existing and bytes(existing['xml'] or b'')==xml and str(existing['source_nsu'] or '')==incoming_nsu and str(existing['last_seen_at'] or '')==incoming_seen:
                received+=1; continue
            if existing:
                if not xml: xml=bytes(existing['xml'] or b'')
                conn.execute('UPDATE documents SET source_nsu=?,last_seen_at=?,central_updated_at=? WHERE doc_id=?',(incoming_nsu,incoming_seen,_central_stamp(conn),doc_id))
            else:
                conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at,central_updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(doc_id,str(doc.get('cnpj') or ''),str(doc.get('family') or ''),str(doc.get('doc_type') or ''),str(doc.get('direction') or ''),str(doc.get('number') or ''),str(doc.get('series') or ''),str(doc.get('issued_at') or ''),str(doc.get('value') or '0.00'),str(doc.get('status') or 'Autorizado'),str(doc.get('access_key') or ''),incoming_nsu,sqlite3.Binary(xml),str(doc.get('first_seen_at') or _now()),incoming_seen or _now(),_central_stamp(conn)))
            for src in doc.get('sources') or []:
                try:
                    conn.execute("INSERT INTO document_sources(cnpj,doc_id,family,actor_code,actor_label,source_nsu,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(cnpj,doc_id,actor_code) DO UPDATE SET actor_label=excluded.actor_label,source_nsu=excluded.source_nsu,last_seen_at=excluded.last_seen_at",(str(doc.get('cnpj') or ''),doc_id,str(doc.get('family') or ''),str(src.get('actor_code') or ''),str(src.get('actor_label') or ''),str(src.get('source_nsu') or ''),str(src.get('first_seen_at') or _now()),str(src.get('last_seen_at') or _now())))
                except Exception: pass
            received+=1; changed+=1
        for ex in payload.get('exports') or []:
            doc_id=str(ex.get('doc_id') or ''); root=str(ex.get('destination_root') or '')
            if not doc_id or not root: continue
            existing=conn.execute('SELECT exported_path,exported_at,xml_sha256 FROM document_exports WHERE doc_id=? AND destination_root=?',(doc_id,root)).fetchone()
            incoming=(str(ex.get('exported_path') or ''),str(ex.get('exported_at') or ''),str(ex.get('xml_sha256') or ''))
            if existing and (str(existing['exported_path'] or ''),str(existing['exported_at'] or ''),str(existing['xml_sha256'] or ''))==incoming:
                received+=1; continue
            conn.execute("INSERT INTO document_exports(doc_id,destination_root,exported_path,exported_at,xml_sha256,central_updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(doc_id,destination_root) DO UPDATE SET exported_path=excluded.exported_path,exported_at=excluded.exported_at,xml_sha256=excluded.xml_sha256,central_updated_at=excluded.central_updated_at",(doc_id,root,incoming[0],incoming[1] or _now(),incoming[2],_central_stamp(conn)))
            received+=1; changed+=1
        conn.commit()
        # V145: eventos de cancelamento enviados por um cliente atualizam a situação das notas no servidor.
        if any(str(d.get('status') or '')=='Evento' for d in payload.get('documents') or []):
            conn.close(); conn=None
            try: ecf.db_apply_cancellation_events()
            except Exception: pass
        return {'ok':True,'received':received,'changed':changed,'has_more':False}
    finally:
        if conn is not None: conn.close()


def _pull(since='',limit=80):
    ecf=_ecf(); _init_shared_columns(); conn=sqlite3.connect(ecf.DB_PATH,timeout=30); conn.row_factory=sqlite3.Row
    since=str(since or ''); lim=max(1,min(int(limit or 80),200))
    rows=conn.execute("SELECT central_updated_at FROM documents WHERE central_updated_at IS NOT NULL AND central_updated_at>? UNION ALL SELECT central_updated_at FROM companies WHERE central_updated_at IS NOT NULL AND central_updated_at>? UNION ALL SELECT central_updated_at FROM document_exports WHERE central_updated_at IS NOT NULL AND central_updated_at>? ORDER BY central_updated_at LIMIT ?",(since,since,since,lim+1)).fetchall()
    stamps=[str(r[0]) for r in rows]; has_more=len(stamps)>lim
    cutoff=stamps[lim-1] if len(stamps)>=lim else (stamps[-1] if stamps else '')
    if not cutoff:
        conn.close(); return {'ok':True,'companies':[],'documents':[],'exports':[],'next_since':since,'has_more':False}
    where='central_updated_at>? AND central_updated_at<=?'; args=(since,cutoff)
    companies=[dict(r) for r in conn.execute(f'SELECT cnpj,name,last_sync_at,created_at,central_updated_at FROM companies WHERE {where} ORDER BY central_updated_at,cnpj',args).fetchall()]
    docs=[]
    for r in conn.execute(f'SELECT doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at,central_updated_at FROM documents WHERE {where} ORDER BY central_updated_at,doc_id',args).fetchall():
        item=dict(r); item['xml_b64']=base64.b64encode(bytes(item.pop('xml') or b'')).decode('ascii'); item['sources']=[dict(x) for x in conn.execute('SELECT actor_code,actor_label,source_nsu,first_seen_at,last_seen_at FROM document_sources WHERE cnpj=? AND doc_id=? ORDER BY actor_code',(item['cnpj'],item['doc_id'])).fetchall()]; docs.append(item)
    exports=[dict(r) for r in conn.execute(f'SELECT doc_id,destination_root,exported_path,exported_at,xml_sha256,central_updated_at FROM document_exports WHERE {where} ORDER BY central_updated_at,doc_id,destination_root',args).fetchall()]
    conn.close(); return {'ok':True,'companies':companies,'documents':docs,'exports':exports,'next_since':cutoff,'has_more':has_more}


class Handler(BaseHTTPRequestHandler):
    server_version='ExatoCentral/140'; sys_version=''
    def log_message(self,fmt,*args): return
    def _guard_token(self):
        if not _token_ok(self): _json(self,401,{'ok':False,'error':'Token da Central inválido.'}); return False
        return True
    def _guard_session(self):
        if not self._guard_token(): return None
        user=_session_user(self)
        if not user: _json(self,401,{'ok':False,'error':'Sessão da Central inválida ou expirada. Faça login novamente.'}); return None
        return user
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path; q=parse_qs(parsed.query)
        try:
            if path=='/api/v140/health':
                if not self._guard_token(): return
                snap=_ecf().central_local_health_snapshot(); _json(self,200,{'ok':True,'server_name':socket.gethostname(),'server_version':getattr(_ecf(),'APP_VERSION','V141'),'time':_now(),**snap}); return
            if path=='/api/v140/auth/user':
                if not self._guard_token(): return
                _json(self,200,{'ok':True,'user':_safe_user(_ecf().db_auth_get_user(q.get('email',[''])[0]))}); return
            if path=='/api/v140/auth/user_by_id':
                if not self._guard_token(): return
                _json(self,200,{'ok':True,'user':_safe_user(_ecf().db_auth_get_user_by_id(int(q.get('id',['0'])[0] or 0)))}); return
            if path=='/api/v140/auth/users':
                if not _admin_user(self): _json(self,403,{'ok':False,'error':'Apenas administradores podem consultar usuários.'}); return
                _json(self,200,{'ok':True,'users':[_safe_user(u) for u in _ecf().db_auth_list_users()]}); return
            if path=='/api/v140/auth/reset_requests':
                if not _admin_user(self): _json(self,403,{'ok':False,'error':'Apenas administradores podem consultar solicitações.'}); return
                pending=q.get('pending_only',['1'])[0] not in ('0','false','False'); _json(self,200,{'ok':True,'requests':_ecf().db_auth_list_reset_requests(pending,int(q.get('limit',['100'])[0]))}); return
            if path=='/api/v140/auth/reset_count':
                if not _admin_user(self): _json(self,403,{'ok':False,'error':'Apenas administradores podem consultar solicitações.'}); return
                _json(self,200,{'ok':True,'count':_ecf().db_auth_pending_reset_count()}); return
            if path=='/api/v140/auth/activity':
                if not _admin_user(self): _json(self,403,{'ok':False,'error':'Apenas administradores podem consultar atividades.'}); return
                _json(self,200,{'ok':True,'activity':_ecf().db_auth_activity(int(q.get('limit',['120'])[0]))}); return
            if path=='/api/v140/sync/pull':
                if not self._guard_session(): return
                _json(self,200,_pull(q.get('since',[''])[0],int(q.get('limit',['80'])[0]))); return
            _json(self,404,{'ok':False,'error':'Endpoint não encontrado.'})
        except Exception as exc: _json(self,500,{'ok':False,'error':str(exc)})
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            payload=_body(self); ecf=_ecf()
            if path=='/api/v140/auth/login':
                if not self._guard_token(): return
                user=ecf.db_auth_login(payload.get('email',''),payload.get('password','')); _json(self,200,{'ok':True,'session_token':_issue_session(user),'user':_safe_user(user)}); return
            if path=='/api/v140/auth/register':
                if not self._guard_token(): return
                user=ecf.db_auth_register_user(payload.get('name',''),payload.get('email',''),payload.get('password','')); _json(self,200,{'ok':True,'user':_safe_user(user)}); return
            if path=='/api/v140/auth/reset_request':
                if not self._guard_token(): return
                accepted=ecf.db_auth_request_password_reset(payload.get('email',''))
                _json(self,200,{'ok':True,'accepted':bool(accepted)}); return
            if path=='/api/v140/auth/import_users':
                if not self._guard_token(): return
                rows=payload.get('users') or []; conn=ecf._auth_connect(); imported=0
                try:
                    for row in rows:
                        if not row.get('email') or not row.get('password_hash') or not row.get('password_salt'): continue
                        email=str(row.get('email') or '').strip().lower()
                        existing=conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE",(email,)).fetchone()
                        if existing:
                            existing_full=conn.execute("SELECT password_hash,password_salt,must_set_password,role,status FROM users WHERE id=?",(int(existing[0]),)).fetchone()
                            incoming_hash=str(row.get('password_hash') or '')
                            # Existing central account remains authoritative for role/status.
                            # Import may only seed credentials when the central account has no password yet.
                            if existing_full and not str(existing_full[0] or '') and incoming_hash:
                                conn.execute("UPDATE users SET name=CASE WHEN name='' THEN ? ELSE name END,password_hash=?,password_salt=?,password_iterations=?,must_set_password=?,updated_at=? WHERE id=?",(str(row.get('name') or ''),incoming_hash,str(row.get('password_salt') or ''),int(row.get('password_iterations') or ecf.AUTH_PASSWORD_ITERATIONS),int(row.get('must_set_password') or 0),_now(),int(existing[0])))
                            imported+=1
                        else:
                            conn.execute("INSERT INTO users(name,email,password_hash,password_salt,password_iterations,role,status,must_set_password,created_at,updated_at,last_login_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(str(row.get('name') or ''),email,str(row.get('password_hash') or ''),str(row.get('password_salt') or ''),int(row.get('password_iterations') or ecf.AUTH_PASSWORD_ITERATIONS),('admin' if email==str(ecf.AUTH_BOOTSTRAP_EMAIL or '').strip().lower() and str(row.get('role') or '')=='admin' else 'user'),'active',int(row.get('must_set_password') or 0),str(row.get('created_at') or _now()),str(row.get('updated_at') or _now()),row.get('last_login_at')))
                            imported+=1
                    conn.commit()
                finally: conn.close()
                _json(self,200,{'ok':True,'imported':imported}); return
            user=self._guard_session()
            if not user: return
            if path=='/api/v140/auth/set_password':
                target_id=int(payload.get('user_id') or user['id'])
                if target_id!=int(user['id']) and not ecf._auth_is_admin(user): _json(self,403,{'ok':False,'error':'Sem permissão para redefinir esta senha.'}); return
                ecf.db_auth_set_password(target_id,payload.get('password','')); _json(self,200,{'ok':True,'user':_safe_user(ecf.db_auth_get_user_by_id(target_id))}); return
            if path=='/api/v140/auth/status':
                if not ecf._auth_is_admin(user): _json(self,403,{'ok':False,'error':'Apenas administradores podem alterar usuários.'}); return
                _json(self,200,{'ok':True,'changed':ecf.db_auth_set_status(int(payload.get('user_id')),str(payload.get('status')),user)}); return
            if path=='/api/v140/auth/reset_resolve':
                if not ecf._auth_is_admin(user): _json(self,403,{'ok':False,'error':'Apenas administradores podem concluir solicitações.'}); return
                _json(self,200,{'ok':True,'changed':ecf.db_auth_resolve_reset_request(int(payload.get('request_id')),user,str(payload.get('status') or 'resolved'))}); return
            if path=='/api/v140/auth/log':
                ecf.db_auth_log(user,str(payload.get('action') or ''),str(payload.get('details') or '')); _json(self,200,{'ok':True}); return
            if path=='/api/v140/sync/push':
                _json(self,200,_push(payload)); return
            _json(self,404,{'ok':False,'error':'Endpoint não encontrado.'})
        except Exception as exc: _json(self,400,{'ok':False,'error':str(exc)})


def run_server(port=PORT):
    global PORT; PORT=int(port or PORT)
    from central_client import ensure_server_configured, write_connection_file
    _init_shared_columns()
    _backfill_central_timestamps()
    st=_settings()
    if st.get('role')!='server' or not st.get('token'):
        ensure_server_configured(PORT)
    path,urls=write_connection_file(PORT)
    try:
        _ecf().create_automatic_backup_if_due()
    except Exception as exc:
        print(f'Backup automático: {exc}')
    backup_stop=threading.Event()
    def backup_loop():
        while not backup_stop.wait(900):
            try: _ecf().create_automatic_backup_if_due()
            except Exception as exc: print(f'Backup automático: {exc}')
    threading.Thread(target=backup_loop,name='ExatoAutoBackup',daemon=True).start()
    server=ThreadingHTTPServer((HOST,PORT),Handler); server.daemon_threads=True
    print('EXATO CENTRAL FISCAL — SERVIDOR CENTRAL')
    print(f'Servidor: {socket.gethostname()}'); print(f'Porta: {PORT}')
    for url in urls: print(f'  {url}')
    print(f'Arquivo de conexão: {path}'); print('Servidor ativo. Ctrl+C para encerrar.')
    try: server.serve_forever(poll_interval=0.4)
    finally:
        backup_stop.set()
        server.server_close()
