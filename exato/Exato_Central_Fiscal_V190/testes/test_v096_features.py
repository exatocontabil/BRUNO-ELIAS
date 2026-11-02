from pathlib import Path
import os, tempfile, importlib.util

base=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    os.environ['EXATO_DATA_DIR']=td
    spec=importlib.util.spec_from_file_location('exato_v096',base/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    cnpj='99999999000199'
    xml_out="""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc><NFe><infNFe Id="NFe35260999999999000199550010000010091000010099"><ide><mod>55</mod><nNF>1009</nNF><serie>1</serie><dhEmi>2026-08-05T10:00:00-03:00</dhEmi><tpNF>1</tpNF><natOp>Venda de mercadoria</natOp></ide><emit><CNPJ>99999999000199</CNPJ><xNome>Empresa Saída</xNome><enderEmit><xLgr>Rua A</xLgr><nro>10</nro><xBairro>Centro</xBairro><xMun>Araranguá</xMun><UF>SC</UF><CEP>88900000</CEP></enderEmit><IE>123</IE></emit><dest><CNPJ>11111111000111</CNPJ><xNome>Cliente</xNome><enderDest><xLgr>Rua B</xLgr><nro>20</nro><xBairro>Centro</xBairro><xMun>Tubarão</xMun><UF>SC</UF><CEP>88700000</CEP></enderDest></dest><det nItem="1"><prod><cProd>1</cProd><xProd>Produto teste</xProd><NCM>22029900</NCM><CFOP>5102</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>10.00</vUnCom><vProd>10.00</vProd></prod><imposto><ICMS><ICMS00><CST>00</CST><vBC>10.00</vBC><pICMS>12.00</pICMS><vICMS>1.20</vICMS></ICMS00></ICMS></imposto></det><total><ICMSTot><vBC>10.00</vBC><vICMS>1.20</vICMS><vProd>10.00</vProd><vNF>10.00</vNF></ICMSTot></total><infAdic><infCpl>Informação complementar de teste.</infCpl></infAdic></infNFe></NFe></nfeProc>""".encode('utf-8')
    xml_in=xml_out.replace(b'<emit><CNPJ>99999999000199</CNPJ><xNome>Empresa Sa\xc3\xadda', b'<emit><CNPJ>11111111000111</CNPJ><xNome>Outro Emitente')
    xml_in=xml_in.replace(b'<dest><CNPJ>11111111000111</CNPJ><xNome>Cliente</xNome>', b'<dest><CNPJ>99999999000199</CNPJ><xNome>Empresa Entrada</xNome>')

    docs=[
        {'family':'nfe','doc_type':'NF-e','direcao':'Saída','data':'2026-08-05','numero':'1009','serie':'1','chave':'35260999999999000199550010000010091000010099','xml':xml_out},
        {'family':'nfe','doc_type':'NF-e','data':'2026-08-06','numero':'1010','serie':'1','chave':'35260999999999000199550010000010101000010100','xml':xml_in},
    ]
    with tempfile.TemporaryDirectory() as out:
        saved,errors=mod.save_documents_organized(docs,out,cnpj,generate_companion_pdf=True,period_start='2026-08-01',period_end='2026-08-31')
        assert not errors, errors
        month=Path(out)/'Empresa_99999999000199'/'2026'/'08 - Agosto'
        assert (month/'Entrada').is_dir()
        assert (month/'Saída').is_dir()
        assert (month/'Entrada'/'NF-e').is_dir()
        assert (month/'Saída'/'NF-e').is_dir()
        pdfs=list((month/'Saída'/'NF-e').glob('*.pdf'))
        assert pdfs and all(p.stat().st_size>1000 for p in pdfs)
        xml_paths=list((month/'Entrada'/'NF-e').glob('*.xml'))+list((month/'Saída'/'NF-e').glob('*.xml'))
        assert len(xml_paths)==2, xml_paths

    with tempfile.TemporaryDirectory() as out:
        p=Path(out)/'danfe.pdf'
        meta={'family':'nfe','xml':xml_out,'access_key':'35260999999999000199550010000010091000010099','number':'1009','series':'1'}
        mod.generate_fiscal_representation_pdf([meta],str(p),family='nfe')
        assert p.exists() and p.stat().st_size>1000
        from pypdf import PdfReader
        text='\n'.join((pg.extract_text() or '') for pg in PdfReader(str(p)).pages)
        for marker in ('DANFE','DESTINATÁRIO/REMETENTE','DADOS DOS PRODUTOS/SERVIÇOS','TRANSPORTADOR/VOLUMES TRANSPORTADOS','DADOS ADICIONAIS'):
            assert marker in text, marker

print('V096_FEATURES_CURRENT_STRUCTURE_OK')
