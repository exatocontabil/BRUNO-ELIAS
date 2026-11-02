"""V176: situação da busca por empresa e tipo (Em dia / Atrasado / Ainda não buscado / Sem notas), filtros e cobertura do fechamento."""
import os, sys, sqlite3, tempfile
from datetime import date, timedelta, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v176_sit_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_situacao_busca as S, exato_cobertura as C, exato_fechamento as F
db=tempfile.mktemp(suffix='.db'); c=sqlite3.connect(db)
c.execute("CREATE TABLE companies(cnpj TEXT PRIMARY KEY,name TEXT)")
c.execute("""CREATE TABLE documents(doc_id TEXT PRIMARY KEY,cnpj TEXT,family TEXT,doc_type TEXT,direction TEXT,number TEXT,series TEXT,issued_at TEXT,value TEXT,status TEXT,access_key TEXT,source_nsu TEXT,xml BLOB,first_seen_at TEXT,last_seen_at TEXT)""")
A,B,Cc='11222333000181','55444333000122','12345678000195'
for cn,nm in ((A,'ALFA LTDA'),(B,'BETA LTDA'),(Cc,'GAMA LTDA')): c.execute("INSERT INTO companies VALUES(?,?)",(cn,nm))
hoje=date(2026,10,7); iso=lambda d:d.isoformat()
def doc(i,cn,fam,visto,status='Autorizado'):
    c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,status,xml,first_seen_at,last_seen_at,issued_at) VALUES(?,?,?,?,?,?,?,?,?)",(f'd{i}',cn,fam,fam,status,b'<x/>',iso(visto),iso(visto),iso(visto)))
doc(1,A,'nfe',date(2026,10,6)); doc(2,A,'cte',date(2026,3,5))      # CT-e visto pela última vez em março: NÃO pode deixar a empresa atrasada
doc(3,B,'nfe',date(2026,9,20)); doc(4,B,'cte',date(2026,9,20))      # atrasada (17 dias)
c.commit(); c.close()
cfg={}
C.registrar(cfg,A,'nfse',ate=date(2026,10,6))                         # buscou NFS-e e voltou vazio
L={l['cnpj']:l for l in S.linhas(db,cfg,None,hoje)}
a=L[A]['celulas']; assert a['nfe']['estado']=='em_dia' and a['nfe']['notas']==1 and a['cte']['estado']=='em_dia' and a['nfe']['detalhe']=='última nota 06/10 • 1 notas\nbuscado até 06/10',a['nfe']          # mostra a data da ÚLTIMA NOTA e a data da busca; o CT-e acompanha a busca do grupo
assert a['cte']['ultima_nota']==date(2026,3,5)            # CT-e acompanha a busca do grupo
assert a['nfce']['estado']=='sem_notas' and a['nfce']['detalhe']=='buscado até 06/10',a['nfce']                              # nenhuma NFC-e, mas a busca passou
assert a['nfse']['estado']=='sem_notas',a['nfse']                                                                           # buscado e vazio
assert L[A]['resumo']=='em_dia' and L[A]['pendentes']==[]
b=L[B]['celulas']; assert b['nfe']['estado']=='atrasado' and b['nfe']['dias']==17 and b['nfe']['texto']=='Atrasado 17 dia(s)' and b['nfe']['detalhe']=='última nota 20/09 • 1 notas\nbuscado até 20/09' and b['nfe']['ultima_nota']==date(2026,9,20),b['nfe']
assert L[B]['resumo']=='nunca' and 'nfse' in L[B]['pendentes'] and 'nfe' in L[B]['pendentes']
g=L[Cc]; assert all(x['estado']=='nunca' for x in g['celulas'].values()) and g['resumo']=='nunca'                       # empresa sem nada
# limite de 3 dias: 3 dias ainda é "em dia", 4 é atraso
C.registrar(cfg,B,'nfe',ate=hoje-timedelta(days=3)); L=S.linhas(db,cfg,None,hoje); assert [l for l in L if l['cnpj']==B][0]['celulas']['nfe']['estado']=='em_dia'
C.registrar(cfg,B,'nfe',ate=hoje-timedelta(days=4)); L=S.linhas(db,cfg,None,hoje); assert [l for l in L if l['cnpj']==B][0]['celulas']['nfe']['estado']=='atrasado'
t=S.totais(S.linhas(db,cfg,None,hoje)); assert t['empresas']==3 and t['em_dia']==1 and t['nunca']==2 and t['atraso']==1,t          # BETA: atrasada e com NFS-e nunca buscada (conta nos dois)
# filtros
L=S.linhas(db,cfg,None,hoje)
assert [l['nome'] for l in S.filtrar(L,'alfa')]==['ALFA LTDA'] and [l['nome'] for l in S.filtrar(L,'55.444')]==['BETA LTDA']
assert [l['nome'] for l in S.filtrar(L,'','Só em dia')]==['ALFA LTDA'] and {l['nome'] for l in S.filtrar(L,'','Só não buscadas')}=={'BETA LTDA','GAMA LTDA'}
assert [l['nome'] for l in S.filtrar(L,'','Só atrasadas')]==['BETA LTDA'] and {l['nome'] for l in S.filtrar(L,'','Só com pendência')}=={'BETA LTDA','GAMA LTDA'}
assert {l['nome'] for l in S.filtrar(L,'','Todas','NFS-e')}=={'ALFA LTDA','BETA LTDA','GAMA LTDA'} and [l['nome'] for l in S.filtrar(L,'','Só em dia','NF-e')]==['ALFA LTDA']
# cobertura do fechamento: o tipo raro (CT-e de março) não trava; sem informação = nada a dizer
assert S.cobertura_empresa(db,{},None,A)==date(2026,10,6) and S.cobertura_empresa(db,{},None,Cc) is None
# fechamento: motivo de cada mês (em português) e candidatos
conn=sqlite3.connect(db); conn.execute("CREATE TABLE IF NOT EXISTS repositorio_copias(doc_id TEXT PRIMARY KEY, caminho TEXT, sha256 TEXT, copiado_em TEXT, tentativas INTEGER DEFAULT 0, ultima_tentativa TEXT, erro TEXT, conflito INTEGER DEFAULT 0, removido INTEGER DEFAULT 0)")
agora=datetime(2026,10,7,12,0)
conn.execute("UPDATE documents SET issued_at='2026-07-10T10:00:00', first_seen_at='2026-07-15T10:00:00' WHERE doc_id='d1'"); conn.execute("UPDATE documents SET issued_at='2026-08-10T10:00:00', first_seen_at='2026-10-05T10:00:00' WHERE doc_id='d2'")
conn.execute("UPDATE documents SET issued_at='2026-06-10T10:00:00', first_seen_at='2026-06-12T10:00:00' WHERE doc_id='d3'"); conn.execute("UPDATE documents SET issued_at='2026-05-10T10:00:00', first_seen_at='2026-05-12T10:00:00' WHERE doc_id='d4'")
conn.execute("INSERT INTO repositorio_copias(doc_id,copiado_em) VALUES('d1','2026-07-16'),('d3','2026-06-13')"); conn.commit(); conn.close()
M=F.motivos(db,5,agora,coberto=lambda cn,mes:cn!=B)
assert M[(A,'2026-07')]=='' ,M                                                                  # tudo copiado, quieto há mais de 5 dias, buscado: pode fechar
assert M[(A,'2026-08')].startswith('Faltam 1 documento(s) no servidor'),M[(A,'2026-08')]
assert M[(B,'2026-06')]=='A busca ainda não passou do fim do mês',M[(B,'2026-06')]
assert 'Faltam' in M[(B,'2026-05')]
conn=sqlite3.connect(db); conn.execute("INSERT INTO repositorio_copias(doc_id,copiado_em) VALUES('d2','2026-10-06')"); conn.commit(); conn.close()
M=F.motivos(db,5,agora); assert M[(A,'2026-08')].startswith('Chegou nota nova em 05/10: fecha em 10/10'),M[(A,'2026-08')]
cand=sorted((x['cnpj'],x['mes']) for x in F.candidatos(db,5,agora)); assert cand==sorted([(A,'2026-07'),(B,'2026-06')]),cand
assert sorted((x['cnpj'],x['mes']) for x in F.candidatos(db,5,agora,forcar=True))==sorted([(A,'2026-07'),(A,'2026-08'),(B,'2026-06')])        # "Fechar agora" ignora a espera
print('V176 situação da busca OK')
