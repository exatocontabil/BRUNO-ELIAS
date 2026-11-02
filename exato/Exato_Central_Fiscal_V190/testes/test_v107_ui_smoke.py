import os,tempfile,importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v106_ui_') as td:
    os.environ['EXATO_DATA_DIR']=td
    os.environ['EXATO_CF_DEV']='1'
    spec=importlib.util.spec_from_file_location('exato_v106_ui',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    app=mod.App(); app.withdraw(); app.update_idletasks()
    assert app.title().startswith('Exato Central Fiscal — V107'), app.title()
    app._show_webservice_test(); app.update_idletasks()
    assert hasattr(app,'processing_labels') and len(app.processing_labels)==3
    app._show_documents(); app.update_idletasks()
    assert hasattr(app,'doc_tree') and str(app.doc_tree.cget('selectmode'))=='extended'
    app._show_audit(); app.update_idletasks()
    assert hasattr(app,'audit_family_buttons')
    app._audit_set_family('nfe'); app._audit_set_family('nfce')
    assert app._audit_selected_families()==['nfe','nfce']
    app.destroy()
    os.environ.pop('EXATO_CF_DEV',None)
print('V107_UI_SMOKE_OK')
