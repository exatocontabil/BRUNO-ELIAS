"""V168: repositório de XML em pasta do servidor (cópia automática, fila, conflito, cópia do banco, conferência, prazo, restaurar)."""
import os, sys, sqlite3, tempfile, shutil, hashlib, zipfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_repo_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_repositorio as R
tmp=Path(tempfile.mkdtemp(prefix='exato_v174_srv_')); servidor=tmp/'servidor'; servidor.mkdir()
db=str(tmp/'banco.db')
conn=sqlite3.connect(db)
conn.execute("CREATE TABLE companies(cnpj TEXT PRIMARY KEY,name TEXT)")
conn.execute("""CREATE TABLE documents(doc_id TEXT PRIMARY KEY,cnpj TEXT,family TEXT,doc_type TEXT,direction TEXT,number TEXT,series TEXT,issued_at TEXT,value TEXT,status TEXT,access_key TEXT,source_nsu TEXT,xml BLOB,first_seen_at TEXT,last_seen_at TEXT)""")
conn.execute("INSERT INTO companies VALUES('11222333000181','ELETROTAK: MANUTENCAO LTDA')")
def doc(i,fam='nfe',direcao='Saída',data='2026-09-10T10:00:00',status='Autorizado',chave=None,xml=None,tipo='NF-e'):
    chave=chave if chave is not None else ('%044d'%i)
    conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,issued_at,status,access_key,xml,first_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (f'd{i}','11222333000181',fam,tipo,direcao,data,status,chave,xml if xml is not None else f'<nfe n="{i}"/>'.encode(),'2026-10-01T10:00:00'))
for i in range(1,6): doc(i)
doc(6,'nfse','Entrada',chave='9'*50,tipo='NFS-e'); doc(7,'nfse','Saída',data='2024-01-05T10:00:00',chave='8'*50,tipo='NFS-e')
doc(8,'nfe','',status='Evento',tipo='Evento',chave='7'*44); doc(9,'cte','Entrada',tipo='CT-e',data='')
conn.commit(); conn.close()

# servidor fora do ar: nada é copiado, nada se perde
fora=tmp/'nao_existe'
r=R.copiar_pendentes(db,str(fora)); assert not r['ok'] and r['motivo']=='inacessivel' and not fora.exists()
assert R.pendentes(db)==9 and R.resumo(db)['fila']==9

# primeira cópia: copia TUDO (inclusive evento e documento sem data), em pastas empresa/ano/mês/tipo
vistos=[]
r=R.copiar_pendentes(db,str(servidor),progresso=lambda x:vistos.append(x),lote=4)
assert r['ok'] and r['novos']==9 and r['erros']==0 and r['restantes']==0 and len(vistos)>=2,r
rep=servidor/'Repositório'; emp=[p for p in rep.iterdir()]; assert len(emp)==1 and emp[0].name=='ELETROTAK MANUTENCAO LTDA - 11222333000181',emp
assert (emp[0]/'2026'/'09'/'NF-e'/'Saída'/('%044d'%1+'.xml')).read_bytes()==b'<nfe n="1"/>'
assert (emp[0]/'2026'/'09'/'NFS-e'/'Tomados'/('9'*50+'.xml')).exists()
assert (emp[0]/'2024'/'01'/'NFS-e'/'Prestados'/('8'*50+'.xml')).exists()
assert any((emp[0]/'2026'/'09'/'Eventos NF-e').glob('*.xml')) and any((emp[0]/'2026'/'10'/'CT-e'/'Entrada').glob('*.xml'))
s=R.resumo(db); assert s['total']==9 and s['copiados']==9 and s['fila']==0 and s['diferentes']==0 and s['ultima_copia']
assert R.pendentes(db)==0 and R.copiar_pendentes(db,str(servidor))['novos']==0       # repetir não faz nada

# outro computador/banco novo com os mesmos XMLs: reconhece que já existem e não duplica
db2=str(tmp/'banco2.db'); shutil.copy(db,db2)
c2=sqlite3.connect(db2); c2.execute("DROP TABLE repositorio_copias"); c2.commit(); c2.close()
r=R.copiar_pendentes(db2,str(servidor)); assert r['existentes']==9 and r['novos']==0 and len(list(rep.rglob('*.xml')))==9

# V168: o 2º computador não lê os arquivos pela rede (passada rápida: lista a pasta e compara o tamanho)
db3=str(tmp/'banco3.db'); shutil.copy(db,db3)
c3=sqlite3.connect(db3); c3.execute("DROP TABLE repositorio_copias"); c3.commit(); c3.close()
_ler_original=R._ler; R._ler=lambda *a,**k: (_ for _ in ()).throw(AssertionError('não podia ler arquivo do servidor'))
r=R.copiar_pendentes(db3,str(servidor)); R._ler=_ler_original
assert r['existentes']==9 and r['novos']==0 and r['restantes']==0 and R.resumo(db3)['fila']==0

# arquivo igual no servidor com conteúdo diferente: nunca sobrescreve, guarda o novo ao lado e conta como diferente
alvo=emp[0]/'2026'/'09'/'NF-e'/'Saída'/('%044d'%2+'.xml'); alvo.write_bytes(b'ALTERADO')
c2=sqlite3.connect(db2); c2.execute("DELETE FROM repositorio_copias WHERE doc_id='d2'"); c2.commit(); c2.close()
r=R.copiar_pendentes(db2,str(servidor)); assert r['diferentes']==1 and alvo.read_bytes()==b'ALTERADO'
assert len(list(alvo.parent.glob('%044d.*.xml'%2)))==1 and R.resumo(db2)['diferentes']==1
# conferência: acusa o arquivo alterado e o que sumiu (e o que sumiu volta para a fila)
alvo.write_bytes(b'<nfe n="2"/>')
(emp[0]/'2026'/'09'/'NF-e'/'Saída'/('%044d'%3+'.xml')).unlink(); (emp[0]/'2026'/'09'/'NF-e'/'Saída'/('%044d'%4+'.xml')).write_bytes(b'x')
p=R.verificar(db,str(servidor),amostra=1000); assert any('sumiu' in t for t in p) and any('alterado' in t for t in p),p
assert R.pendentes(db)==1 and R.copiar_pendentes(db,str(servidor))['novos']==1

# cópia diária do banco (uma por dia e por computador) com os dados dentro
assert R.backup_diario(db,str(servidor),'PC-BRUNO')=='feito' and R.backup_diario(db,str(servidor),'PC-BRUNO')=='ja_feito'
z=next((servidor/'Backups').rglob('central_fiscal_PC-BRUNO.zip'))
with zipfile.ZipFile(z) as zz:
    zz.extract('central_fiscal.db',tmp/'bk'); assert sqlite3.connect(str(tmp/'bk'/'central_fiscal.db')).execute('SELECT COUNT(*) FROM documents').fetchone()[0]==9
assert R.backup_diario(db,str(fora),'PC')=='inacessivel'

# prazo de guarda: só avisa; apagar é uma chamada separada (precisa de confirmação) e só mexe no servidor
v=R.vencidos(str(servidor),12); assert v['arquivos']==1 and v['pastas']==[(emp[0].name,'2024','01')],v
assert len(list(rep.rglob('*.xml')))>=9
R.apagar_vencidos(db,str(servidor),12); assert not (emp[0]/'2024').exists() and R.resumo(db)['total']==9 and R.vencidos(str(servidor),12)['arquivos']==0
(emp[0]/'2026'/'09'/'NF-e'/'Saída'/('%044d'%4+'.xml')).write_bytes(b'<nfe n="4"/>')
assert R.verificar(db,str(servidor),amostra=1000)==[] and R.pendentes(db)==0       # o que foi apagado por prazo não volta para a fila

# restaurar: lista todos os XMLs do repositório com CNPJ e tipo
lista=R.listar_para_restaurar(str(servidor)); assert len(lista)>=8 and {c for c,_f,_p in lista}=={'11222333000181'} and {'nfe','nfse','cte'}<={f for _c,f,_p in lista}
shutil.rmtree(tmp,ignore_errors=True); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 repositório: OK')
