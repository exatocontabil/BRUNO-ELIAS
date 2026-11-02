"""V183: prioridade de empresa na fila do Repositório (copiar a empresa pedida primeiro / só ela), sem tocar nas outras."""
import os, sys, sqlite3, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_prio_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_repositorio as R
tmp=Path(tempfile.mkdtemp(prefix='exato_v183_prio_srv_')); db=str(tmp/'b.db')
EMP={'11222333000181':'ALFA LTDA','45723174000110':'BETA LTDA','11444777000161':'GAMA LTDA'}
c=sqlite3.connect(db); c.execute("CREATE TABLE companies(cnpj TEXT PRIMARY KEY,name TEXT)")
src=Path(ROOT/'testes'/'test_v190_repositorio.py').read_text(encoding='utf-8')
ddl=src[src.index('conn.execute("""CREATE TABLE documents'):]; ddl=ddl[:ddl.index('""")')+4]
c.execute(ddl.replace('conn.execute("""','').replace('""")','').strip())          # mesma tabela do teste do Repositório
for cn,n in EMP.items(): c.execute("INSERT INTO companies VALUES(?,?)",(cn,n))
k=0
for cn in EMP:
    for i in range(4):
        k+=1; c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,issued_at,status,access_key,xml,first_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (f'd{k:03d}',cn,'nfe','NF-e','Saída','2026-09-10T10:00:00','Autorizado','%044d'%k,f'<n i="{k}"/>'.encode(),'2026-10-01T10:00:00'))
c.commit(); c.close()
srv=tmp/'srv'; srv.mkdir()
fila=R.pendentes_por_empresa(db); assert fila=={cn:4 for cn in EMP},fila
# prioridade à 3ª empresa: ela é copiada ANTES das outras (limite de 'maximo' pega só ela)
r=R.copiar_pendentes(db,str(srv),prioridade=['11444777000161'],maximo=4,lote=2)
f2=R.pendentes_por_empresa(db); assert '11444777000161' not in f2 and f2.get('11222333000181')==4 and f2.get('45723174000110')==4,f2
# "só esta": não toca nas outras
r=R.copiar_pendentes(db,str(srv),somente='45.723.174/0001-10'); assert r['novos']==4,r
f3=R.pendentes_por_empresa(db); assert f3=={'11222333000181':4},f3
# sem prioridade: copia o resto
r=R.copiar_pendentes(db,str(srv)); assert r['novos']==4 and R.pendentes_por_empresa(db)=={} and R.pendentes(db)==0
print('prioridade ok')
