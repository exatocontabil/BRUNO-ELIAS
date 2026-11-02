"""V134 — UI do Arquivo Fiscal Local e ações de exportação."""
from __future__ import annotations
import os, sys, tempfile, sqlite3, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v134_ui_')
os.environ['EXATO_CF_DEV']='1'
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as mod  # noqa: E402
mod.messagebox.showinfo=lambda *a,**k: None
mod.messagebox.showwarning=lambda *a,**k: (_ for _ in ()).throw(AssertionError(f'warning: {a}'))
mod.messagebox.showerror=lambda *a,**k: (_ for _ in ()).throw(AssertionError(f'error: {a}'))
chosen=Path(os.environ['EXATO_DATA_DIR'])/'dest'; chosen.mkdir(parents=True,exist_ok=True)
mod.filedialog.askdirectory=lambda **k: str(chosen)
mod.init_database(); cnpj='49894842000123'; now='2026-09-25T17:00:00'
xml=b'''<?xml version="1.0" encoding="UTF-8"?><nfeProc><NFe><infNFe Id="NFe12345678901234567890123456789012345678901234"><ide><dhEmi>2026-09-25T10:00:00-03:00</dhEmi><nNF>290248</nNF><serie>0</serie><mod>55</mod></ide></infNFe></NFe></nfeProc>'''
conn=sqlite3.connect(mod.DB_PATH)
conn.execute('INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)',(cnpj,'ELYON LTDA',now,now))
conn.execute("""INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",('doc1',cnpj,'nfe','NF-e','Saída','290248','0','2026-09-25T10:00:00','14248.94','Autorizado','12345678901234567890123456789012345678901234','10',xml,now,now))
conn.commit(); conn.close()
app=mod.App(); app.cnpj_var.set(cnpj); app._capture_period_snapshot=('2026-09-01','2026-09-30'); app._cnpj_confirmed=True; app._period_confirmed=True
app._show_documents(); app.update_idletasks()
assert mod.APP_VERSION=='V134'
assert hasattr(app,'doc_save_xml_btn') and hasattr(app,'doc_save_new_xml_btn')
assert 'exportacao' in app.doc_tree['columns']
assert len(app.doc_tree.get_children())==1
# No export yet
row=app._doc_row_map[next(iter(app._doc_row_map))]
assert not row.get('exported_any')
assert str(app.doc_save_new_xml_btn.cget('state'))=='normal'
# Save selected XML, then refresh should show export status.
iid=app.doc_tree.get_children()[0]; app.doc_tree.selection_set(iid); app._on_document_selection(); app._save_selected_document_xmls()
for _ in range(120):
    app.update()
    if list(chosen.rglob('*.xml')): break
    time.sleep(0.02)
assert len(list(chosen.rglob('*.xml')))==1
app._refresh_documents_list(); app.update_idletasks()
row2=app._doc_row_map[next(iter(app._doc_row_map))]
assert row2.get('exported_any')==1
# Filter Exportado / Não exportado
app.doc_export_status.set('Exportado'); app._refresh_documents_list(); assert len(app.doc_tree.get_children())==1
app.doc_export_status.set('Não exportado'); app._refresh_documents_list(); assert len(app.doc_tree.get_children())==0
app.destroy()
print('V134 documents UI: OK')
