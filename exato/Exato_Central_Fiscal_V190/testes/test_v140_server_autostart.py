import os, subprocess, sys, tempfile, time, urllib.request, json, socket, signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=tempfile.mkdtemp(prefix='exato_v140_autostart_')
env=os.environ.copy(); env['EXATO_DATA_DIR']=data; env['PYTHONPATH']=str(ROOT)

def free_port():
    s=socket.socket(); s.bind(('127.0.0.1',0)); port=s.getsockname()[1]; s.close(); return port

port=free_port()
proc_pid=None
try:
    code=f"""
import exato_central_fiscal as e
import central_client as c
e._prepare_persistent_storage(); e.init_database(); c.ensure_server_configured({port}); print(c.ensure_server_running({port})); print(c.get_settings()['token'])
"""
    p=subprocess.run([sys.executable,'-c',code],env=env,cwd=ROOT,check=True,capture_output=True,text=True)
    lines=p.stdout.strip().splitlines(); assert lines[0]=='True', p.stdout+p.stderr; token=lines[-1]
    end=time.time()+6; ok=False
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.time()<end:
        try:
            req=urllib.request.Request(f'http://127.0.0.1:{port}/api/v140/health',headers={'X-Exato-Token':token})
            with opener.open(req,timeout=0.7) as r:
                obj=json.loads(r.read().decode()); ok=bool(obj.get('ok')); break
        except Exception: time.sleep(.1)
    assert ok
    print(f'V140 server autostart: OK (port {port})')
finally:
    # Identify only the child created for this exact temporary port.
    try:
        out=subprocess.check_output(['pgrep','-af',f'exato_central_fiscal.py --central-server --central-port {port}'],text=True,stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            try:
                pid=int(line.split()[0]);
                if pid != os.getpid(): os.kill(pid,signal.SIGTERM)
            except Exception: pass
    except Exception: pass
