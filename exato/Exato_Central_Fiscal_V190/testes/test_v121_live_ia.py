import os, tempfile, importlib.util, time
from pathlib import Path
from PIL import Image, ImageChops
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v120_ia_')
os.environ['EXATO_CF_DEV']='1'
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('exato_v120',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
app=mod.App(); app.withdraw(); app.update_idletasks()
assert app._ia_live_ready
assert app._ia_behavior_state in app._ia_behavior_profiles

# Numeric/procedural variation over time.
import PIL.ImageTk as _ITK
_ITK.PhotoImage=lambda im: im
frames=[]
start=time.monotonic()
for i in range(18):
    frames.append(app._ia_live_render_frame(start+i*0.06))
assert all(f is not None for f in frames)
diffs=[ImageChops.difference(frames[0],f).getbbox() for f in frames[1:]]
assert any(d is not None for d in diffs), diffs

# Cursor attention is perceived and should enter interaction briefly.
class E: pass
e=E(); e.x_root=app.ia_float_img.winfo_rootx()+app.ia_float_img.winfo_width()/2; e.y_root=app.ia_float_img.winfo_rooty()+app.ia_float_img.winfo_height()/2
app._ia_float_on_mouse_move(e)
assert app._ia_behavior_cursor_near
assert app._ia_behavior_state in {'INTERAGINDO','OBSERVANDO'}

# Contextual state transitions.
app._ia_float_set_state('processando','Processando',1200,react=True)
assert app._ia_behavior_state in {'PROCESSANDO','BUSCANDO'}
app._ia_float_set_state('concluido','Concluído',800,react=True)
assert app._ia_behavior_state=='SUCESSO'
app._ia_float_set_state('divergencia','Atenção',800,react=True)
assert app._ia_behavior_state=='DIVERGÊNCIA'
app._ia_float_set_state('erro','Erro',800,react=True)
assert app._ia_behavior_state=='ERRO'

# After transient expiry, the engine returns to contextual idle/observation.
app._ia_float_set_state('repouso','',0)
app._ia_behavior_until=time.monotonic()-1
state=app._ia_behavior_tick(time.monotonic())
assert state in {'IDLE','OBSERVANDO','INTERAGINDO'}

# Blink still works and supports natural durations.
app._ia_live_blink_started=time.monotonic(); b1=app._ia_live_blink_factor(time.monotonic()); b2=app._ia_live_blink_factor(time.monotonic()+0.07); b3=app._ia_live_blink_factor(time.monotonic()+0.30)
assert b1>b2 and b3==1.0

app.destroy()
print('V121_IA_BEHAVIOR_ENGINE_OK')
