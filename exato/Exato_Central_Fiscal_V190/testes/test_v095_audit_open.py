from pathlib import Path
import os,tempfile,importlib.util

base=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    os.environ['EXATO_DATA_DIR']=td
    spec=importlib.util.spec_from_file_location('exato_v095',base/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

    calls=[]
    mod.db_list_documents=lambda **kwargs: calls.append(kwargs) or [
        {
            'family':'nfe','number':'001009','series':'1','issued_at':'2026-08-05 10:00:00',
            'access_key':'35260999999999000199550010000010091000010099',
            'xml':b'<nfeProc/>','cnpj':'99999999000199','doc_type':'NF-e'
        }
    ]
    audit_row={
        'modelo':'NF-e','numero':'1009','serie':'1','data':'2026-08-05',
        'chave':'35260999999999000199550010000010091000010099'
    }
    found=mod._find_local_audit_document('99999999000199',audit_row)
    assert found and found['number']=='001009' and found['xml']==b'<nfeProc/>'
    assert calls and calls[0].get('query')=='35260999999999000199550010000010091000010099'

print('V095_AUDIT_OPEN_OK')
