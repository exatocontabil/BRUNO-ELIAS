from pathlib import Path
import os, tempfile, importlib.util
from pypdf import PdfReader

BASE = Path(__file__).resolve().parents[1]

def load_app():
    td = tempfile.TemporaryDirectory()
    os.environ["EXATO_DATA_DIR"] = td.name
    spec = importlib.util.spec_from_file_location("exato_v099", BASE / "exato_central_fiscal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, td

def mkxml(model, tp, number, cnpj, nat, value, day):
    dest = '11111111000111'
    issuer_cnpj = cnpj if tp == '1' else dest
    issuer_name = 'EMPRESA TESTE' if tp == '1' else 'FORNECEDOR TESTE'
    dest_cnpj = dest if tp == '1' else cnpj
    dest_name = 'CLIENTE TESTE' if tp == '1' else 'EMPRESA TESTE'
    cfop = '5102' if tp == '1' else '1102'
    xml = """<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe422608{}{}{}{}"><ide><cUF>42</cUF><cNF>12345678</cNF><natOp>{}</natOp><mod>{}</mod><serie>1</serie><nNF>{}</nNF><dhEmi>2026-08-{:02d}T17:53:26-03:00</dhEmi><dhSaiEnt>2026-08-{:02d}T18:00:00-03:00</dhSaiEnt><tpNF>{}</tpNF></ide><emit><CNPJ>{}</CNPJ><xNome>{}</xNome><enderEmit><xLgr>RUA A</xLgr><nro>10</nro><xBairro>CENTRO</xBairro><xMun>ARARANGUA</xMun><UF>SC</UF><CEP>88900000</CEP></enderEmit><IE>123456789</IE></emit><dest><CNPJ>{}</CNPJ><xNome>{}</xNome><enderDest><xLgr>RUA B</xLgr><nro>20</nro><xBairro>CENTRO</xBairro><xMun>TUBARAO</xMun><UF>SC</UF><CEP>88700000</CEP></enderDest></dest><det nItem="1"><prod><cProd>1</cProd><xProd>PRODUTO TESTE</xProd><NCM>22021000</NCM><CFOP>{}</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>{}</vUnCom><vProd>{}</vProd></prod><imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><vBC>{}</vBC><vICMS>1.20</vICMS><pICMS>12.00</pICMS></ICMS00></ICMS></imposto></det><total><ICMSTot><vBC>{}</vBC><vICMS>1.20</vICMS><vBCST>0.00</vBCST><vST>0.00</vST><vII>0.00</vII><vIPI>0.00</vIPI><vProd>{}</vProd><vFrete>0.00</vFrete><vSeg>0.00</vSeg><vDesc>0.00</vDesc><vOutro>0.00</vOutro><vNF>{}</vNF></ICMSTot></total><transp><modFrete>9</modFrete></transp></infNFe></NFe></nfeProc>""".format(cnpj, model, number, '', nat, model, number, day, day, tp, issuer_cnpj, issuer_name, dest_cnpj, dest_name, cfop, value, value, value, value, value, value, value)
    return xml.encode()

mod, td = load_app()
try:
    with tempfile.TemporaryDirectory() as out:
        cnpj='23187104000152'
        docs=[]
        entry_days=[1,3,4,5,7,8,10,11,12,13,15,18,20,21,22,24,27,29,31]
        for i, day in enumerate(entry_days,1):
            value=f'{100+i*7:.2f}'
            docs.append({'family':'nfe','xml':mkxml('55','0',2000+i,cnpj,'COMPRA PARA COMERCIALIZACAO',value,day),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}','direction':'Entrada','number':str(2000+i),'series':'1'})
        out_days=[1,2,3,4,5,6,7,8,9,10,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31]*2
        out_days=out_days[:49]
        for i, day in enumerate(out_days,1):
            value=f'{300+i*5:.2f}'
            docs.append({'family':'nfce','xml':mkxml('65','1',3000+i,cnpj,'VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS',value,day),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}','direction':'Saída','number':str(3000+i),'series':'1'})

        report=Path(out)/'report.pdf'
        mod.generate_documents_pdf(docs,str(report),consulta_cnpj=cnpj,period_start='2026-08-01',period_end='2026-08-31')
        reader=PdfReader(str(report)); assert len(reader.pages)==6, len(reader.pages)
        texts=[p.extract_text() or '' for p in reader.pages]
        all_text='\n'.join(texts)
        assert 'Sem 5' in texts[0] and '(29 a 31)' in texts[0]
        assert all_text.count('EXATO IA — ENTRADA')==1
        assert all_text.count('EXATO IA — SAÍDA')==1
        assert 'TOTAL DA OPERAÇÃO\n19' in all_text
        assert 'TOTAL DA OPERAÇÃO\n49' in all_text
        assert all_text.count('NESTA PÁGINA')==5
        assert 'VENDA DE MERCADORIA' in texts[0]
        assert all('TODOS' not in t for t in texts[1:])
        assert '49 de 49 documentos' in all_text
        assert '38–49 de 49 documentos' in all_text

        saved, errors = mod.save_documents_organized(docs[:2] + docs[-2:], out, cnpj, {'company_names':{cnpj:'EMPRESA TESTE'}}, generate_companion_pdf=True, period_start='2026-08-01', period_end='2026-08-31')
        assert not errors, errors
        month=Path(out)/'EMPRESA TESTE'/'2026'/'08 - Agosto'
        assert (month/'Entrada'/'NF-e').is_dir()
        assert (month/'Saída'/'NFC-e').is_dir()
        assert all(p.suffix.lower() in {'.xml','.pdf'} for d in [month/'Entrada'/'NF-e',month/'Saída'/'NFC-e'] for p in d.iterdir())
        assert not (month/'PDFs Fiscais').exists()
        assert not (month/'NF-e').exists()
        assert not (month/'NFC-e').exists()
    print('V099_REPORT_REGRESSION_OK')
finally:
    td.cleanup()
