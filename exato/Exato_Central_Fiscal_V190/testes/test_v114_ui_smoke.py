import os, tempfile, importlib.util, time
from pathlib import Path
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v114_ui_')
os.environ['EXATO_CF_DEV']='1'
BASE=Path('/mnt/data/work_v114/Exato_Central_Fiscal_V113')
spec=importlib.util.spec_from_file_location('v114ui',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
app=mod.App(); app.geometry('1126x760+0+0'); app.update_idletasks(); app.update()
assert app.title().startswith('Exato Central Fiscal — V114')
app._show_audit(); app.update_idletasks()
assert set(app.audit_family_buttons)=={'nfe','nfce'}
app._audit_set_family('nfe'); app._audit_set_family('nfce')
assert app._audit_selected_families()==['nfe','nfce']
# Cursor direction enters live engine.
class E: x_root=app.winfo_rootx()+5
app._ia_float_on_mouse_move(E()); left=app._ia_live_mouse_target
E.x_root=app.winfo_rootx()+app.winfo_width()-5
app._ia_float_on_mouse_move(E()); right=app._ia_live_mouse_target
assert left < -0.8 and right > 0.8
app.destroy()
print('V114_UI_LIVE_IA_SMOKE_OK')
