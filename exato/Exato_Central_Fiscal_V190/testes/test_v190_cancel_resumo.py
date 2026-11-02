"""V179: o RESUMO do evento de cancelamento (resEvento, o que a SEFAZ entrega ao destinatário) cancela a nota; o evento completo substitui o resumo;
resumo nunca vai para a pasta Eventos/ZIP; notas já guardadas são conferidas de novo."""
import os, sys, sqlite3, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_resev_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
EMIT='11222333000181'; DEST='45723174000110'; ch='35260911222333000181550010000000011000000100'
NS='xmlns="http://www.portalfiscal.inf.br/nfe"'
nfe=(f'<nfeProc {NS}><NFe><infNFe Id="NFe{ch}"><ide><mod>55</mod><nNF>1</nNF><serie>1</serie><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide><emit><CNPJ>{EMIT}</CNPJ><xNome>EMIT LTDA</xNome></emit>'
     f'<dest><CNPJ>{DEST}</CNPJ><xNome>DEST LTDA</xNome></dest><total><ICMSTot><vNF>100.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{ch}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
res=(f'<resEvento {NS}><chNFe>{ch}</chNFe><tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento><xEvento>Cancelamento homologado</xEvento><dhEvento>2026-09-11T09:00:00-03:00</dhEvento><nProt>135260000000001</nProt></resEvento>').encode()
ciencia=(f'<resEvento {NS}><chNFe>{ch}</chNFe><tpEvento>210210</tpEvento><nSeqEvento>1</nSeqEvento><nProt>135260000000002</nProt></resEvento>').encode()
sem_prot=res.replace(b'<nProt>135260000000001</nProt>',b'')
completo=(f'<procEventoNFe {NS}><evento><infEvento><chNFe>{ch}</chNFe><tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento></infEvento></evento><retEvento><infEvento><cStat>135</cStat><chNFe>{ch}</chNFe></infEvento></retEvento></procEventoNFe>').encode()
d=m._event_details(res); assert d['cancels'] and d['summary'] and d['key']==ch and d['type']=='110111',d
assert not m._event_details(ciencia)['cancels'] and m._event_details(ciencia)['summary']
assert not m._event_details(sem_prot)['cancels']
d=m._event_details(completo); assert d['cancels'] and not d['summary']
m.init_database(); m.db_register_company(EMIT,'EMIT LTDA')
def status():
    c=sqlite3.connect(m.DB_PATH); r=c.execute("SELECT status FROM documents WHERE access_key=? AND status<>'Evento'",(ch,)).fetchone(); c.close(); return r and r[0]
# 1) nota primeiro, resumo depois -> Cancelada
m.db_upsert_documents(EMIT,[{'xml':nfe,'family':'nfe','tipo':'nfeProc','nsu':1}]); assert status()=='Autorizado'
m.db_upsert_documents(EMIT,[{'xml':res,'family':'nfe','tipo':'resEvento','nsu':2}]); assert status()=='Cancelado',status()
# 2) só o resumo: aviso "sem evento completo" e nada de arquivo Eventos/ZIP
assert [k for _,k in m.db_canceladas_sem_evento(EMIT,'nfe')]==[ch]
assert m._zip_eventos(EMIT,[ch])==[]
# 3) o evento completo chega depois e substitui o resumo
m.db_upsert_documents(EMIT,[{'xml':completo,'family':'nfe','tipo':'procEventoNFe','nsu':3}])
c=sqlite3.connect(m.DB_PATH); n=c.execute("SELECT COUNT(*) FROM documents WHERE status='Evento' AND access_key=?",(ch,)).fetchone()[0]; c.close(); assert n==1,n
assert m.db_canceladas_sem_evento(EMIT,'nfe')==[] and len(m._zip_eventos(EMIT,[ch]))==1
# 4) o resumo chega ANTES da nota -> nasce cancelada
c=sqlite3.connect(m.DB_PATH); c.execute("DELETE FROM documents"); c.commit(); c.close()
m.db_upsert_documents(EMIT,[{'xml':res,'family':'nfe','tipo':'resEvento','nsu':1}]); m.db_upsert_documents(EMIT,[{'xml':nfe,'family':'nfe','tipo':'nfeProc','nsu':2}]); assert status()=='Cancelado'
# 5) passado: nota guardada como autorizada + resumo já guardado -> a conferência geral marca
c=sqlite3.connect(m.DB_PATH); c.execute("UPDATE documents SET status='Autorizado' WHERE status='Cancelado'"); c.commit(); c.close(); assert status()=='Autorizado'
assert m.db_reapply_all_cancellations()==1 and status()=='Cancelado' and m.db_reapply_all_cancellations()==0
# 6) manifestação (ciência) nunca cancela
c=sqlite3.connect(m.DB_PATH); c.execute("UPDATE documents SET status='Autorizado' WHERE status='Cancelado'"); c.execute("DELETE FROM documents WHERE status='Evento'"); c.commit(); c.close()
m.db_upsert_documents(EMIT,[{'xml':ciencia,'family':'nfe','tipo':'resEvento','nsu':5}]); assert status()=='Autorizado'
print('V179 cancel resumo OK')
