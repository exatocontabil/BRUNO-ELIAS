from pathlib import Path
import os, tempfile, importlib.util, ast, hashlib
from pypdf import PdfReader

BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_CF_DEV']='1'
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v123_pdf_')
spec=importlib.util.spec_from_file_location('v123',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V123'


def mk_nfe(model, tp, number, cnpj, nat, value, day):
    dest='11111111000111'
    issuer_cnpj=cnpj if tp=='1' else dest
    issuer_name='EMPRESA TESTE' if tp=='1' else 'FORNECEDOR TESTE'
    dest_cnpj=dest if tp=='1' else cnpj
    dest_name='CLIENTE TESTE' if tp=='1' else 'EMPRESA TESTE'
    cfop='5102' if tp=='1' else '1102'
    return f'''<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe4226082318710400015255{number:0>8}"><ide><cUF>42</cUF><cNF>12345678</cNF><natOp>{nat}</natOp><mod>{model}</mod><serie>1</serie><nNF>{number}</nNF><dhEmi>2026-08-{day:02d}T17:53:26-03:00</dhEmi><tpNF>{tp}</tpNF></ide><emit><CNPJ>{issuer_cnpj}</CNPJ><xNome>{issuer_name}</xNome></emit><dest><CNPJ>{dest_cnpj}</CNPJ><xNome>{dest_name}</xNome></dest><det nItem="1"><prod><cProd>1</cProd><xProd>PRODUTO TESTE</xProd><NCM>22021000</NCM><CFOP>{cfop}</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>{value}</vUnCom><vProd>{value}</vProd></prod></det><total><ICMSTot><vProd>{value}</vProd><vNF>{value}</vNF></ICMSTot></total></infNFe></NFe></nfeProc>'''.encode()


def mk_cte(number, day, value, cnpj):
    key=f'422608111111110001115700100000{number:06d}00000000000000'
    return f'''<?xml version="1.0"?><cteProc xmlns="http://www.portalfiscal.inf.br/cte" versao="4.00"><CTe><infCte Id="CTe{key}"><ide><cUF>42</cUF><nCT>{number}</nCT><serie>1</serie><dhEmi>2026-08-{day:02d}T17:53:26-03:00</dhEmi></ide><emit><CNPJ>11111111000111</CNPJ><xNome>TRANSPORTADORA TESTE</xNome></emit><toma3><toma>3</toma><CNPJ>{cnpj}</CNPJ></toma3><vPrest><vTPrest>{value}</vTPrest></vPrest></infCte></CTe></cteProc>'''.encode()

cnpj='49894842000123'; docs=[]
# Entrada: 8 NF-e + 2 CT-e, mirroring the real mixed-document scenario.
for i,day in enumerate([5,10,18,18,21,22,25,31],1):
    val=f'{100+i*7:.2f}'
    docs.append({'family':'nfe','xml':mk_nfe('55','0',5000+i,cnpj,'COMPRA PARA COMERCIALIZACAO',val,day),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}'})
for i,day in enumerate([20,25],1):
    val=f'{120+i*50:.2f}'
    docs.append({'family':'cte','xml':mk_cte(7000+i,day,val,cnpj),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}'})
# Saída: 54 NF-e + 7 NFC-e.
for i in range(1,62):
    day=[3,4,13,14,17,25,26,27,28,31][(i-1)%10]
    val=f'{300+i*5:.2f}'
    is_nfce=i in {22,23,24,27,47,52,61}
    family='nfce' if is_nfce else 'nfe'; model='65' if is_nfce else '55'
    docs.append({'family':family,'xml':mk_nfe(model,'1',8000+i,cnpj,'VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS',val,day),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}'})

from collections import Counter
with tempfile.TemporaryDirectory(prefix='v123_report_') as td:
    out=Path(td)/'report.pdf'
    mod.generate_documents_pdf(docs,out,consulta_cnpj=cnpj,period_start='2026-08-01',period_end='2026-08-31')
    reader=PdfReader(str(out)); pages=len(reader.pages); texts=[p.extract_text() or '' for p in reader.pages]
    assert pages==6, pages
    full='\n'.join(texts)
    assert full.count('EXATO IA — ENTRADA')==1
    assert full.count('EXATO IA — SAÍDA')==1
    assert '7 de 7' in full  # family-local NFC-e pagination is valid
    assert not any(('NF-e' in t and 'NFC-e' in t and '1–' in t and 'documentos' in t) for t in texts[1:])
    # Physical detail sections are type-pure: NF-e and NFC-e ranges each appear once.
    ranges=[('1–18 de 54 documentos NF-e','NF-e-1'),('19–36 de 54 documentos NF-e','NF-e-2'),('37–54 de 54 documentos NF-e','NF-e-3'),('1–7 de 7 documentos NFC-e','NFC-e-1')]
    for marker,_ in ranges:
        assert sum(marker in t for t in texts)==1, marker
    # Entry page keeps NF-e and CT-e as separate blocks, never a mixed table.
    entry_pages=[t for t in texts if 'EXATO IA — ENTRADA' in t]
    exit_pages=[t for t in texts if 'EXATO IA — SAÍDA' in t]
    assert len(entry_pages)==1 and '1–8 de 8 documentos NF-e' in entry_pages[0] and '1–2 de 2 documentos CT-e' in entry_pages[0]
    assert len(exit_pages)==1 and '1–7 de 7 documentos NFC-e' in exit_pages[0]
    assert 'NATUREZA DA OPERAÇÃO' in entry_pages[0] and 'NATUREZA DA OPERAÇÃO' in exit_pages[0]
    for i in range(1,7):
        assert f'Página {i} de 6' in texts[i-1]
print('V123_REPORT_LAYOUT_OK')
