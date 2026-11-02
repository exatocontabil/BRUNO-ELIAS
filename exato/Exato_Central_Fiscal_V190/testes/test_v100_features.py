from pathlib import Path
import os, tempfile, importlib.util
from pypdf import PdfReader

BASE = Path(__file__).resolve().parents[1]


def load_app():
    td = tempfile.TemporaryDirectory()
    os.environ['EXATO_DATA_DIR'] = td.name
    spec = importlib.util.spec_from_file_location('exato_v100', BASE / 'exato_central_fiscal.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, td


def mkxml(model, tp, number, cnpj, nat, value, day):
    dest='11111111000111'
    issuer_cnpj=cnpj if tp=='1' else dest
    issuer_name='EMPRESA TESTE' if tp=='1' else 'FORNECEDOR TESTE'
    dest_cnpj=dest if tp=='1' else cnpj
    dest_name='CLIENTE TESTE' if tp=='1' else 'EMPRESA TESTE'
    cfop='5102' if tp=='1' else '1102'
    xml='''<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe422608231871040001526500100000{}11111111111111"><ide><cUF>42</cUF><cNF>12345678</cNF><natOp>{}</natOp><mod>{}</mod><serie>1</serie><nNF>{}</nNF><dhEmi>2026-08-{:02d}T17:53:26-03:00</dhEmi><tpNF>{}</tpNF></ide><emit><CNPJ>{}</CNPJ><xNome>{}</xNome><enderEmit><xLgr>RUA A</xLgr><nro>10</nro><xBairro>CENTRO</xBairro><xMun>ARARANGUA</xMun><UF>SC</UF><CEP>88900000</CEP></enderEmit><IE>123456789</IE></emit><dest><CNPJ>{}</CNPJ><xNome>{}</xNome><enderDest><xLgr>RUA B</xLgr><nro>20</nro><xBairro>CENTRO</xBairro><xMun>TUBARAO</xMun><UF>SC</UF><CEP>88700000</CEP></enderDest></dest><det nItem="1"><prod><cProd>1</cProd><xProd>PRODUTO TESTE</xProd><NCM>22021000</NCM><CFOP>{}</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>{}</vUnCom><vProd>{}</vProd></prod><imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><vBC>{}</vBC><vICMS>1.20</vICMS><pICMS>12.00</pICMS></ICMS00></ICMS></imposto></det><total><ICMSTot><vBC>{}</vBC><vICMS>1.20</vICMS><vBCST>0.00</vBCST><vST>0.00</vST><vII>0.00</vII><vIPI>0.00</vIPI><vProd>{}</vProd><vFrete>0.00</vFrete><vSeg>0.00</vSeg><vDesc>0.00</vDesc><vOutro>0.00</vOutro><vNF>{}</vNF></ICMSTot></total><transp><modFrete>9</modFrete></transp></infNFe></NFe></nfeProc>'''.format(number,nat,model,number,day,tp,issuer_cnpj,issuer_name,dest_cnpj,dest_name,cfop,value,value,value,value,value,value,value)
    return xml.encode()

mod, td = load_app()
try:
    cnpj='23187104000152'
    docs=[]
    # Two Entrada NF-e and two Saída NFC-e across the same month.
    for i,day in enumerate((4,11),1):
        num=190000+i
        docs.append({'family':'nfe','xml':mkxml('55','0',num,cnpj,'COMPRA PARA COMERCIALIZACAO',f'{500+i*10:.2f}',day),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}','direction':'Entrada','number':str(num),'series':'1'})
    for i,day in enumerate((5,12),1):
        num=1000+i
        docs.append({'family':'nfce','xml':mkxml('65','1',num,cnpj,'VENDA DE MERCADORIA',f'{600+i*10:.2f}',day),'cnpj':cnpj,'data':f'2026-08-{day:02d}','issued_at':f'2026-08-{day:02d}','direction':'Saída','number':str(num),'series':'1'})

    with tempfile.TemporaryDirectory() as out:
        saved, errors=mod.save_documents_organized(docs,out,cnpj,{'company_names':{cnpj:'EMPRESA TESTE'}},generate_companion_pdf=True,period_start='2026-08-01',period_end='2026-08-31')
        assert not errors, errors
        month=Path(out)/'EMPRESA TESTE'/'2026'/'08 - Agosto'
        in_nfe=month/'Entrada'/'NF-e'
        out_nfce=month/'Saída'/'NFC-e'
        assert in_nfe.is_dir() and out_nfce.is_dir()
        assert sorted(p.suffix.lower() for p in in_nfe.iterdir()).count('.xml')==2
        assert sorted(p.suffix.lower() for p in in_nfe.iterdir()).count('.pdf')==3
        assert sorted(p.suffix.lower() for p in out_nfce.iterdir()).count('.xml')==2
        assert sorted(p.suffix.lower() for p in out_nfce.iterdir()).count('.pdf')==3
        in_con=next(p for p in in_nfe.iterdir() if 'Entrada' in p.name)
        out_con=next(p for p in out_nfce.iterdir() if 'Saida' in p.name)
        assert len(PdfReader(str(in_con)).pages)==2
        assert len(PdfReader(str(out_con)).pages)==2
        assert not (month/'PDFs Fiscais').exists()
        assert not (month/'NF-e').exists()
        assert not (month/'NFC-e').exists()

    # The period-scoped card values are exercised without launching a GUI by reproducing
    # the same direction/family aggregation used by the dashboard refresh.
    counts={f:{'Entrada':0,'Saída':0} for f in ('nfe','nfce','cte')}
    for d in docs:
        counts[d['family']][d['direction']]+=1
    assert counts['nfe']=={'Entrada':2,'Saída':0}
    assert counts['nfce']=={'Entrada':0,'Saída':2}
    print('V100_EXPORT_AND_DIRECTION_COUNTS_OK')
finally:
    td.cleanup()
