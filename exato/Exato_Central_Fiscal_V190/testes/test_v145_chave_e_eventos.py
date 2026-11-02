"""V145 — chave de acesso completa, eventos fora do lugar das notas e reparo do banco legado."""
import os, sys, sqlite3, tempfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v145_')
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as e
import central_client as c

CNPJ='11222333000181'
def key(n): return f'422609{CNPJ}55001{n:09d}1000001234'
def nfe(n,valor='150.00'):
    k=key(n)
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00">'
            f'<ide><mod>55</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{CNPJ}</CNPJ><xNome>EMPRESA TESTE LTDA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>CLIENTE</xNome></dest>'
            f'<total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total></infNFe></NFe>'
            f'<protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
def evento(n,tp='110111',cstat='135',seq=1):
    k=key(n)
    return (f'<procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00"><evento><infEvento Id="ID{tp}{k}{seq:02d}"><chNFe>{k}</chNFe>'
            f'<tpEvento>{tp}</tpEvento><nSeqEvento>{seq}</nSeqEvento></infEvento></evento>'
            f'<retEvento><infEvento><cStat>{cstat}</cStat><chNFe>{k}</chNFe><tpEvento>{tp}</tpEvento></infEvento></retEvento></procEventoNFe>').encode()
def rows(sql,*a):
    conn=sqlite3.connect(e.DB_PATH); out=conn.execute(sql,a).fetchall(); conn.close(); return out
def doc(xml,tipo,nsu): return {'xml':xml,'tipo':tipo,'nsu':str(nsu),'family':'nfe','actor_code':'1','actor_label':'Emitente / Saída'}

e._prepare_persistent_storage(); e.init_database()

# 1) chave completa
assert e._parse_document_metadata(nfe(1),CNPJ,'nfe')['chave']==key(1)
assert e._extract_access_key_from_xml(b'<NFe><infNFe Id="NFe'+key(1).encode()+b'"/></NFe>')==key(1)
assert e.db_upsert_documents(CNPJ,[doc(nfe(1),'nfeProc',1)])==(1,0)
assert rows('SELECT access_key,status FROM documents')==[(key(1),'Autorizado')]

# 2) cancelamento depois da nota: nota vira Cancelado, evento não conta como documento
assert e.db_upsert_documents(CNPJ,[doc(evento(1),'procEventoNFe',2)])==(0,0)
assert rows("SELECT status FROM documents WHERE doc_type<>'Evento'")==[('Cancelado',)]
assert rows("SELECT COUNT(*) FROM documents WHERE status='Evento'")==[(1,)]
assert e.db_document_count(CNPJ)==1 and e.db_get_stats(CNPJ)['total']==1 and e.db_get_stats(CNPJ)['authorized']==0
assert e.db_upsert_documents(CNPJ,[doc(evento(1),'procEventoNFe',2)])==(0,0)      # repetido não duplica
assert rows("SELECT COUNT(*) FROM documents")==[(2,)]

# 3) cancelamento ANTES da nota: o XML da nota continua sendo gravado
assert e.db_upsert_documents(CNPJ,[doc(evento(2),'procEventoNFe',3)])==(0,0)
assert e.db_upsert_documents(CNPJ,[doc(nfe(2),'nfeProc',4)])==(1,0)
r=rows("SELECT status,number,length(xml) FROM documents WHERE access_key=? AND status<>'Evento'",key(2))
assert r==[('Cancelado','2',len(nfe(2)))], r

# 4) carta de correção e cancelamento não homologado não cancelam
e.db_upsert_documents(CNPJ,[doc(nfe(3),'nfeProc',5),doc(evento(3,'110110'),'procEventoNFe',6),doc(evento(3,'110111','573',2),'procEventoNFe',7)])
assert rows("SELECT status FROM documents WHERE access_key=? AND status<>'Evento'",key(3))==[('Autorizado',)]
assert rows("SELECT COUNT(*) FROM documents WHERE access_key=? AND status='Evento'",key(3))==[(2,)]

# 5) auditoria casa pela chave mesmo sem série no relatório do SAT
sat=[{'numero':'3','data':'2026-09-10','valor':Decimal('150.00'),'chave':key(3),'serie':'','situacao':'Autorizada','tipo_documento':'NF-e','operacao':'Saída'}]
res=e.audit_sat_excel_against_xml(CNPJ,sat,'2026-09-01','2026-09-30',family='nfe')
assert len(res['matched'])==1 and not res['sat_only'], (len(res['matched']),len(res['sat_only']))

# 6) relatório por período enxerga o cancelamento
payload=e.db_load_documents_as_payload(CNPJ,date_from='2026-09-01',date_to='2026-09-30',include_events=True)
assert [d['status'] for d in payload][:3]==['Autorizado','Cancelado','Cancelado'] or sorted(d['status'] for d in payload if d['status']!='Evento')==['Autorizado','Cancelado','Cancelado']
assert e._build_report_cancel_map(payload)=={key(1),key(2)}
assert all(d['status']!='Evento' for d in e.db_load_documents_as_payload(CNPJ,date_from='2026-09-01',date_to='2026-09-30'))

# 7) reparo de um banco gravado pela V144 (chave com 41 dígitos e evento como "NF-e Autorizado")
conn=sqlite3.connect(e.DB_PATH)
for t in ('documents','document_sources','document_exports'): conn.execute(f'DELETE FROM {t}')
now='2026-09-20T10:00:00'
def legacy(doc_id,k,number,issued,value,xml):
    conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (doc_id,CNPJ,'nfe','NF-e','Saída',number,'1' if number else '',issued,value,'Autorizado',k,'1',sqlite3.Binary(xml),now,now))
for n in (10,11):
    legacy(f'{CNPJ}|{key(n)[:41]}',key(n)[:41],str(n),'2026-09-10T10:00:00-03:00','150.00',nfe(n))
    conn.execute("INSERT INTO document_exports(doc_id,destination_root,exported_path,exported_at,xml_sha256) VALUES(?,?,?,?,?)",(f'{CNPJ}|{key(n)[:41]}','c:\\saida','',now,''))
    conn.execute("INSERT INTO document_sources(cnpj,doc_id,family,actor_code,actor_label,source_nsu,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?)",(CNPJ,f'{CNPJ}|{key(n)[:41]}','nfe','1','Emitente / Saída','1',now,now))
legacy(f'{CNPJ}|{key(10)}',key(10),'','','0.00',evento(10))          # cancelamento da nota 10, gravado como nota
conn.commit(); conn.close()
state=e._read_data_state(); state.pop('v145_index_repair',None); e._write_data_state(state)
assert e.db_document_count(CNPJ)==3                                   # era assim que a V144 contava
out=e.repair_document_index_v145()
assert (out['keys_fixed'],out['events_fixed'],out['cancelled'],out['unresolved'])==(2,1,1,0), out
assert out['backup'] and Path(out['backup']).exists()
assert sorted(rows("SELECT doc_id,access_key,status FROM documents WHERE status<>'Evento'"))==[(f'{CNPJ}|{key(10)}',key(10),'Cancelado'),(f'{CNPJ}|{key(11)}',key(11),'Autorizado')]
assert rows("SELECT doc_type,status,access_key FROM documents WHERE status='Evento'")==[('Evento','Evento',key(10))]
assert sorted(x[0] for x in rows('SELECT doc_id FROM document_exports'))==[f'{CNPJ}|{key(10)}',f'{CNPJ}|{key(11)}']
assert sorted(x[0] for x in rows('SELECT doc_id FROM document_sources'))==[f'{CNPJ}|{key(10)}',f'{CNPJ}|{key(11)}']
assert e.db_document_count(CNPJ)==2
assert all(len(x[0])==len(nfe(10)) for x in rows("SELECT xml FROM documents WHERE status<>'Evento'"))   # XML intacto
assert e.repair_document_index_v145()['skipped'] is True              # segunda execução não faz nada
assert e.db_upsert_documents(CNPJ,[doc(nfe(10),'nfeProc',9)])==(0,1)  # nova captura reconhece a nota já existente

# 8) inicialização automática do servidor: comando montado sem erro de import
assert '--central-server' in c._server_start_command(8765)
print('V145 chave e eventos: OK')
