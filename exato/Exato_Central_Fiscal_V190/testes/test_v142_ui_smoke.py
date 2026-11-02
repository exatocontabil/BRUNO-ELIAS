import os, sys, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v141_ui_')
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaUI#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaUI#2026')
app=m.App(current_user=user); app.update_idletasks(); app.update()
assert m.APP_VERSION=='V142'
assert hasattr(app,'header_central')
app._show_maintenance(); app.update_idletasks(); app.update()
assert hasattr(app,'central_health_labels')
assert set(('connection','sync','autostart','backup')).issubset(app.central_health_labels)
app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V142 UI smoke: OK')
