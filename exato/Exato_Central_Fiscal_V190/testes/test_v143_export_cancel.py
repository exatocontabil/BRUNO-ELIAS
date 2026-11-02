"""V143 — cancelamento seguro entre empresas durante exportação de XMLs."""
from __future__ import annotations
import os, sys, tempfile, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR'] = tempfile.mkdtemp(prefix='exato_v142_export_cancel_')
os.environ['EXATO_CF_DEV'] = '1'
sys.path.insert(0, str(ROOT))
import exato_central_fiscal as mod  # noqa: E402

mod.messagebox.showinfo = lambda *a, **k: None
mod.messagebox.showwarning = lambda *a, **k: None
mod.messagebox.showerror = lambda *a, **k: (_ for _ in ()).throw(AssertionError(f'error: {a}'))
mod.init_database()
root_folder = Path(os.environ['EXATO_DATA_DIR']) / 'clientes'; root_folder.mkdir(parents=True, exist_ok=True)
companies=[('49894842000123','ELYON LTDA'),('12345678000195','SEGUNDA EMPRESA LTDA')]
xmls=[]; docs=[]
conn=sqlite3.connect(mod.DB_PATH)
for idx,(cnpj,name) in enumerate(companies,1):
    now=f'2026-09-25T18:0{idx}:00'; conn.execute('INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)',(cnpj,name,now,now))
    key=('98765432109876543210987654321098765432100'+str(idx))[:44]
    xml=(f'<nfeProc><NFe><infNFe Id="NFe{key}"><ide><dhEmi>2026-09-25T10:00:00-03:00</dhEmi><nNF>{300000+idx}</nNF><serie>0</serie><mod>55</mod></ide></infNFe></NFe></nfeProc>').encode()
    conn.execute("""INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(f'd{idx}',cnpj,'nfe','NF-e','Saída',str(300000+idx),'0','2026-09-25T10:00:00','10.00','Autorizado',key,str(idx),xml,now,now))
    docs.append({'doc_id':f'd{idx}','cnpj':cnpj,'family':'nfe','doc_type':'NF-e','direction':'Saída','number':str(300000+idx),'issued_at':'2026-09-25T10:00:00','access_key':key,'xml':xml})
    xmls.append(xml)
conn.commit(); conn.close()

app=mod.App(); app._show_documents(); app.update_idletasks()
orig_save=mod.save_documents_organized; orig_ask=mod.filedialog.askdirectory
mod.filedialog.askdirectory=lambda **k:str(root_folder)
def slow_save(*args,**kwargs):
    time.sleep(0.35)
    return orig_save(*args,**kwargs)
mod.save_documents_organized=slow_save
app._export_document_rows(docs,only_new=False)

cancel_requested=False; deadline=time.time()+5
while time.time()<deadline:
    app.update()
    label=getattr(app,'_export_progress_company',None)
    if label and label.get() and 'Empresa 1 de 2' in label.get() and not cancel_requested:
        app._cancel_export_progress(); cancel_requested=True
    if cancel_requested and not getattr(app,'_export_progress_window',None):
        break
    time.sleep(0.02)

assert cancel_requested, 'cancel control was never exercised'
# One company may finish before cancellation is observed; the second must never be exported.
xml_files=list(root_folder.rglob('*.xml'))
assert len(xml_files)==1, xml_files
assert len(mod.db_filter_unexported(docs,str(root_folder)))==1
app.destroy(); mod.save_documents_organized=orig_save; mod.filedialog.askdirectory=orig_ask
print('V143 export cancel: OK')
