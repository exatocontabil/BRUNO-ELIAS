import os, sys, tempfile, sqlite3, time
from pathlib import Path
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v132_ui_')
os.environ['EXATO_CF_DEV']='1'
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import exato_central_fiscal as mod
mod.messagebox.showinfo=lambda *a,**k:None
mod.messagebox.showwarning=lambda *a,**k:None
mod.messagebox.showerror=lambda *a,**k:None
mod.init_database()
cnpj='49894842000123'; name='ELYON LTDA'; now='2026-09-25T17:00:00'
conn=sqlite3.connect(mod.DB_PATH)
conn.execute('INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)',(cnpj,name,now,now))
for i in range(3):
  xml=(f'<?xml version="1.0"?><nfeProc><NFe><infNFe Id="NFe1234567890123456789012345678901234567890123{i}"><ide><dhEmi>2026-09-25T10:00:00-03:00</dhEmi><nNF>{290248+i}</nNF><serie>0</serie><mod>55</mod></ide></infNFe></NFe></nfeProc>').encode()
  key=f'1234567890123456789012345678901234567890123{i}'
  conn.execute('INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(f'doc{i}',cnpj,'nfe','NF-e','Saída',str(290248+i),'0','2026-09-25T10:00:00',str(100+i),'Autorizado',key,str(i+1),xml,now,now))
conn.commit(); conn.close()
app=mod.App(); app.cnpj_var.set(cnpj); app._show_documents(); app.update_idletasks()
items=app.doc_tree.get_children(); app.doc_tree.selection_set(items); app._on_document_selection(); app.update_idletasks();
# Keep window alive briefly for screenshot.
time.sleep(1)
try:
 import pyautogui
 pyautogui.screenshot('/mnt/data/work_v132/preview/documentos_salvar_xmls_v132.png')
except Exception:
 pass
app.destroy()
print('UI_SCREENSHOT_OK')
