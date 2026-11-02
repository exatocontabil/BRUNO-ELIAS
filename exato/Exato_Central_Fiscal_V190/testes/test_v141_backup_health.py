import os, sys, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v141_backup_')
sys.path.insert(0,str(ROOT/'programa'))
import exato_central_fiscal as e
import central_client as c
e.init_database(); c.save_settings(enabled=True, role='server', token='T'*64, server_url='')
p=e.create_automatic_backup_if_due(force=True)
assert p and Path(p).exists()
with zipfile.ZipFile(p,'r') as z:
    names=set(z.namelist())
    assert 'central_fiscal.db' in names and 'usuarios.db' in names and 'config.json' in names and 'backup_manifest.json' in names
st=e._get_backup_status(); assert st['last_automatic_backup_at'] and not st['automatic_due']
print('V141 backup health: OK')
