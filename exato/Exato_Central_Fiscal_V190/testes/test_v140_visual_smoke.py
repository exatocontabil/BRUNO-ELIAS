import os, sys, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=tempfile.mkdtemp(prefix='exato_v140_visual_')
os.environ['EXATO_DATA_DIR']=data
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as m
m.init_database()
u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL)
m.db_auth_set_password(u['id'],'SenhaVisual#2026')
user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaVisual#2026')
app=m.App(current_user=user)
app.update_idletasks(); app.update()
# Basic presence assertions.
assert m.LOGO_PATH.is_file() and m.LOGO_MARK_PATH.is_file()
assert m.MASCOT_EXATO_IA_PATH.is_file()
assert any(v is not None for v in getattr(app,'__dict__',{}).values())
# Find labels/images referring to app assets if exposed; the core app has mascot state/rendering methods.
assert hasattr(app,'_exatinho_presence_tick') and hasattr(app,'_exatinho_open_panel')
try:
    from PIL import ImageGrab
    out=Path('/mnt/data/v140_visual_smoke.png')
    img=ImageGrab.grab()
    img.save(out)
    print('SCREENSHOT',out)
except Exception as exc:
    print('SCREENSHOT_SKIPPED',exc)
print('V140 visual smoke: OK')
app.destroy(); shutil.rmtree(data,ignore_errors=True)
