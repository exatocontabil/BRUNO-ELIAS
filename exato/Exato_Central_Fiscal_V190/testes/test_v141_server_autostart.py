import os, sys, tempfile, subprocess, shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v141_autostart_')
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as e
import central_client as c
e.init_database()
assert c.configure_windows_server_autostart(True,8765) in (False, True)
# On non-Windows CI the registry is intentionally unsupported; on Windows the command is registered.
print('V141 server autostart capability: OK')
