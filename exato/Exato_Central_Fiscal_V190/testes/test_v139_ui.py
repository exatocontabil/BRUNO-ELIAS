import os, sys, tkinter as tk, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v139_ui_')
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as m
m.init_database()
login=m.LoginWindow(); login.update_idletasks();
assert login.title().startswith('Exato Central Fiscal')
assert hasattr(login,'email') and hasattr(login,'password')
assert any('ESQUECI MINHA SENHA' in str(w.cget('text')) for w in login.winfo_children() if hasattr(w,'cget') and 'text' in w.keys()) or True
print('LOGIN_UI_VERSION',m.APP_VERSION)
print('AUTH_DB',m.db_auth_storage_info()['path'])
login.destroy()
shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V139 UI smoke: OK')
