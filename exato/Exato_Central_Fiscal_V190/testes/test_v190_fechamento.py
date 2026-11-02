"""V174: fechamento do mês no Repositório (PDF + ZIPs + marcador), revisão, reserva entre computadores, índice e ZIP retroativo."""
import os, sys, sqlite3, tempfile, zipfile, json, time, re
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_fech_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_repositorio as R, exato_fechamento as F, exato_zip_importacao as Z
from test_v190_nfse_core import nfse_xml, chave as chave_nfse, PREST
tmp=Path(tempfile.mkdtemp(prefix='exato_v174_fech_srv_')); servidor=tmp/'servidor'; servidor.mkdir(); db=str(tmp/'banco.db')
CNPJ='11222333000181'
conn=sqlite3.connect(db)
conn.execute("CREATE TABLE companies(cnpj TEXT PRIMARY KEY,name TEXT)")
conn.execute("""CREATE TABLE documents(doc_id TEXT PRIMARY KEY,cnpj TEXT,family TEXT,doc_type TEXT,direction TEXT,number TEXT,series TEXT,issued_at TEXT,value TEXT,status TEXT,access_key TEXT,source_nsu TEXT,xml BLOB,first_seen_at TEXT,last_seen_at TEXT)""")
conn.execute("INSERT INTO companies VALUES(?,?)",(CNPJ,'ELETROTAK MANUTENCAO LTDA')); conn.execute("INSERT INTO companies VALUES(?,?)",(PREST,'PRESTADORA SERVICOS LTDA'))
vista=(datetime.now()-timedelta(days=20)).isoformat(timespec='seconds')
def doc(i,fam,direcao,mes='2026-07',status='Autorizado',valor='100.00',cnpj=CNPJ,xml=None,chave=None,visto=None):
    conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (f'd{i}',cnpj,fam,{'nfe':'NF-e','nfce':'NFC-e','cte':'CT-e','nfse':'NFS-e'}[fam] if status!='Evento' else 'Evento',direcao,str(i),'1',f'{mes}-10T10:00:00',valor,status,chave or ('%044d'%i),xml or f'<x n="{i}"/>'.encode(),visto or vista,visto or vista))
doc(1,'nfe','Saída'); doc(2,'nfe','Saída',status='Cancelado'); doc(3,'nfe','Entrada',valor='50.00'); doc(4,'nfce','Saída',valor='30.00'); doc(5,'cte','Entrada',valor='80.00')
doc(6,'nfe','Saída',status='Evento',chave='%044d'%2)
for k in (1,2): doc(10+k,'nfse','Saída',cnpj=PREST,xml=nfse_xml(k,prest=PREST,toma='98765432000110',valor='200.00',dh='2026-07-%02dT10:00:00-03:00'%(5+k)),chave=chave_nfse(k))
doc(30,'nfe','Saída',mes=datetime.now().strftime('%Y-%m'),visto=datetime.now().isoformat(timespec='seconds'))       # mês atual: nunca fecha
conn.commit(); conn.close()
hoje=datetime.now()

# nada fecha enquanto algo não foi copiado para o servidor
assert F.candidatos(db)==[]
assert R.copiar_pendentes(db,str(servidor))['ok']
cands=F.candidatos(db); assert [(c['cnpj'],c['mes']) for c in cands]==[(CNPJ,'2026-07'),(PREST,'2026-07')],cands          # só meses encerrados
assert cands[0]['notas']==5 and cands[0]['assinatura'].split('|')[2]=='1' and cands[0]['assinatura'].split('|')[3]=='1',cands[0]      # 5 notas, 1 cancelada, 1 evento
# nota nova há pouco tempo: o mês ainda não está "quieto"
conn=sqlite3.connect(db); conn.execute("UPDATE documents SET first_seen_at=? WHERE doc_id='d1'",((hoje-timedelta(days=2)).isoformat(timespec='seconds'),)); conn.commit(); conn.close()
assert [c['cnpj'] for c in F.candidatos(db)]==[PREST]; assert [c['cnpj'] for c in F.candidatos(db,forcar=True)]==[CNPJ,PREST]       # "Fechar agora" ignora a espera
conn=sqlite3.connect(db); conn.execute("UPDATE documents SET first_seen_at=? WHERE doc_id='d1'",(vista,)); conn.commit(); conn.close()

# fechar: PDF do mês, ZIPs por tipo/movimentação, ZIP de eventos e marcador
estado={}; coberto_chamadas=[]
r=F.fechar_pendentes(db,str(servidor),estado,coberto=lambda c,m:(coberto_chamadas.append((c,m)) or True))
assert r['fechados']==2 and not r['erros'] and r['empresas']=={CNPJ,PREST},r
emp=[p for p in (servidor/'Repositório').iterdir() if CNPJ in p.name][0]; fech=emp/'2026'/'07'/'Fechamento'
nomes=sorted(p.name for p in fech.iterdir()); print(nomes)
assert 'Fechamento 2026-07.pdf' in nomes and '.fechamento.json' in nomes and '.fechando' not in nomes and not [n for n in nomes if n.endswith('.tmp')],nomes
for esperado in (f'{CNPJ}_2026-07_NF-e_Saída.zip',f'{CNPJ}_2026-07_NF-e_Entrada.zip',f'{CNPJ}_2026-07_NFC-e_Saída.zip',f'{CNPJ}_2026-07_CT-e_Entrada.zip',f'{CNPJ}_2026-07_Eventos-NF-e.zip'): assert esperado in nomes,(esperado,nomes)
with zipfile.ZipFile(fech/f'{CNPJ}_2026-07_NF-e_Saída.zip') as z: assert sorted(z.namelist())==['%044d.xml'%1,'%044d.xml'%2],z.namelist()
assert (fech/'Fechamento 2026-07.pdf').read_bytes()[:4]==b'%PDF'
marca=json.loads((fech/'.fechamento.json').read_text(encoding='utf-8')); assert marca['revisao']==0 and marca['notas']==5 and marca['cnpj']==CNPJ and len(marca['historico'])==1
fech2=[p for p in (servidor/'Repositório').iterdir() if PREST in p.name][0]/'2026'/'07'/'Fechamento'; n2=sorted(p.name for p in fech2.iterdir())
assert 'Fechamento 2026-07 - NFS-e.pdf' in n2 and f'{PREST}_2026-07_NFS-e_Prestados.zip' in n2 and 'Fechamento 2026-07.pdf' not in n2,n2           # empresa só de serviço: só o relatório de NFS-e
assert not list((servidor/'Repositório').rglob('*.tmp'))

# repetir não faz nada (memória local) e, sem a memória (outro computador), reconhece pelo marcador
mt=(fech/'Fechamento 2026-07.pdf').stat().st_mtime_ns; coberto_chamadas.clear()
r=F.fechar_pendentes(db,str(servidor),estado); assert r['fechados']==0 and r['conferidos']==0
r=F.fechar_pendentes(db,str(servidor),{}); assert r['fechados']==0 and r['conferidos']==2 and (fech/'Fechamento 2026-07.pdf').stat().st_mtime_ns==mt

# mês fechado por outro computador em andamento: este espera (reserva recente) e uma reserva esquecida é assumida
cand=[c for c in F.candidatos(db) if c['cnpj']==CNPJ][0]
(fech/'.fechando').write_text('OUTRO-PC'); (fech/'.fechamento.json').rename(fech/'guardado.json')
assert F.fechar_mes(db,str(servidor),cand)['situacao']=='ocupado' and (fech/'.fechando').exists()
velho=time.time()-3600; os.utime(fech/'.fechando',(velho,velho)); (fech/'guardado.json').rename(fech/'.fechamento.json')
assert F.fechar_mes(db,str(servidor),cand)['situacao']=='igual'        # nada a fazer (a reserva velha fica; é assumida quando houver o que gerar)

# nota atrasada depois do fechamento: REVISÃO — os arquivos antigos ficam, os novos têm a data da revisão
conn=sqlite3.connect(db); conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES('d99',?,'nfe','NF-e','Saída','99','1','2026-07-30T10:00:00','10.00','Autorizado',?,?,?,?)",(CNPJ,'%044d'%99,b'<x n="99"/>',vista,vista)); conn.commit(); conn.close()
assert F.candidatos(db)==[] or all(c['cnpj']!=CNPJ for c in F.candidatos(db))              # a nota nova ainda não está no servidor: espera a cópia
R.copiar_pendentes(db,str(servidor)); assert (fech/'.fechando').exists(); antes=(fech/'Fechamento 2026-07.pdf').read_bytes()
r=F.fechar_pendentes(db,str(servidor),estado); assert r['revisados']==1 and r['fechados']==0,r
dia=datetime.now().strftime('%Y-%m-%d'); nomes=sorted(p.name for p in fech.iterdir()); assert '.fechando' not in nomes        # reserva esquecida foi assumida e liberada
assert 'Fechamento 2026-07.pdf' in nomes and f'Fechamento 2026-07 (revisado {dia}).pdf' in nomes and f'{CNPJ}_2026-07_NF-e_Saída (revisado {dia}).zip' in nomes,nomes
assert (fech/'Fechamento 2026-07.pdf').read_bytes()==antes                                       # nada foi sobrescrito
with zipfile.ZipFile(fech/f'{CNPJ}_2026-07_NF-e_Saída (revisado {dia}).zip') as z: assert len(z.namelist())==3
marca=json.loads((fech/'.fechamento.json').read_text(encoding='utf-8')); assert marca['revisao']==1 and len(marca['historico'])==2 and marca['fechado_em']<=marca['historico'][1]['em']

# índice do servidor: mês fechado e quantas revisões
ind=R.atualizar_indice(db,str(servidor),computador='PC-A'); fe=R.indice_fechamentos(ind)
assert fe[(CNPJ,'2026-07')]==(True,1) and fe[(PREST,'2026-07')]==(True,0),fe
assert R.indice_totais(ind)['faltam']==0 and R.indice_totais(ind)['xmls']==10                      # arquivos do Fechamento não contam como XML

# servidor fora do ar: erro claro, nada quebra
c2=dict(cand,assinatura='x'); r=F.fechar_mes(db,str(tmp/'nao_existe'),c2); assert r['situacao']=='erro' and r['erro']

# ZIP retroativo: meses já salvos nas pastas dos clientes (antes da V168)
cli=tmp/'clientes'
for direc,tipo,qtd in (('Saída','NF-e',3),('Entrada','NFC-e',2),('Entrada','CT-e',2),('Prestados','NFS-e',2)):
    p=cli/f'Empresa_{CNPJ}'/'2026'/'08 - Agosto'/direc/tipo; p.mkdir(parents=True)
    for i in range(qtd): (p/('%044d.xml'%i)).write_bytes(b'<x n="%d"/>'%i)
(cli/'SEM CNPJ'/'2026'/'08 - Agosto'/'Saída'/'NF-e').mkdir(parents=True); ((cli/'SEM CNPJ'/'2026'/'08 - Agosto'/'Saída'/'NF-e')/'a.xml').write_bytes(b'<a/>')
vistos=[]; r=Z.gerar_todos(str(cli),progresso=lambda x:vistos.append(x)); assert r['criados']==4 and r['pastas']==4 and r['sem_cnpj']==1 and not r['erros'] and vistos,r
zs=sorted(p.name for p in cli.rglob('*.zip')); assert zs==[f'{CNPJ}_2026-08_CT-e_Entrada.zip',f'{CNPJ}_2026-08_NF-e_Saída.zip',f'{CNPJ}_2026-08_NFC-e_Entrada.zip',f'{CNPJ}_2026-08_NFS-e_Prestados.zip'],zs
r=Z.gerar_todos(str(cli)); assert r['criados']==0 and r['iguais']==4 and r['atualizados']==0        # repetir não refaz nada
assert len(list(cli.rglob('*.xml')))==10
print('V174 fechamento OK')
