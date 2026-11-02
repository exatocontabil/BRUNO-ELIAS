"""V132 — ação SALVAR XMLs na tela Documentos Fiscais."""
from __future__ import annotations
import os, sys, tempfile, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR'] = tempfile.mkdtemp(prefix='exato_v132_save_xmls_')
os.environ['EXATO_CF_DEV'] = '1'
sys.path.insert(0, str(ROOT))
import exato_central_fiscal as mod  # noqa: E402

mod.messagebox.showinfo = lambda *a, **k: None
mod.messagebox.showwarning = lambda *a, **k: (_ for _ in ()).throw(AssertionError(f'warning: {a}'))
mod.messagebox.showerror = lambda *a, **k: (_ for _ in ()).throw(AssertionError(f'error: {a}'))
mod.filedialog.askdirectory = lambda **k: ''

mod.init_database()
cnpj = '49894842000123'
company = 'ELYON LTDA'
now = '2026-09-25T17:00:00'
conn = sqlite3.connect(mod.DB_PATH)
conn.execute('INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)', (cnpj, company, now, now))
xml = b'''<?xml version="1.0" encoding="UTF-8"?><nfeProc><NFe><infNFe Id="NFe12345678901234567890123456789012345678901234"><ide><dhEmi>2026-09-25T10:00:00-03:00</dhEmi><nNF>290248</nNF><serie>0</serie><mod>55</mod></ide></infNFe></NFe></nfeProc>'''
conn.execute("""INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", ('doc1', cnpj, 'nfe', 'NF-e', 'Saída', '290248', '0', '2026-09-25T10:00:00', '14248.94', 'Autorizado', '12345678901234567890123456789012345678901234', '10', xml, now, now))
conn.commit(); conn.close()

app = mod.App()
app.cnpj_var.set(cnpj)
app._capture_period_snapshot = ('2026-09-01','2026-09-30')
app._cnpj_confirmed = True
app._period_confirmed = True
root_folder = Path(os.environ['EXATO_DATA_DIR']) / 'clientes'
root_folder.mkdir(parents=True, exist_ok=True)
app._auto_search_config()['root_folder'] = str(root_folder)
app._show_documents()
app.update_idletasks()

# Exactly the new UI control must exist and start disabled without selection.
assert mod.APP_VERSION == 'V132'
assert hasattr(app, 'doc_save_xml_btn')
assert app.doc_save_xml_btn.cget('text') == 'SALVAR XMLs'
assert str(app.doc_save_xml_btn.cget('state')) == 'disabled'
assert app.doc_save_xml_btn.winfo_x()+app.doc_save_xml_btn.winfo_width() <= app.doc_save_xml_btn.master.winfo_width() + 2

# Select the stored document and verify the action becomes available.
items = app.doc_tree.get_children()
assert len(items) == 1
app.doc_tree.selection_set(items[0])
app._on_document_selection()
assert str(app.doc_save_xml_btn.cget('state')) == 'normal'

# Export only the selected stored XML; no webservice call occurs in this path.
app._save_selected_document_xmls()
root = Path(app._auto_search_config()['root_folder'])
out = root / company
for _ in range(100):
    app.update()
    xmls = list(root.rglob('*.xml')) if root.exists() else []
    if xmls:
        break
    time.sleep(0.02)
assert len(xmls) == 1, xmls
assert xmls[0].read_bytes() == xml

app.destroy()
print('V132 SALVAR XMLs test: OK')
