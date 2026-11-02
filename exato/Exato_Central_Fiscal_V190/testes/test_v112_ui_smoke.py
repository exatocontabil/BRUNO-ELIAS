import os, tempfile
from pathlib import Path
import importlib.util
BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='v112_ui_')
spec=importlib.util.spec_from_file_location('exato_v112_ui',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
app=mod.App(); app.withdraw(); app.update_idletasks()
assert hasattr(app,'ia_float')
app._ia_float_on_mouse_move(type('E',(),{'x_root':app.winfo_rootx()+app.winfo_width()*0.8,'y_root':app.winfo_rooty()+200})())
assert app._ia_float_mouse_dir=='right'
app._ia_float_set_state('repouso','Teste V112',duration_ms=100)
app.update_idletasks(); app.destroy()
print('V112_UI_SMOKE_OK')
