import os, tempfile, importlib.util, time
from pathlib import Path
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v117_ui_')
os.environ['EXATO_CF_DEV']='1'
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v116ui',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
app=mod.App(); app.geometry('1126x760+0+0'); app.update_idletasks(); app.update()
assert app.title().startswith('Exato Central Fiscal — V118')
assert app._ia_live_ready
# Let the procedural loop run long enough to exercise timed callbacks.
end=time.monotonic()+1.2
while time.monotonic()<end:
    app.update()
    time.sleep(0.02)
# Screen transitions must keep the IA state machine alive.
for screen_method in ('_show_dashboard','_show_documents','_show_reports','_show_pending','_show_history'):
    if hasattr(app,screen_method):
        getattr(app,screen_method)(); app.update_idletasks(); app.update()
        assert getattr(app,'current_screen',None)
# Cursor direction regression.
class E: pass
e=E(); cx=app.ia_float_img.winfo_rootx()+app.ia_float_img.winfo_width()/2; cy=app.ia_float_img.winfo_rooty()+app.ia_float_img.winfo_height()/2; e.y_root=cy; e.x_root=cx-360; app._ia_float_on_mouse_move(e); left=app._ia_live_mouse_target
e.x_root=cx+360; app._ia_float_on_mouse_move(e); right=app._ia_live_mouse_target
assert left < -0.30 and right > 0.30
app.destroy()
print('V118_UI_STARTUP_SMOKE_OK')
