"""V172: o banco não fica travado para a busca: carimbo da Central uma vez por lote (não por documento), semeadura única da fila de envio,
registro da busca que nunca trava a tela."""
import os, sys, sqlite3, tempfile, shutil, threading, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_banco_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
import central_client as cc
m.init_database()
N=30000
c=sqlite3.connect(m.DB_PATH)
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'd{i}','11222333000181','nfe','NF-e','Saída',str(i),'2026-09-10T10:00:00','Autorizado','%044d'%i,b'<nfe n="%d"/>'%i,'2026-10-01','2026-10-01') for i in range(N)]); c.commit(); c.close()
m.db_register_company('11222333000181','ELETROTAK MANUTENCAO LTDA')

# ---- esquema da Central: semeia UMA vez; fila vazia depois de enviar tudo NÃO recoloca o arquivo inteiro
cc.prepare_local_schema()
def fila(): 
    k=sqlite3.connect(m.DB_PATH); n=k.execute('SELECT COUNT(*) FROM central_outbox_documents').fetchone()[0]; k.close(); return n
assert fila()==N                                                # primeira vez: todo o arquivo entra na fila
k=sqlite3.connect(m.DB_PATH); k.execute('DELETE FROM central_outbox_documents'); k.execute('DELETE FROM central_outbox_companies'); k.execute('DELETE FROM central_outbox_exports'); k.commit(); k.close()
cc._SCHEMA_PRONTO.clear(); cc.prepare_local_schema(); cc._ensure_local_sync_schema(forcar=True)
assert fila()==0,fila()                                         # antes da V172 voltava a N (e a Central reenviava tudo, sem parar)
# instalação antiga (sem a marca): se já sincronizou, não semeia
k=sqlite3.connect(m.DB_PATH); k.execute('UPDATE central_sync_state SET last_sync_at=?',('2026-10-01T10:00:00',)); k.execute('ALTER TABLE central_sync_state DROP COLUMN semeado'); k.commit(); k.close()          # como a V171 deixou o banco
cc._SCHEMA_PRONTO.clear(); cc.prepare_local_schema(); assert fila()==0
# índices do carimbo
k=sqlite3.connect(m.DB_PATH); idx={r[1] for r in k.execute("SELECT * FROM sqlite_master WHERE type='index'").fetchall()}; k.close()
assert {'idx_documents_central','idx_companies_central','idx_document_exports_central'}<=idx,idx

# ---- marcar documentos (papel de servidor): UM carimbo por chamada, em sequência, em lotes curtos
cc.save_settings(enabled=True,role='server')
chamadas=[]; orig=cc._next_central_stamp
cc._next_central_stamp=lambda conn: (chamadas.append(1),orig(conn))[1]
ids=[f'd{i}' for i in range(1500)]
t=time.time(); cc.mark_documents_dirty(ids,'11222333000181'); dt=time.time()-t
cc._next_central_stamp=orig
assert len(chamadas)==1,len(chamadas)                          # antes: 3 consultas à tabela inteira POR documento
assert dt<8,dt
k=sqlite3.connect(m.DB_PATH)
sts=[r[0] for r in k.execute("SELECT central_updated_at FROM documents WHERE doc_id IN (%s) ORDER BY rowid"%','.join("'%s'"%i for i in ids[:50])).fetchall()]
assert len(set(sts))==50 and sts==sorted(sts),sts[:3]          # carimbos únicos e crescentes
assert k.execute('SELECT COUNT(*) FROM central_outbox_documents').fetchone()[0]==1500
k.close()
# durante a marcação o banco aceita outra gravação (lotes curtos)
trava=[]
def marcar(): cc.mark_documents_dirty([f'd{i}' for i in range(1500,6500)],'11222333000181')
th=threading.Thread(target=marcar); th.start(); ok=0
while th.is_alive():
    try:
        k=sqlite3.connect(m.DB_PATH,timeout=0.5); k.execute("INSERT INTO sync_runs(cnpj,started_at,status) VALUES('x','2026-10-07','teste')"); k.commit(); k.close(); ok+=1
    except sqlite3.OperationalError: trava.append(1)
    time.sleep(.01)
th.join(); assert ok>0 and len(trava)<=ok,(ok,len(trava))

# ---- registro da busca: banco ocupado NÃO trava a tela nem derruba a busca
m._RUN_ESPERA=0.3; m._RUN_TENTATIVAS=2
rid=m.db_start_run('11222333000181'); assert rid and rid>0
bloq=sqlite3.connect(m.DB_PATH,timeout=1); bloq.execute('BEGIN IMMEDIATE')          # outra parte do programa segura o banco para escrita
t=time.time(); rid2=m.db_start_run('11222333000181'); dt=time.time()-t
assert rid2 is None and dt<5,(rid2,dt)                                               # antes: esperava 30 s e dava "Algo não saiu como esperado"
t=time.time(); m.db_update_run(rid,'Concluído',finished=True,total_found=1); assert time.time()-t<5 and m.db_update_run(None,'x') is None
bloq.rollback(); bloq.close()
m.db_update_run(rid,'Concluído',finished=True,total_found=7,new_count=3); k=sqlite3.connect(m.DB_PATH); r=k.execute('SELECT status,total_found,new_count FROM sync_runs WHERE id=?',(rid,)).fetchone(); k.close()
assert r==('Concluído',7,3),r
rid3=m.db_start_run('11222333000181'); assert rid3 and rid3>rid
log=Path(m.APP_DATA_DIR/'Logs'/'exato.log'); assert log.exists() and 'Banco ocupado ao abrir o registro da busca' in log.read_text(encoding='utf-8',errors='replace')
shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V172 banco e busca: OK')
