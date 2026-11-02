import os, shutil, sqlite3, subprocess, sys, tempfile, time, urllib.request, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PORT = 18765


def run(env_dir):
    env = os.environ.copy(); env['EXATO_DATA_DIR'] = str(env_dir); env['PYTHONPATH'] = str(ROOT / 'programa')
    return env


def wait_health(env, token, timeout=8):
    url=f'http://127.0.0.1:{PORT}/api/v140/health'
    end=time.time()+timeout
    while time.time()<end:
        try:
            req=urllib.request.Request(url,headers={'X-Exato-Token':token})
            with urllib.request.urlopen(req,timeout=0.7) as r:
                obj=json.loads(r.read().decode())
                if obj.get('ok'): return True
        except Exception: pass
        time.sleep(0.15)
    return False


def main():
    base=Path(tempfile.mkdtemp(prefix='exato_v140_central_test_'))
    server_dir=base/'server'; client_dir=base/'client'
    server_dir.mkdir(); client_dir.mkdir()
    proc=None
    try:
        # Server process: initialize persistent databases and central server config.
        envs=run(server_dir)
        code="""
import exato_central_fiscal as e
from central_client import ensure_server_configured

e._prepare_persistent_storage(); e.init_database(); ensure_server_configured(18765)
# Give bootstrap admin a password so remote login is exercised with a real credential.
e.db_auth_set_password(1, 'TesteCentral#2026')
print(e.central_client.get_settings()['token'], flush=True)
"""
        bootstrap=subprocess.run([PYTHON,'-c',code],env=envs,cwd=ROOT,check=True,capture_output=True,text=True)
        token=bootstrap.stdout.strip().splitlines()[-1].strip()
        assert token
        # Add a legacy server-side document BEFORE the server starts. This verifies
        # first-start backfill of pre-existing records into the shared timeline.
        code_srv="""
import exato_central_fiscal as e
xml=b'<NFe><infNFe Id="NFe123"/></NFe>'
e.db_upsert_documents('12345678000199',[{'doc_type':'NF-e','family':'nfe','direction':'Saída','number':'9001','series':'1','issued_at':'2026-09-29T08:00:00','value':'123.45','status':'Autorizado','chave':'12345678901234567890123456789012345678901234','xml':xml,'source_nsu':'1'}])
print('server-doc-ok', flush=True)
"""
        subprocess.run([PYTHON,'-c',code_srv],env=envs,cwd=ROOT,check=True)
        proc=subprocess.Popen([PYTHON,str(ROOT/'programa'/'exato_central_fiscal.py'),'--central-server','--central-port',str(PORT)],env=envs,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        assert wait_health(envs,token), 'central server did not start'
        connection_file=server_dir/'EXATO_CENTRAL_CONEXAO.txt'
        end=time.time()+4
        while time.time()<end and not connection_file.exists(): time.sleep(0.1)
        assert connection_file.exists(), 'connection file was not generated'

        # Client config/connect using the same connection file flow used by the UI.
        shutil.copy2(connection_file,client_dir/'EXATO_CENTRAL_CONEXAO.txt')
        envc=run(client_dir)
        code_cli="""
import exato_central_fiscal as e
import central_client as c

e._prepare_persistent_storage(); e.init_database(); conn_info=c.parse_connection_file(__import__('os').path.join(__import__('os').environ['EXATO_DATA_DIR'],'EXATO_CENTRAL_CONEXAO.txt'))
c.configure_client('http://127.0.0.1:18765', conn_info['token'])
c.remote_import_local_users()
u=c.remote_login('brunoalbano.elias8@gmail.com','TesteCentral#2026')
assert u and u.get('email')=='brunoalbano.elias8@gmail.com'
print('client-login-ok',u['id'],flush=True)
"""
        envc['EXATO_TOKEN']=token
        subprocess.run([PYTHON,'-c',code_cli],env=envc,cwd=ROOT,check=True)

        # Client creates a new user; it must be immediately visible on the shared server.
        code_reg="""
import exato_central_fiscal as e, central_client as c
u=c.remote_register_user('Maria Central','maria.central@example.com','Senha#2026')
assert u and u.get('status')=='active'
print('register-ok',flush=True)
"""
        subprocess.run([PYTHON,'-c',code_reg],env=envc,cwd=ROOT,check=True)
        code_srv_users="""
import exato_central_fiscal as e
users=e.db_auth_list_users()
assert any(u.get('email')=='maria.central@example.com' and u.get('status')=='active' for u in users)
print('server-user-ok',flush=True)
"""
        subprocess.run([PYTHON,'-c',code_srv_users],env=envs,cwd=ROOT,check=True)

        # Client-side document is pushed to server and server-side legacy doc is pulled back.
        code_client_doc="""
import exato_central_fiscal as e, central_client as c
c.remote_login('brunoalbano.elias8@gmail.com','TesteCentral#2026')
xml=b'<NFe><infNFe Id="NFeCLIENT"/></NFe>'
e.db_upsert_documents('12345678000199',[{'doc_type':'NF-e','family':'nfe','direction':'Entrada','number':'9002','series':'1','issued_at':'2026-09-29T09:00:00','value':'321.00','status':'Autorizado','chave':'98765432109876543210987654321098765432109876','xml':xml,'source_nsu':'2'}])
r=c.sync_now(max_seconds=8)
assert e.db_load_documents_as_payload('12345678000199', family='', limit=100)
print('client-sync-ok',flush=True)
"""
        subprocess.run([PYTHON,'-c',code_client_doc],env=envc,cwd=ROOT,check=True)
        code_srv_doc="""
import exato_central_fiscal as e
rows=e.db_load_documents_as_payload('12345678000199', family='', limit=100)
keys={str(r.get('chave') or '') for r in rows}
assert '98765432109876543210987654321098765432109876' in keys
print('server-doc-sync-ok',flush=True)
"""
        subprocess.run([PYTHON,'-c',code_srv_doc],env=envs,cwd=ROOT,check=True)
        code_client_export="""
import exato_central_fiscal as e, central_client as c
c.remote_login('brunoalbano.elias8@gmail.com','TesteCentral#2026')
rows=e.db_load_documents_as_payload('12345678000199', family='', limit=100)
row=next(x for x in rows if x.get('chave')=='98765432109876543210987654321098765432109876')
e.db_mark_documents_exported([row], '/tmp/exato-central-export-test', '/tmp/exato-central-export-test')
r=c.sync_now(max_seconds=8)
assert r.get('ok')
print('client-export-sync-ok',flush=True)
"""
        subprocess.run([PYTHON,'-c',code_client_export],env=envc,cwd=ROOT,check=True)
        code_srv_export="""
import exato_central_fiscal as e
rows=e.db_find_export_history('',100)
assert any(x.get('destination_root')=='/tmp/exato-central-export-test' for x in rows)
print('server-export-sync-ok',flush=True)
"""
        subprocess.run([PYTHON,'-c',code_srv_export],env=envs,cwd=ROOT,check=True)
        code_client_pull="""
import exato_central_fiscal as e, central_client as c
# Re-authenticate after the standalone process (session token is in-process only).
c.remote_login('brunoalbano.elias8@gmail.com','TesteCentral#2026')
r=c.sync_now(max_seconds=8)
rows=e.db_load_documents_as_payload('12345678000199', family='', limit=100)
keys={str(x.get('chave') or '') for x in rows}
assert '12345678901234567890123456789012345678901234' in keys
print('client-pull-ok',r.get('pulled'),flush=True)
"""
        subprocess.run([PYTHON,'-c',code_client_pull],env=envc,cwd=ROOT,check=True)

        # Password reset requested on client becomes visible to admin on server.
        code_reset="""
import exato_central_fiscal as e, central_client as c
c.remote_login('brunoalbano.elias8@gmail.com','TesteCentral#2026')
# Use the newly-created user so the request is meaningful.
assert c.remote_request_password_reset('maria.central@example.com')
print('reset-request-ok',flush=True)
"""
        subprocess.run([PYTHON,'-c',code_reset],env=envc,cwd=ROOT,check=True)
        code_reset_srv="""
import exato_central_fiscal as e
assert e.db_auth_pending_reset_count()>=1
print('reset-visible-ok',flush=True)
"""
        subprocess.run([PYTHON,'-c',code_reset_srv],env=envs,cwd=ROOT,check=True)
        print('V140 central sync: OK')
    finally:
        if proc:
            try: proc.terminate(); proc.wait(timeout=3)
            except Exception:
                try: proc.kill()
                except Exception: pass
        shutil.rmtree(base,ignore_errors=True)

if __name__=='__main__': main()
