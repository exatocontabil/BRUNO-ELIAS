"""V168: o reparo único do arquivo fiscal não segura mais a abertura: roda em segundo plano, com avisos, e NFS-e fica de fora."""
import os, sys, tempfile, shutil, time, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_reparo_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaRep#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaRep#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
CNPJ='12345678000195'; m.db_register_company(CNPJ,'EMPRESA TESTE LTDA')
def nfe(n): return ('<nfeProc><NFe><infNFe Id="NFe%044d"><ide><mod>55</mod><nNF>%d</nNF></ide><emit><CNPJ>%s</CNPJ><xNome>X</xNome></emit></infNFe></NFe></nfeProc>'%(n,n,CNPJ)).encode()
c=sqlite3.connect(m.DB_PATH)
# 300 NF-e gravadas com chave de 41 dígitos (defeito antigo) + 4000 NFS-e (chave de 50 dígitos: não são candidatas)
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'a{i}',CNPJ,'nfe','NF-e','Saída',str(i),'2026-01-01','Autorizado','%041d'%i,nfe(i),'x','x') for i in range(300)])
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'n{i}',CNPJ,'nfse','NFS-e','Saída',str(i),'2026-01-01','Autorizado','%050d'%i,b'<NFSe/>','x','x') for i in range(4000)])
c.commit(); c.close()
assert c and sqlite3.connect(m.DB_PATH).execute("SELECT COUNT(*) "+m._v145_repair_candidates_sql()).fetchone()[0]==300      # só as NF-e: NFS-e ficam de fora
# --- a função em si: etapas avisadas em ordem e correções feitas
etapas=[]; marcas=[]
r=m.repair_document_index_v145(lambda d,t: marcas.append((d,t)),etapas.append)
assert r['keys_fixed']==300 and not r['skipped'] and any('cópia de segurança' in e for e in etapas) and any('Gravando' in e for e in etapas) and any('canceladas' in e for e in etapas),(r,etapas)
assert r['backup'] and Path(r['backup']).exists()
assert m.repair_document_index_v145()['skipped']                      # segunda vez: nada a fazer, imediato
# --- no programa: roda em segundo plano depois de abrir; a janela não espera
c=sqlite3.connect(m.DB_PATH); c.execute("UPDATE documents SET access_key=substr(access_key,4) WHERE family='nfe'"); c.commit(); c.close()
st=m._read_data_state(); st.pop('v145_index_repair',None); m._write_data_state(st)
app=m.App(current_user=user); status=[]
orig=app.set_status; app.set_status=lambda t,*a,**k: (status.append(t), orig(t,*a,**k))[1]
try:
    t0=time.time(); app.geometry('1366x650+0+0'); app.update(); assert time.time()-t0<5            # abre normalmente
    m._V145_STATE.update(rodando=False,feito=False)
    app._v145_start(); assert m._V145_STATE['rodando']
    fim=time.time()+30
    while not m._V145_STATE['feito'] and time.time()<fim: app.update(); time.sleep(.02)
    assert m._V145_STATE['feito'],'o reparo tem de terminar'
    app.update(); assert any('Preparando o arquivo fiscal' in t or 'cópia de segurança' in t for t in status) and any('Arquivo fiscal conferido' in t for t in status),status
    n=sqlite3.connect(m.DB_PATH).execute("SELECT COUNT(*) FROM documents WHERE family='nfe' AND length(access_key)=44").fetchone()[0]; assert n==300
    app._v145_start(); app.update(); assert not m._V145_STATE['rodando']                   # não roda duas vezes
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 reparo em segundo plano: OK')
