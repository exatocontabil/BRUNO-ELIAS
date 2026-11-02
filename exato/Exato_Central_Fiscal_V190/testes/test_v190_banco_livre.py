"""V168: o banco não fica travado (database is locked) enquanto o repositório copia arquivos pela rede, e a configuração resiste ao "Acesso negado"."""
import os, sys, tempfile, shutil, time, threading, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_livre_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
import exato_repositorio as R
m.init_database(); CNPJ='12345678000195'; m.db_register_company(CNPJ,'EMPRESA TESTE LTDA')
c=sqlite3.connect(m.DB_PATH)
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'd{i}',CNPJ,'nfe','NF-e','Saída',str(i),'1','2026-09-10T10:00:00','10.00','Autorizado','%044d'%i,'1',b'<x n="%d"/>'%i,'2026-01-01','2026-01-01') for i in range(40)])
c.commit(); c.close()
srv=Path(tempfile.mkdtemp(prefix='exato_v174_srv3_'))
# rede lenta: cada arquivo demora 0,15 s para copiar (a cópia inteira leva ~6 s)
original=R.copiar_arquivo
def lenta(*a,**k): time.sleep(0.15); return original(*a,**k)
R.copiar_arquivo=lenta
res={}
t=threading.Thread(target=lambda: res.update(R.copiar_pendentes(m.DB_PATH.as_posix(),str(srv))),daemon=True); t.start()
time.sleep(.5)
piores=0.0; n=0
while t.is_alive():
    t0=time.perf_counter()
    m.db_list_companies(); rid=m.db_start_run(CNPJ); m.db_update_run(rid,'Concluído',finished=True,total_found=0,new_count=0,duplicate_count=0,error_text='')     # leitura e escrita comuns do programa
    piores=max(piores,time.perf_counter()-t0); n+=1; time.sleep(.05)
t.join(); R.copiar_arquivo=original
assert res.get('novos')==40 and n>=5,(res,n)
assert piores<1.5,f'o banco ficou travado por {piores:.1f} s durante a cópia'
# a preparação completa do banco roda uma vez só (não grava mais a cada consulta)
antes=sqlite3.connect(str(m.AUTH_DB_PATH)).execute("SELECT updated_at FROM users WHERE email=? COLLATE NOCASE",(m.AUTH_BOOTSTRAP_EMAIL,)).fetchone()
time.sleep(1.1); [m.init_database() for _ in range(5)]
depois=sqlite3.connect(str(m.AUTH_DB_PATH)).execute("SELECT updated_at FROM users WHERE email=? COLLATE NOCASE",(m.AUTH_BOOTSTRAP_EMAIL,)).fetchone()
assert antes==depois,(antes,depois)
m.init_database(force=True)                  # forçar continua funcionando (restauração de cópia de segurança)
# configuração: "Acesso negado" passageiro do Windows (antivírus segurando o arquivo) é tentado de novo
real=Path.replace; falhas={'n':0}
def instavel(self,alvo):
    if falhas['n']<3: falhas['n']+=1; raise PermissionError(5,'Acesso negado')
    return real(self,alvo)
Path.replace=instavel
try: m.save_config({'teste':1})
finally: Path.replace=real
assert falhas['n']==3 and m.load_config().get('teste')==1
shutil.rmtree(srv,ignore_errors=True); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 banco livre: OK')
