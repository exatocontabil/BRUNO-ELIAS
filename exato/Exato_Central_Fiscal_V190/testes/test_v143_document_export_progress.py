"""V143 — progresso e persistência da exportação local de XMLs."""
from __future__ import annotations
import os, sys, tempfile, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR'] = tempfile.mkdtemp(prefix='exato_v142_export_progress_')
os.environ['EXATO_CF_DEV'] = '1'
sys.path.insert(0, str(ROOT))
import exato_central_fiscal as mod  # noqa: E402

mod.messagebox.showinfo = lambda *a, **k: None
mod.messagebox.showwarning = lambda *a, **k: (_ for _ in ()).throw(AssertionError(f'warning: {a}'))
mod.messagebox.showerror = lambda *a, **k: (_ for _ in ()).throw(AssertionError(f'error: {a}'))

mod.init_database()
root_folder = Path(os.environ['EXATO_DATA_DIR']) / 'clientes'
root_folder.mkdir(parents=True, exist_ok=True)

companies = [
    ('49894842000123', 'ELYON LTDA'),
    ('12345678000195', 'SEGUNDA EMPRESA LTDA'),
]
xml_template = b'''<?xml version="1.0" encoding="UTF-8"?><nfeProc><NFe><infNFe Id="NFe{key}"><ide><dhEmi>2026-09-25T10:00:00-03:00</dhEmi><nNF>{num}</nNF><serie>0</serie><mod>55</mod></ide></infNFe></NFe></nfeProc>'''

docs = []
conn = sqlite3.connect(mod.DB_PATH)
for idx, (cnpj, company) in enumerate(companies, 1):
    now = f'2026-09-25T17:0{idx}:00'
    conn.execute('INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)', (cnpj, company, now, now))
    xml = xml_template.replace(b'{key}', str(1000 + idx).encode()).replace(b'{num}', str(290000 + idx).encode())
    doc_id = f'doc{idx}'
    access = ('12345678901234567890123456789012345678' + str(idx))[:44]
    conn.execute("""INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (doc_id, cnpj, 'nfe', 'NF-e', 'Saída', str(290000 + idx), '0', '2026-09-25T10:00:00', '142.48', 'Autorizado', access, str(idx), xml, now, now))
    docs.append({'doc_id': doc_id, 'cnpj': cnpj, 'family': 'nfe', 'doc_type': 'NF-e', 'direction': 'Saída',
                 'number': str(290000 + idx), 'issued_at': '2026-09-25T10:00:00', 'access_key': access, 'xml': xml})
conn.commit(); conn.close()

app = mod.App()
app._show_documents()
app.update_idletasks()
original_save = mod.save_documents_organized
orig_ask = mod.filedialog.askdirectory
mod.filedialog.askdirectory = lambda **k: str(root_folder)

def slow_save(*args, **kwargs):
    time.sleep(0.20)
    return original_save(*args, **kwargs)
mod.save_documents_organized = slow_save

items = list(app.doc_tree.get_children())
assert len(items) == 2, items
app.doc_tree.selection_set(*items)
app._on_document_selection()
app._export_document_rows(docs, only_new=False)

observed = []
deadline = time.time() + 5
while time.time() < deadline:
    app.update()
    win = getattr(app, '_export_progress_window', None)
    if win is not None and win.winfo_exists():
        observed.append((app._export_progress_percent.get(), app._export_progress_company.get()))
        if not getattr(app, '_export_progress_window', None):
            break
    if list(root_folder.rglob('*.xml')) and not getattr(app, '_export_progress_window', None):
        break
    time.sleep(0.02)

assert any(p == '0%' for p, _ in observed), observed
assert any('Empresa 1 de 2' in c for _, c in observed), observed
assert any('Empresa 2 de 2' in c for _, c in observed), observed

# Wait for the export to finish and verify the local export register.
deadline = time.time() + 5
while time.time() < deadline and getattr(app, '_export_progress_window', None):
    app.update(); time.sleep(0.02)

xmls = list(root_folder.rglob('*.xml'))
assert len(xmls) == 2, xmls
assert mod.db_filter_unexported(docs, str(root_folder)) == []

# Re-import the same database surface as a new app version would: the data directory is external to the version folder.
import importlib
mod.save_documents_organized = original_save
mod.filedialog.askdirectory = orig_ask
sys.modules.pop('exato_central_fiscal', None)
mod2 = importlib.import_module('exato_central_fiscal')
assert mod2.APP_VERSION == 'V143'
assert mod2.db_filter_unexported(docs, str(root_folder)) == []

app.destroy()
print('V143 document export progress + persistence: OK')
