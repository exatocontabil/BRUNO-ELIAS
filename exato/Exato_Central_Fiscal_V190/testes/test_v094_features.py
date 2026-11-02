from pathlib import Path
import os,tempfile,importlib.util
base=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    os.environ['EXATO_DATA_DIR']=td
    spec=importlib.util.spec_from_file_location('exato_v094',base/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    result={'audit_rows':[{'numero':'1009','data':'2026-08-05','valor_sat':'991','valor_xml':'981','status':'Divergência','differences':[]}]}
    assert 'nota 1009' in mod.ExatoIAEngine(result).answer('Qual nota devo revisar primeiro?').lower()
    with tempfile.TemporaryDirectory() as out:
        xml=b'<nfeProc><NFe><infNFe Id="NFe35260999999999000199550010000010091000010099"><ide><nNF>1009</nNF><serie>1</serie><dhEmi>2026-08-05T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide><emit><CNPJ>99999999000199</CNPJ><xNome>Empresa Teste</xNome></emit><dest><CNPJ>11111111000111</CNPJ><xNome>Destinatario</xNome></dest><total><ICMSTot><vNF>991.00</vNF></ICMSTot></total></infNFe></NFe></nfeProc>'
        docs=[{'family':'nfe','doc_type':'NF-e','direcao':'Saída','data':'2026-08-05','numero':'1009','serie':'1','chave':'35260999999999000199550010000010091000010099','xml':xml}]
        saved,errors=mod.save_documents_organized(docs,out,'99999999000199',generate_companion_pdf=False,period_start='2026-08-01',period_end='2026-08-31')
        assert not errors,errors
        p=Path([x for x in saved if str(x).endswith('.xml')][0])
        assert [x.name for x in p.parents][:4]==['NF-e','Saída','08 - Agosto','2026'],p
print('V094_FEATURES_OK')
