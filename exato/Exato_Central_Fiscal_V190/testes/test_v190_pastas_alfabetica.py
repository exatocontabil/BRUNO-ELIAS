"""V182: pastas do Repositório em ordem alfabética ("Nome - CNPJ"); as antigas ("CNPJ - Nome") são reconhecidas e migradas (renomeia; se o destino já existe, une sem sobrescrever)."""
import os, sys, sqlite3, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_alf_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_repositorio as R, exato_busca_compartilhada as C
# ---- reconhecimento dos dois formatos
assert R.cnpj_no_nome('ELYON LTDA - 49894842000123')=='49894842000123' and R.cnpj_no_nome('49894842000123 - ELYON LTDA')=='49894842000123' and R.cnpj_no_nome('49894842000123')=='49894842000123'
assert R.cnpj_no_nome('.indice')=='' and R.cnpj_no_nome('Backups')=='' and R.nome_no_nome('ELYON LTDA - 49894842000123')=='ELYON LTDA' and R.nome_no_nome('49894842000123 - ELYON LTDA')=='ELYON LTDA'
tmp=Path(tempfile.mkdtemp(prefix='exato_v183_srv_')); servidor=tmp/'servidor'; rep=servidor/'Repositório'; rep.mkdir(parents=True)
db=str(tmp/'banco.db'); conn=sqlite3.connect(db)
conn.execute("CREATE TABLE companies(cnpj TEXT PRIMARY KEY,name TEXT)")
conn.execute("""CREATE TABLE documents(doc_id TEXT PRIMARY KEY,cnpj TEXT,family TEXT,doc_type TEXT,direction TEXT,number TEXT,series TEXT,issued_at TEXT,value TEXT,status TEXT,access_key TEXT,source_nsu TEXT,xml BLOB,first_seen_at TEXT,last_seen_at TEXT)""")
empresas=[('11222333000181','ZETA COMERCIO LTDA'),('45723174000110','ALFA SERVICOS LTDA'),('12345678000195','MARIA & FILHOS ME')]
for c,n in empresas: conn.execute("INSERT INTO companies VALUES(?,?)",(c,n))
for i,(c,n) in enumerate(empresas,1):
    conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,issued_at,status,access_key,xml,first_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(f'd{i}',c,'nfe','NF-e','Saída','2026-09-10T10:00:00','Autorizado','%044d'%i,f'<nfe n="{i}"/>'.encode(),'2026-10-01T10:00:00'))
conn.commit(); conn.close()
# pasta ANTIGA já existente de uma empresa, com um arquivo dentro
antiga=rep/'11222333000181 - ZETA COMERCIO LTDA'; (antiga/'2026'/'08'/'NF-e'/'Saída').mkdir(parents=True); (antiga/'2026'/'08'/'NF-e'/'Saída'/('%044d.xml'%99)).write_bytes(b'<nfe n="99"/>')
# e uma que já existe nos DOIS formatos (une sem sobrescrever)
dupla_velha=rep/'45723174000110 - ALFA SERVICOS LTDA'; (dupla_velha/'2026'/'07').mkdir(parents=True); (dupla_velha/'2026'/'07'/'x.xml').write_bytes(b'velho')
dupla_nova=rep/'ALFA SERVICOS LTDA - 45723174000110'; (dupla_nova/'2026'/'07').mkdir(parents=True); (dupla_nova/'2026'/'07'/'y.xml').write_bytes(b'novo')
r=R.copiar_pendentes(db,str(servidor)); assert r['ok'],r
nomes=sorted(p.name for p in rep.iterdir())
assert nomes==['ALFA SERVICOS LTDA - 45723174000110','MARIA & FILHOS ME - 12345678000195','ZETA COMERCIO LTDA - 11222333000181'],nomes          # ordem alfabética pelo nome, formato novo, sem pasta antiga
assert (rep/'ZETA COMERCIO LTDA - 11222333000181'/'2026'/'08'/'NF-e'/'Saída'/('%044d.xml'%99)).exists()          # o arquivo da pasta antiga foi junto
assert (rep/'ALFA SERVICOS LTDA - 45723174000110'/'2026'/'07'/'x.xml').read_bytes()==b'velho' and (rep/'ALFA SERVICOS LTDA - 45723174000110'/'2026'/'07'/'y.xml').read_bytes()==b'novo'          # unido, nada sobrescrito
assert sorted(nomes,key=str.casefold)==nomes
# o resto do sistema acha a empresa nos dois formatos
assert {c for c,_f,_e,_p in C.arquivos(str(servidor))}=={'11222333000181','45723174000110','12345678000195'}
rod=R.resumo(db); assert rod['pendentes'] if 'pendentes' in rod else True
print('V182 pastas em ordem alfabética OK')
