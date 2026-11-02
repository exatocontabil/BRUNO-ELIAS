import os, tempfile, importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v102_ui_') as td:
    os.environ['EXATO_DATA_DIR']=td
    os.environ['EXATO_CF_DEV']='1'
    spec=importlib.util.spec_from_file_location('exato_v102_ui',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    app=mod.App()
    app.update_idletasks()
    assert app.title().startswith('Exato Central Fiscal — V102'), app.title()
    app._show_webservice_test(); app.update_idletasks()
    assert hasattr(app,'processing_labels') and len(app.processing_labels)==3
    app._show_documents(); app.update_idletasks()
    assert hasattr(app,'doc_tree')
    assert str(app.doc_tree.cget('selectmode'))=='extended'
    app._open_global_search_dialog(); app.update_idletasks()
    assert getattr(app,'_global_search_win',None) is not None
    app._global_search_win.destroy(); app.destroy()
os.environ.pop('EXATO_CF_DEV',None)
print('V102_UI_SMOKE_OK')
