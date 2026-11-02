import os, tempfile, importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v108_ui_') as td:
    os.environ['EXATO_DATA_DIR']=td
    os.environ['EXATO_CF_DEV']='1'
    spec=importlib.util.spec_from_file_location('v108_ui',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert mod.APP_VERSION=='V108'
    app=mod.App(); app.withdraw(); app._show_audit(); app.update_idletasks()
    app._audit_refresh_mascot('atencao'); app.update_idletasks()
    assert getattr(app,'audit_mascot_img',None) is not None
    assert app.audit_ai_left.cget('bg') in ('#FFF7E8','#ECF8F0','#FFF0F1')
    assert app.audit_mascot_label.cget('bg')==app.audit_ai_left.cget('bg')
    # Type filter control remains available for multi-type audit.
    assert list(app.audit_type_filter_combo.cget('values'))==['Todos','NF-e','NFC-e','CT-e']
    # The state filter includes distinct semantics.
    assert 'Sem correspondência' in list(app.audit_filter_combo.cget('values'))
    app.destroy()
print('V108_UI_SMOKE_OK')
