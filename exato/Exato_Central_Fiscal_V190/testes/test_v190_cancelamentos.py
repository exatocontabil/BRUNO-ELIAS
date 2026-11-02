"""V177: nota cancelada e evento de cancelamento seguem JUNTOS (arquivo ao lado + ZIP); evento nunca vira nota; portal lê a situação "cancelada"."""
import os, sys, sqlite3, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v177_canc_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m, exato_nfse_portal as P, exato_zip_importacao as Z
from test_v190_nfse_core import nfse_xml, chave, PREST
# ---- portal: a lista traz o ícone "NFS-e cancelada"; só conta cancelada/cancelado, nunca o menu "Cancelar NFS-e"
k1,k2,k3='1'*50,'2'*50,'3'*50
html=f'''<table><tr><th>Situação</th></tr>
<tr><td><a href="/Notas/Download/NFSe/{k1}">x</a></td><td><i title="NFS-e cancelada"></i></td><td><a>Cancelar NFS-e</a></td></tr>
<tr><td><a href="/Notas/Download/NFSe/{k2}">x</a></td><td><i title="NFS-e emitida"></i></td><td><a>Cancelar NFS-e</a></td></tr>
<tr><td><a href="/Notas/Download/NFSe/{k3}">x</a></td><td data-original-title="NFS-e cancelada"></td></tr></table>'''
sit=P.parse_situacoes(html); assert sit=={k1:'Cancelada',k2:'Autorizada',k3:'Cancelada'},sit
assert P.parse_situacoes('<html></html>')=={} and P.parse_situacoes('')=={}
# ---- banco: nota autorizada vira cancelada pelo portal; sem evento = aviso
m.init_database(); m.db_register_company(PREST,'PRESTADORA SERVICOS LTDA')
notas=[{'xml':nfse_xml(i,prest=PREST,toma='98765432000110',valor='100.00',dh='2026-09-%02dT10:00:00-03:00'%(5+i)),'chave':chave(i),'tipo_documento':'NFSE','tipo_evento':'','nsu':0} for i in range(1,4)]
r=m.db_upsert_nfse_items(PREST,notas); assert r['new']==3
ids=m.db_mark_nfse_cancelled(PREST,[chave(2)]); assert len(ids)==1 and m.db_mark_nfse_cancelled(PREST,[chave(2)])==[]          # idempotente
assert [k for _,k in m.db_canceladas_sem_evento(PREST,'nfse')]==[chave(2)]
# evento de cancelamento guardado no banco
c=sqlite3.connect(m.DB_PATH)
evxml=b'<evento tipo="cancelamento" chave="x"/>'
c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,status,access_key,xml,first_seen_at,last_seen_at,issued_at,value) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(f'{PREST}|{chave(2)}|EV|101101|1',PREST,'nfse','Evento','','Evento',chave(2),evxml,'x','x','','0.00')); c.commit(); c.close()
assert m.db_canceladas_sem_evento(PREST,'nfse')==[]
# ---- salvar: a nota cancelada vai com o evento ao lado; o evento NUNCA é gravado como nota
rows=[r_ for r_ in m.db_list_documents(cnpj=PREST,family='nfse',limit=100)]; assert any(x['status']=='Evento' for x in rows) and any(x['status']=='Cancelado' for x in rows)
dest=Path(tempfile.mkdtemp(prefix='exato_v177_cli_')); saved,erros=m.save_documents_any(rows,str(dest),PREST,{'zip_importacao':True},None); assert not erros,erros
xmls=sorted(dest.rglob('*.xml')); notas_xml=[p for p in xmls if p.parent.name=='NFS-e']; ev=[p for p in xmls if p.parent.name=='Eventos']
assert len(notas_xml)==3 and len(ev)==1,[str(p.relative_to(dest)) for p in xmls]
assert ev[0].name.startswith(f'evento_{chave(2)}_') and ev[0].read_bytes()==evxml and ev[0].parent.parent.name=='NFS-e'          # ao lado da nota, na subpasta Eventos
zp=next(dest.rglob('*.zip')); z=zipfile.ZipFile(zp); nomes=z.namelist(); assert len(nomes)==4 and any(n.startswith('evento_') for n in nomes),nomes     # 3 notas + 1 evento no ZIP
# repetir não duplica nem refaz
saved,erros=m.save_documents_any(rows,str(dest),PREST,{'zip_importacao':True},None); assert len(list((ev[0].parent).glob('*.xml')))==1
# ZIP desligado: o evento continua indo para a pasta Eventos
dest2=Path(tempfile.mkdtemp(prefix='exato_v177_cli2_')); m.save_documents_any(rows,str(dest2),PREST,{'zip_importacao':False},None)
assert len(list(dest2.rglob('Eventos/*.xml')))==1 and not list(dest2.rglob('*.zip'))
# ---- NF-e: o evento que chega junto com as notas não vira nota (antes: gravado como nota na pasta errada)
EMIT='11222333000181'; DEST='99888777000166'; ch='35260911222333000181550010000000011000000100'
nfe=('<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe%s"><ide><mod>55</mod><nNF>1</nNF><serie>1</serie><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide><emit><CNPJ>%s</CNPJ><xNome>EMIT</xNome></emit><dest><CNPJ>%s</CNPJ><xNome>DEST</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe></nfeProc>'%(ch,EMIT,DEST)).encode()
evn=('<procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe"><evento><infEvento><chNFe>%s</chNFe><tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento></infEvento></evento></procEventoNFe>'%ch).encode()
m.db_register_company(EMIT,'EMIT LTDA'); c=sqlite3.connect(m.DB_PATH)
c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at,value) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('n1',EMIT,'nfe','NF-e','Saída','1','2026-09-10T10:00:00','Cancelado',ch,nfe,'x','x','10.00'))
c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,issued_at,status,access_key,xml,first_seen_at,last_seen_at,value) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(f'{EMIT}|{ch}|EV|110111|1',EMIT,'nfe','Evento','','','Evento',ch,evn,'x','x','0.00')); c.commit(); c.close()
docs=[{'xml':nfe,'family':'nfe','chave':ch,'cnpj':EMIT,'status':'Cancelado','data':'2026-09-10'},{'xml':evn,'family':'nfe','chave':ch,'cnpj':EMIT,'status':'Evento','doc_type':'Evento','data':'2026-09-10'}]
d3=Path(tempfile.mkdtemp(prefix='exato_v177_nfe_')); sv,er=m.save_documents_any(docs,str(d3),EMIT,{'zip_importacao':True},None,generate_companion_pdf=False); assert not er,er
todos=sorted(str(p.relative_to(d3)) for p in d3.rglob('*.xml')); assert len(todos)==2 and sum('Eventos' in t for t in todos)==1 and sum('Saída' in t and 'Eventos' not in t for t in todos)==1,todos      # só a nota em Saída/NF-e + o evento em Eventos
assert not any('Entrada' in t for t in todos)
# ---- meses já salvos: "Gerar ZIPs dos meses já salvos" também grava os eventos que faltam
import shutil
for p in dest.rglob('Eventos'): shutil.rmtree(p)
for p in dest.rglob('*.zip'): p.unlink()
res=Z.gerar_todos(str(dest),eventos_fn=m._zip_eventos,resolver_cnpj=m._cnpj_pela_pasta); assert res['criados']==1 and len(list(dest.rglob('Eventos/*.xml')))==1,res
# ---- eventos nunca entram na lista de notas a salvar
assert [d['status'] for d in m._sem_eventos(docs)]==['Cancelado']
print('V177 cancelamentos OK')
