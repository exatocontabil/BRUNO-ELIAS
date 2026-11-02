"""V180: a Auditoria reconhece nota CANCELADA (o SAT só traz autorizadas): fora de "sem correspondência", com a coluna Documento, e permite marcar à mão."""
import os, sys, tempfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_aud_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as e
CNPJ='11222333000181'
def key(n): return f'422609{CNPJ}55001{n:09d}1000001234'
def nfe(n,valor):
    k=key(n)
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{CNPJ}</CNPJ><xNome>EMPRESA TESTE LTDA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>CLIENTE</xNome></dest><total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total></infNFe></NFe>'
            f'<protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
def evento(n):
    k=key(n); return (f'<procEventoNFe xmlns="http://www.portalfiscal.inf.br/nfe"><evento><infEvento><chNFe>{k}</chNFe><tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento></infEvento></evento><retEvento><infEvento><cStat>135</cStat><chNFe>{k}</chNFe></infEvento></retEvento></procEventoNFe>').encode()
def doc(x,t,n): return {'xml':x,'tipo':t,'nsu':str(n),'family':'nfe','actor_code':'1','actor_label':'Emitente / Saída'}
e._prepare_persistent_storage(); e.init_database(); e.db_register_company(CNPJ,'EMPRESA TESTE LTDA')
# 1,2 autorizadas (no SAT); 3 cancelada (cancelamento recebido, fora do SAT); 4 autorizada que o SAT não traz e o Exato ainda não sabe que foi cancelada
e.db_upsert_documents(CNPJ,[doc(nfe(1,'100.00'),'nfeProc',1),doc(nfe(2,'200.00'),'nfeProc',2),doc(nfe(3,'217.00'),'nfeProc',3),doc(evento(3),'procEventoNFe',4),doc(nfe(4,'50.00'),'nfeProc',5)])
sat=[{'numero':str(n),'data':'2026-09-10','valor':Decimal(v),'chave':key(n),'serie':'1','situacao':'Autorizada','tipo_documento':'NF-e','operacao':'Saída'} for n,v in ((1,'100.00'),(2,'200.00'))]
res=e.audit_sat_excel_against_xml(CNPJ,sat,'2026-09-01','2026-09-30',family='nfe')
assert {r['numero'] for r in res['xml_only']}=={'3','4'} and res['xml_count']==4          # antes: as duas aparecem como sem correspondência
e._audit_separar_cancelados(res,CNPJ)
assert [r['numero'] for r in res['xml_only']]==['4'] and [r['numero'] for r in res['cancelled_xml']]==['3']
assert res['xml_count']==3 and res['xml_total']==Decimal('350.00') and res['xml_only_value']==Decimal('50.00'),(res['xml_count'],res['xml_total'],res['xml_only_value'])
rows={r['numero']:r for r in res['display_rows']}
assert e._audit_status_label_for_row(rows['3'])=='Cancelada' and rows['3']['situacao_doc']=='Cancelada' and 'CANCELADA' in rows['3']['observacao'] and rows['3']['valor_sat'] is None
assert e._audit_status_label_for_row(rows['4'])=='Sem correspondência' and 'só traz notas autorizadas' in rows['4']['observacao'] and rows['4']['situacao_doc']=='Autorizada'
assert rows['1']['situacao_doc']=='Autorizada' and e._audit_status_label_for_row(rows['1'])=='Conforme'
ai=e.analyze_audit_result(res,'EMPRESA TESTE LTDA','2026-09-01','2026-09-30'); assert ai['counts']['xml_only']==1,ai['counts']          # só a 4 conta como sem correspondência
e._audit_separar_cancelados(res,CNPJ); assert len(res['cancelled_xml'])==1 and res['xml_count']==3          # repetir não duplica
# marcar à mão a nota 4
assert len(e.db_mark_document_cancelled(CNPJ,key(4)))==1 and e.db_mark_document_cancelled(CNPJ,key(4))==[]
e._audit_separar_cancelados(res,CNPJ)
assert res['xml_only']==[] and sorted(r['numero'] for r in res['cancelled_xml'])==['3','4'] and res['xml_total']==Decimal('300.00')
# PDF da auditoria traz a coluna Documento e a situação Cancelada
import pypdf
tmp=Path(tempfile.mkdtemp(prefix='exato_v183_audpdf_')); pdf=tmp/'a.pdf'
res['ai_analysis']=e.analyze_audit_result(res,'EMPRESA TESTE LTDA','2026-09-01','2026-09-30')
e.generate_audit_pdf(res,str(pdf),'EMPRESA TESTE LTDA',CNPJ,'2026-09-01','2026-09-30',[])
tx=' '.join(' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(pdf)).pages).split())
assert 'Documento' in tx and 'Cancelada' in tx,tx[-800:]
print('V182 auditoria cancelada OK')
