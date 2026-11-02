import os,tempfile,importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v103_ui_') as td:
    os.environ['EXATO_DATA_DIR']=td
    os.environ['EXATO_CF_DEV']='1'
    spec=importlib.util.spec_from_file_location('exato_v103_ui',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    app=mod.App(); app.withdraw(); app._show_audit(); app.update_idletasks()
    assert app.title().startswith('Exato Central Fiscal — V103'), app.title()
    assert hasattr(app,'audit_family_buttons') and set(app.audit_family_buttons)=={'nfe','nfce'}
    app._audit_set_family('nfe'); app._audit_set_family('nfce')
    assert app._audit_selected_families()==['nfe','nfce']
    assert app.audit_family_var.get()=='multi'
    assert 'separadamente' in app.audit_family_hint.cget('text').casefold()
    app.destroy()
    os.environ.pop('EXATO_CF_DEV',None)
print('V103_UI_SMOKE_OK')
