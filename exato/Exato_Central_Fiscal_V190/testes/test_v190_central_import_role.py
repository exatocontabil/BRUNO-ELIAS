import os, sys, tempfile, shutil, json, threading, urllib.request, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v146_import_')
sys.path.insert(0,str(ROOT/'programa'))
import exato_central_fiscal as m
import central_client, exato_central_server as srv
from http.server import ThreadingHTTPServer
try:
    m.init_database(); central_client.ensure_server_configured(18766)
    token=central_client.get_settings()['token']
    handler=getattr(srv,'Handler',None) or next(v for k,v in vars(srv).items() if isinstance(v,type) and k.endswith('Handler') and k!='BaseHTTPRequestHandler')
    httpd=ThreadingHTTPServer(('127.0.0.1',18766),handler); threading.Thread(target=httpd.serve_forever,daemon=True).start(); time.sleep(.3)
    salt,digest,iters=m._auth_password_record('Senha#2026')
    row=dict(name='Intruso',email='intruso@example.com',role='admin',status='active',password_hash=digest,password_salt=salt,password_iterations=iters)
    req=urllib.request.Request('http://127.0.0.1:18766/api/v140/auth/import_users',data=json.dumps({'users':[row]}).encode(),headers={'X-Exato-Token':token,'Content-Type':'application/json'},method='POST')
    out=json.loads(urllib.request.urlopen(req,timeout=5).read().decode()); assert out.get('imported')==1,out
    assert m.db_auth_get_user('intruso@example.com')['role']=='user'
    httpd.shutdown()
    assert [m._natural_number_key(x) for x in ('2','10')]==sorted([m._natural_number_key(x) for x in ('2','10')])
finally:
    shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 import role: OK')
