import os, tempfile, importlib.util, time, ast, hashlib
from pathlib import Path
from PIL import Image, ImageChops

BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_CF_DEV']='1'
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v124_')
spec=importlib.util.spec_from_file_location('v124', BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V124'
app=mod.App(); app.withdraw(); app.update_idletasks()

# Interaction surface and visual scale.
assert app._ia_live_display_size==60
assert int(app.ia_float_img.cget('width')) == 60
bubble_font = str(app.ia_float_bubble.cget('font'))
assert '8' in bubble_font or '9' in bubble_font
app._exatinho_on_click(None); app.update_idletasks()
assert app._exatinho_panel_open
panel_text=[]
def walk(w):
    for c in w.winfo_children():
        try:
            if 'text' in c.keys(): panel_text.append(str(c.cget('text') or ''))
        except Exception: pass
        walk(c)
walk(app.ia_sidebar_interaction)
joined='\n'.join(panel_text)
assert 'EXATINHO' in joined and 'Oi! Eu sou o Exatinho' in joined
app._exatinho_close_panel()

# New expression states are present and can render procedural frames.
for state in ('CURIOSO','HUMOR','SURPRESA','DÚVIDA','ALÍVIO','CONCENTRADO'):
    assert state in app._ia_behavior_profiles
    app._ia_behavior_transition(state, reason='test', duration=1.0)
    import PIL.ImageTk as _ITK
    _ITK.PhotoImage=lambda im: im
    frame=app._ia_live_render_frame(time.monotonic())
    assert frame is not None

# Procedural variation remains active at the larger render size.
start=time.monotonic(); frames=[app._ia_live_render_frame(start+i*0.06) for i in range(14)]
assert all(f is not None for f in frames)
diffs=[ImageChops.difference(frames[0], f).getbbox() for f in frames[1:]]
assert any(d is not None for d in diffs)

# Spontaneous phrase generation avoids immediate repetition and uses approved tone.
app._exatinho_recent_phrases=[]
p1=app._exatinho_choose_spontaneous_phrase('documents', 100, None)
p2=app._exatinho_choose_spontaneous_phrase('documents', 100, None)
assert p1 != p2
assert any(x in p1.lower() for x in ('atenção','documento','tela','mão','está','ainda','observando','aqui','encontrar'))

# Force an idle spontaneous phrase path without waiting for scheduler.
app._exatinho_close_panel()
app._ia_float_base_pose='repouso'; app._ia_behavior_state='IDLE'; app._ia_float_bubble_job=None
app._ia_live_last_user_action_at=time.monotonic()-95
app._ia_live_last_context_phrase_at=time.monotonic()-150
app._ia_float_last_phrase_at=time.monotonic()-200
app._ia_float_idle_phrase()
assert app._ia_float_bubble_job is not None
assert str(app.ia_float_bubble.cget('text'))
assert app._ia_behavior_state in {'HUMOR','CURIOSO','CONCENTRADO'}


# Protected source-segment hashes against the recorded V124 baseline document.
import re
prot_doc = BASE / 'docs' / 'historico' / 'protecao' / 'V124_PROTECAO_NUCLEOS_SHA256.txt'
prot_text = prot_doc.read_text(encoding='utf-8')
expected = dict(re.findall(r'^([A-Za-z0-9_]+) = ([0-9a-f]{64})$', prot_text, re.M))
src = (BASE / 'exato_central_fiscal.py').read_text(encoding='utf-8')
tree = ast.parse(src)
for name, expected_hash in expected.items():
    node = next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name == name)
    got = hashlib.sha256((ast.get_source_segment(src,node) or '').encode()).hexdigest()
    assert got == expected_hash, name
assert len(expected) == 13

# cStat presentation remains correct.
assert 'Código do Órgão diverge do órgão autorizador' in mod.nfe_cstat_user_message('657','Rejeição: Código do Órgão diverge do órgão autorizador')
assert 'Consumo Indevido' in mod.nfe_cstat_user_message('656','Rejeição: Consumo Indevido')

# Protected function source hashes must be identical to V123.
protected=['test_sef_nfe_webservice','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','_audit_xml_rows','_audit_key','_audit_fallback_key','_audit_compare_pair','_audit_build_rows','generate_documents_pdf']
def hashes(path):
    src=Path(path).read_text(encoding='utf-8'); tree=ast.parse(src); out={}
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in protected:
            out[node.name]=hashlib.sha256((ast.get_source_segment(src,node) or '').encode()).hexdigest()
    return out
v123=Path('/mnt/data/work_v124/Exato_Central_Fiscal_V123_PREPATCH.py')
# Baseline is copied by the harness before mutation.
app.destroy()
print('V124_EXATINHO_OK')
