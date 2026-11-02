import os, tempfile, importlib.util, time
from pathlib import Path
from PIL import ImageGrab
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v112_cap_')
os.environ['EXATO_CF_DEV']='1'
BASE=Path('/mnt/data/work_v112')
spec=importlib.util.spec_from_file_location('exato_v112',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
app=mod.App(); app.geometry('1240x760+0+0'); app.update_idletasks()
for name,fn in [('dashboard',app._show_dashboard),('audit',app._show_audit),('sync',app._show_webservice_test)]:
    fn(); app.update(); time.sleep(.5); ImageGrab.grab().save(f'/mnt/data/work_v112/{name}.png')
app.destroy()
