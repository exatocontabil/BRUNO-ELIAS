import os, tempfile, importlib.util, time, hashlib, ast
from pathlib import Path
from PIL import Image

os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v114_test_')
os.environ['EXATO_CF_DEV']='1'
BASE=Path('/mnt/data/work_v114/Exato_Central_Fiscal_V113')
spec=importlib.util.spec_from_file_location('exato_v114', BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

app=mod.App()
app.withdraw()
app.update_idletasks()
assert app._ia_live_ready, 'IA renderer not ready'

frames=[]
now=time.monotonic()
# baseline
app._ia_live_mouse_target=-0.8
app._ia_live_last_mouse_at=now
for i in range(5):
    frames.append(app._ia_live_render_frame(now+i*0.04))
# move gaze across the character and advance animation
app._ia_live_mouse_target=0.8
app._ia_live_last_mouse_at=time.monotonic()
for i in range(8):
    frames.append(app._ia_live_render_frame(now+0.25+i*0.04))
# save representative frames
out=BASE/'testes'/'v114_ia_frames'
out.mkdir(exist_ok=True)
for i,imgtk in enumerate([frames[0],frames[4],frames[8],frames[-1]]):
    img=app.tk.call(imgtk,'cget','-file') if False else None
# Force real app renderer to create and then take screenshot under Xvfb separately.
# For numeric validation, compare PhotoImage pixel bytes via Tk get on a small sample.
# Also validate the renderer produces different images across time.
import PIL.ImageTk as _ITK
_ITK.PhotoImage=lambda im: im
photos=[]
for i in range(12):
    photos.append(app._ia_live_render_frame(time.monotonic()+i*0.05))

# Export representative frames and verify their pixels differ.
out=BASE/'testes'/'v114_ia_frames'; out.mkdir(exist_ok=True)
paths=[]
for i,photo in enumerate((photos[0],photos[4],photos[8],photos[11])):
    path=out/f'frame_{i}.png'
    photo.save(path)
    paths.append(path)
imgs=[Image.open(p).convert('RGBA') for p in paths]
from PIL import ImageChops
diffs=[ImageChops.difference(imgs[0],img).getbbox() for img in imgs[1:]]
assert any(d is not None for d in diffs), f'No meaningful rendered pixel variation: {diffs}'

# Blink test is driven directly by setting a blink start.
app._ia_live_blink_started=time.monotonic()
b1=app._ia_live_blink_factor(time.monotonic())
b2=app._ia_live_blink_factor(time.monotonic()+0.07)
b3=app._ia_live_blink_factor(time.monotonic()+0.3)
assert b1 > b2 and b3 == 1.0, (b1,b2,b3)

app.destroy()
print('V114_IA_PROCEDURAL_RENDER_OK')
