from pathlib import Path
import ast, hashlib, importlib.util, json, os, tempfile, time

BASE = Path(__file__).resolve().parents[1]
os.environ['EXATO_CF_DEV'] = '1'
os.environ['EXATO_DATA_DIR'] = tempfile.mkdtemp(prefix='exato_v123_exatinho_')
spec = importlib.util.spec_from_file_location('v123_exatinho', BASE / 'exato_central_fiscal.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert mod.APP_VERSION == 'V123'

# Identity / interaction surface.
app = mod.App()
app.withdraw()
app.update_idletasks()
assert hasattr(app, '_exatinho_on_click')
assert hasattr(app, '_exatinho_open_panel')
assert hasattr(app, 'ia_sidebar_interaction')
assert getattr(app, '_exatinho_first_interaction', False) is True
app._exatinho_on_click(None)
app.update_idletasks()
assert app._exatinho_panel_open is True
assert len(app.ia_sidebar_interaction.winfo_children()) >= 3
def all_texts(widget):
    texts=[]
    for child in widget.winfo_children():
        try:
            if 'text' in child.keys():
                texts.append(str(child.cget('text') or ''))
        except Exception:
            pass
        texts.extend(all_texts(child))
    return texts
assert 'EXATINHO' in '\n'.join(all_texts(app.ia_sidebar_interaction))
app._exatinho_show_last_event()
app.update_idletasks()
assert app._exatinho_last_panel_topic == 'history'
app._exatinho_show_status()
app.update_idletasks()
assert app._exatinho_last_panel_topic == 'status'
app._exatinho_close_panel()
assert app._exatinho_panel_open is False
app.destroy()
print('V123_EXATINHO_INTERACTION_OK')

# Protected functions: reproducible source-segment hashes against the V122 source package.
protected = [
    'test_sef_nfe_webservice', 'choose_nfe_actor', 'mark_nfe_sync_cycle',
    'sync_documents_automatically', 'generate_fiscal_representation_pdf',
    'open_document_fiscal_representation', 'save_documents_organized',
    '_audit_xml_rows', '_audit_key', '_audit_fallback_key',
    '_audit_compare_pair', '_audit_build_rows', 'generate_documents_pdf'
]

def hashes(path):
    src = Path(path).read_text(encoding='utf-8')
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in protected:
            out[node.name] = hashlib.sha256((ast.get_source_segment(src, node) or '').encode()).hexdigest()
    return out

baseline = BASE.parent.parent / 'base' / 'exato_central_fiscal.py'
# Fallback when running from a different work dir: V122 zip extraction is recorded beside the work package.
if not baseline.exists():
    baseline = Path('/mnt/data/work_v123/base/exato_central_fiscal.py')
base_hash = hashes(baseline)
now_hash = hashes(BASE / 'exato_central_fiscal.py')
assert all(base_hash.get(k) == now_hash.get(k) for k in protected)
print('V123_PROTECTED_NUCLEI_OK_13_OF_13')

# Context helpers remain evidence-first and contextual.
app2 = mod.App(); app2.withdraw(); app2.update_idletasks()
app2._ia_event_context.update({'screen':'documents','status':'SYNC_SUCCESS','documents':71,'last_cstat':'','last_result_at':time.monotonic()})
assert '71' in app2._exatinho_context_message()
app2.destroy()
print('V123_CONTEXT_OK')
