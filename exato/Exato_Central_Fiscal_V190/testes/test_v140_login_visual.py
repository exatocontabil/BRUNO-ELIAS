import os, sys, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=tempfile.mkdtemp(prefix='exato_v140_login_visual_'); os.environ['EXATO_DATA_DIR']=data; sys.path.insert(0,str(ROOT))
import exato_central_fiscal as m
m.init_database(); login=m.LoginWindow(); login.update_idletasks(); login.update()
# Ensure key controls are present and inside visible window bounds.
texts=[]
def walk(w):
    try:
        if 'text' in w.keys():
            t=str(w.cget('text') or '')
            if t: texts.append((t,w.winfo_rootx(),w.winfo_rooty(),w.winfo_width(),w.winfo_height()))
    except Exception: pass
    for c in w.winfo_children(): walk(c)
walk(login)
for label in ['ESQUECI MINHA SENHA','CONFIGURAR CENTRAL COMPARTILHADA','ENTRAR','SOLICITAR CADASTRO']:
    assert any(label in t for t,*_ in texts), f'missing {label}'
# Main window geometry should contain all controls without obvious overflow.
wr=login.winfo_rootx()+login.winfo_width(); hb=login.winfo_rooty()+login.winfo_height()
for t,x,y,w,h in texts:
    if any(k in t for k in ['ESQUECI MINHA SENHA','CONFIGURAR CENTRAL COMPARTILHADA','ENTRAR','SOLICITAR CADASTRO']):
        assert x>=login.winfo_rootx() and y>=login.winfo_rooty() and x+w<=wr+2 and y+h<=hb+2, (t,x,y,w,h,wr,hb)
try:
    from PIL import ImageGrab
    out=Path('/mnt/data/v140_login_visual.png'); ImageGrab.grab().save(out); print('SCREENSHOT',out)
except Exception as exc: print('SCREENSHOT_SKIPPED',exc)
login.destroy(); shutil.rmtree(data,ignore_errors=True)
print('V140 login visual: OK')
