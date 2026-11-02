"""V137 — SALVAR XMLs NOVOS por destino."""
from __future__ import annotations
import os, sys, tempfile, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v134_new_')
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as mod  # noqa: E402
mod.init_database(); cnpj='49894842000123'; now='2026-09-25T17:00:00'
conn=sqlite3.connect(mod.DB_PATH); conn.execute('INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)',(cnpj,'ELYON LTDA',now,now))
for i,n in enumerate(('100','101'),1):
    key=('1'*43)+str(i)
    xml=f'''<nfeProc><NFe><infNFe Id="NFe{key}"><ide><dhEmi>2026-09-25T10:00:00-03:00</dhEmi><nNF>{n}</nNF><serie>0</serie><mod>55</mod></ide></infNFe></NFe></nfeProc>'''.encode()
    conn.execute("""INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(f'doc{i}',cnpj,'nfe','NF-e','Saída',n,'0','2026-09-25T10:00:00','1.00','Autorizado',key,'',xml,now,now))
conn.commit(); conn.close()
rows=mod.db_load_documents_as_payload(cnpj,limit=10,date_from='2026-09-01',date_to='2026-09-30')
dest=Path(os.environ['EXATO_DATA_DIR'])/'dest'; dest.mkdir()
# Register one of the two documents as already exported to this destination.
mod.db_mark_documents_exported([rows[0]],str(dest))
new_rows=mod.db_filter_unexported(rows,str(dest))
assert len(new_rows)==1
saved,errors=mod.save_documents_organized(new_rows,str(dest),cnpj,config_data={'company_names':{cnpj:'ELYON LTDA'}},generate_companion_pdf=False,period_start='2026-09-01',period_end='2026-09-30')
assert not errors, errors
assert len([p for p in saved if str(p).lower().endswith('.xml')])==1
mod.db_mark_documents_exported(new_rows,str(dest))
assert mod.db_filter_unexported(rows,str(dest))==[]
print('V137 SALVAR XMLs NOVOS: OK')
