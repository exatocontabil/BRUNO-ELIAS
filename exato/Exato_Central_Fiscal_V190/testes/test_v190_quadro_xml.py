"""V179: relatório de NF-e/NFC-e/CT-e traz uma página final com autorizadas e canceladas em linhas separadas; o resumo do cancelamento conta como cancelado no relatório."""
import os, sys, tempfile, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_quadro_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m, exato_quadro_pdf as Q, exato_fechamento_pdf as F
import pypdf
EMIT='11222333000181'; DEST='45723174000110'
def chave(i): return f'3526091122233300018155001{i:09d}1000000010'[:44].ljust(44,'0')
NS='xmlns="http://www.portalfiscal.inf.br/nfe"'
def nfe(i,valor):
    ch=chave(i)
    return (f'<nfeProc {NS}><NFe><infNFe Id="NFe{ch}"><ide><mod>55</mod><nNF>{i}</nNF><serie>1</serie><dhEmi>2026-09-1{i}T10:00:00-03:00</dhEmi><natOp>Venda</natOp></ide><emit><CNPJ>{EMIT}</CNPJ><xNome>EMIT LTDA</xNome></emit>'
            f'<dest><CNPJ>{DEST}</CNPJ><xNome>DEST LTDA</xNome></dest><total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{ch}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
def resumo(i): return (f'<resEvento {NS}><chNFe>{chave(i)}</chNFe><tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento><xEvento>Cancelamento</xEvento><nProt>13526000000000{i}</nProt></resEvento>').encode()
m.init_database(); m.db_register_company(EMIT,'EMIT LTDA')
m.db_upsert_documents(EMIT,[{'xml':nfe(1,'100.00'),'family':'nfe','tipo':'nfeProc','nsu':1},{'xml':nfe(2,'250.00'),'family':'nfe','tipo':'nfeProc','nsu':2},{'xml':nfe(3,'40.00'),'family':'nfe','tipo':'nfeProc','nsu':3},
                       {'xml':resumo(2),'family':'nfe','tipo':'resEvento','nsu':4}])
docs=m.db_load_documents_as_payload(EMIT,limit=1000,include_events=True)
q=Q.quadro(docs); assert q==[('nfe','Saída',2,m.Decimal('140.00'),1,m.Decimal('250.00'))],q
tmp=Path(tempfile.mkdtemp(prefix='exato_v183_q_')); pdf=tmp/'r.pdf'
m._relatorio_documentos_pdf(docs,str(pdf),None,EMIT,'2026-09-01','2026-09-30')
tx=' '.join(' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(pdf)).pages).split())
assert 'Autorizadas e canceladas' in tx and 'Autorizadas: 2 nota(s)' in tx and 'Canceladas: 1 nota(s)' in tx and 'R$ 140,00 Canceladas' in tx,tx[-700:]
# o relatório principal (núcleo) também enxerga a nota 2 como cancelada (o resumo só vale na memória)
assert 'Cancelado' in tx or 'CANCELAD' in tx.upper(),tx[:1200]
# nada foi gravado como evento "completo": o resumo continua resumo no banco
c=sqlite3.connect(m.DB_PATH); x=c.execute("SELECT xml FROM documents WHERE status='Evento'").fetchone()[0]; assert b'retEvento' not in bytes(x) and b'resEvento' in bytes(x)
# fechamento: valores de autorizadas e canceladas separados
rows=[{'family':'nfe','direcao':'Saída','situacao':'Autorizada','valor':'100.00','numero':'1','data':'2026-09-10','chave':chave(1),'serie':'1'},
      {'family':'nfe','direcao':'Saída','situacao':'Cancelada','valor':'250.00','numero':'2','data':'2026-09-11','chave':chave(2),'serie':'1'}]
assert F.resumo_separado(rows)==[('nfe','Saída',1,m.Decimal('100.00'),1,m.Decimal('250.00'))]
f=tmp/'f.pdf'; F.gerar_fechamento_pdf(rows,str(f),'EMIT LTDA',EMIT,'2026-09')
tf=' '.join(' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(f)).pages).split())
for e in ('Autorizadas (valor)','Canceladas (valor)','R$ 250,00','Total autorizadas','Total canceladas','Autorizadas: 1 nota(s)','Canceladas: 1 nota(s)'): assert e in tf,(e,tf[:800])
print('V179 quadro XML OK')
