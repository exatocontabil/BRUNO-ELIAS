from pathlib import Path
import os, tempfile, importlib.util
from pypdf import PdfReader
BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v115_pdf_')
spec=importlib.util.spec_from_file_location('exato_v115',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def mkxml(model, tp, number, cnpj, nat, value, day):
    dest='11111111000111'; issuer_cnpj=cnpj if tp=='1' else dest; issuer_name='EMPRESA TESTE' if tp=='1' else 'FORNECEDOR TESTE'; dest_cnpj=dest if tp=='1' else cnpj; dest_name='CLIENTE TESTE' if tp=='1' else 'EMPRESA TESTE'; cfop='5102' if tp=='1' else '1102'
    return f'''<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe4226082318710400015255{number:0>8}"><ide><cUF>42</cUF><cNF>12345678</cNF><natOp>{nat}</natOp><mod>{model}</mod><serie>1</serie><nNF>{number}</nNF><dhEmi>2026-08-{day:02d}T17:53:26-03:00</dhEmi><tpNF>{tp}</tpNF></ide><emit><CNPJ>{issuer_cnpj}</CNPJ><xNome>{issuer_name}</xNome></emit><dest><CNPJ>{dest_cnpj}</CNPJ><xNome>{dest_name}</xNome></dest><det nItem="1"><prod><cProd>1</cProd><xProd>PRODUTO TESTE</xProd><NCM>22021000</NCM><CFOP>{cfop}</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>{value}</vUnCom><vProd>{value}</vProd></prod></det><total><ICMSTot><vProd>{value}</vProd><vNF>{value}</vNF></ICMSTot></total></infNFe></NFe></nfeProc>'''.encode()

cnpj='49894842000123'; docs=[]
for i,day in enumerate([5,10,18,18,20,21,22,25,31,31],1):
    val=f'{100+i*7:.2f}'
    docs.append({'family':'nfe','xml':mkxml('55','0',5000+i,cnpj,'COMPRA PARA COMERCIALIZACAO',val,day),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}','direction':'Entrada','number':str(5000+i),'series':'1'})
for i in range(1,62):
    day=[3,4,13,14,17,25,26,27,28,31][(i-1)%10]
    val=f'{300+i*5:.2f}'
    docs.append({'family':'nfce' if i in {22,23,24,27,47,52,61} else 'nfe','xml':mkxml('65' if i in {22,23,24,27,47,52,61} else '55','1',8000+i,cnpj,'VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS',val,day),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}','direction':'Saída','number':str(8000+i),'series':'1'})
with tempfile.TemporaryDirectory(prefix='v115_report_') as td:
    out=Path(td)/'report.pdf'
    mod.generate_documents_pdf(docs,out,consulta_cnpj=cnpj,period_start='2026-08-01',period_end='2026-08-31')
    reader=PdfReader(str(out)); n=len(reader.pages); texts=[p.extract_text() or '' for p in reader.pages]
    print('pages=',n)
    print('page_labels=',[next((line for line in t.splitlines() if ' de ' in line and line[0].isdigit()),'') for t in texts])
    assert n==6, n
    full='\n'.join(texts)
    assert full.count('EXATO IA — ENTRADA')==1
    assert full.count('EXATO IA — SAÍDA')==1
    assert all(f'{i} de 6' in texts[i-1] for i in range(2,7))
    assert '7 de 7' not in full and '7 de 6' not in full
    # IA saída must be on the same physical page as the final output table.
    assert 'EXATO IA — SAÍDA' in texts[-1]
    assert '61–61' not in full
    # The final output page should still contain the final document range.
    assert '47–61 de 61 documentos' in texts[-1]
print('V115_REPORT_LAYOUT_OK')
