from pathlib import Path
import os,tempfile,importlib.util
from types import SimpleNamespace

base=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    os.environ['EXATO_DATA_DIR']=td
    spec=importlib.util.spec_from_file_location('exato_v095_ui',base/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

    # Deterministic unit test of the new selection/button wiring.
    class Button:
        def __init__(self): self.state='disabled'; self.text='VER/GERAR REPRESENTAÇÃO'
        def config(self,**kw):
            if 'state' in kw: self.state=kw['state']
            if 'text' in kw: self.text=kw['text']
        def cget(self,key): return self.state if key=='state' else self.text
    class Tree:
        def __init__(self,iid): self._iid=iid
        def selection(self): return (self._iid,)
    fake=SimpleNamespace(
        audit_tree=Tree('audit_0'),
        _audit_row_map={'audit_0':{'status':'Conforme','numero':'1009','data':'2026-08-05','modelo':'NF-e'}},
        audit_rep_btn=Button()
    )
    fake._selected_audit_row=lambda: fake._audit_row_map.get('audit_0')
    fake._audit_source_document=lambda row=None: mod._find_local_audit_document('99999999000199', row or fake._selected_audit_row())
    mod.App._on_audit_selection(fake)
    assert fake.audit_rep_btn.state=='normal'
    assert fake.audit_rep_btn.text=='VER/GERAR DANFE'
    fake._audit_row_map['audit_0']['modelo']='NFC-e'
    mod.App._on_audit_selection(fake)
    assert fake.audit_rep_btn.state=='normal'
    assert fake.audit_rep_btn.text=='VER/GERAR DANFE NFC-e'
    fake._audit_row_map['audit_0']['status']='XML não localizado'
    mod.App._on_audit_selection(fake)
    assert fake.audit_rep_btn.state=='disabled'

    # Verify the action resolves the source XML and delegates to the existing fiscal renderer.
    calls=[]
    mod._find_local_audit_document=lambda cnpj,row: calls.append((cnpj,row)) or {
        'family':'nfe','doc_type':'NF-e','number':'1009','series':'1',
        'issued_at':'2026-08-05 10:00:00','access_key':'','cnpj':cnpj,'xml':b'<nfeProc/>'
    }
    rendered=[]
    mod.open_document_fiscal_representation=lambda source: rendered.append(source) or '/tmp/NFe_1009.pdf'
    fake._audit_row_map['audit_0']={'status':'Conforme','numero':'1009','data':'2026-08-05','modelo':'NF-e','chave':'','serie':'1'}
    fake.cnpj_var=SimpleNamespace(get=lambda:'99999999000199')
    fake.set_status=lambda text: None
    mod.App._open_selected_audit_representation(fake)
    assert calls and calls[0][0]=='99999999000199'
    assert rendered and rendered[0]['xml']==b'<nfeProc/>'

print('V095_AUDIT_UI_OK')
