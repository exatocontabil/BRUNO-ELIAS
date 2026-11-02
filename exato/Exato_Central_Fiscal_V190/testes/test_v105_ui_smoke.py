import os, tempfile, importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v105_ui_') as td:
    os.environ['EXATO_DATA_DIR']=td
    os.environ['EXATO_CF_DEV']='1'
    spec=importlib.util.spec_from_file_location('exato_v105_smoke',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    app=mod.App(); app.withdraw()
    assert app.title().startswith('Exato Central Fiscal — V105'), app.title()
    app._show_audit(); app.update_idletasks()
    assert hasattr(app,'audit_family_buttons') and set(app.audit_family_buttons)=={'nfe','nfce'}
    app._audit_set_family('nfe'); app._audit_set_family('nfce')
    assert app._audit_selected_families()==['nfe','nfce']
    assert app.audit_family_var.get()=='multi'
    app.destroy()
    os.environ.pop('EXATO_CF_DEV',None)
print('V105_UI_SMOKE_OK')
