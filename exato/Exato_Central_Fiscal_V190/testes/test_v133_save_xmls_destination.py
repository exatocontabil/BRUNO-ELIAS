"""V133 — SALVAR XMLs sempre permite escolher a pasta de destino."""
from __future__ import annotations
import os, sys, tempfile, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR'] = tempfile.mkdtemp(prefix='exato_v133_save_xmls_')
os.environ['EXATO_CF_DEV'] = '1'
sys.path.insert(0, str(ROOT))
import exato_central_fiscal as mod  # noqa: E402

mod.messagebox.showinfo = lambda *a, **k: None
mod.messagebox.showwarning = lambda *a, **k: (_ for _ in ()).throw(AssertionError(f'warning: {a}'))
mod.messagebox.showerror = lambda *a, **k: (_ for _ in ()).throw(AssertionError(f'error: {a}'))

chosen = Path(os.environ['EXATO_DATA_DIR']) / 'destino_escolhido'
chosen.mkdir(parents=True, exist_ok=True)
ask_calls = []
mod.filedialog.askdirectory = lambda **k: (ask_calls.append(k) or str(chosen))

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
assert mod.APP_VERSION == 'V133'
app.cnpj_var.set(cnpj)
app._capture_period_snapshot = ('2026-09-01','2026-09-30')
app._cnpj_confirmed = True
app._period_confirmed = True
old_root = Path(os.environ['EXATO_DATA_DIR']) / 'antigo_root'
old_root.mkdir(parents=True, exist_ok=True)
app._auto_search_config()['root_folder'] = str(old_root)
app._show_documents(); app.update_idletasks()
items = app.doc_tree.get_children(); assert len(items) == 1
app.doc_tree.selection_set(items[0]); app._on_document_selection(); app.update_idletasks()
assert str(app.doc_save_xml_btn.cget('state')) == 'normal'

app._save_selected_document_xmls()
for _ in range(120):
    app.update()
    xmls = list(chosen.rglob('*.xml')) if chosen.exists() else []
    if xmls: break
    time.sleep(0.02)
assert ask_calls, 'O diálogo de seleção de pasta não foi chamado.'
assert ask_calls[0].get('title') == 'Escolha a pasta onde os XMLs serão salvos'
assert ask_calls[0].get('initialdir') == str(old_root)
assert len(xmls) == 1, xmls
assert xmls[0].read_bytes() == xml
assert app._auto_search_config().get('root_folder') == str(chosen)
app.destroy()
print('V133 SALVAR XMLs destination test: OK')
