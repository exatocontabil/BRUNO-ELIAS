import os, tempfile, importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v110_ui_') as td:
    os.environ['EXATO_DATA_DIR']=td
    os.environ['EXATO_CF_DEV']='1'
    spec=importlib.util.spec_from_file_location('v110_ui',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert mod.APP_VERSION=='V110'
    app=mod.App(); app.withdraw(); app._show_audit(); app.update_idletasks()
    app._audit_refresh_mascot('atencao'); app.update_idletasks()
    assert getattr(app,'audit_mascot_img',None) is not None
    assert app.audit_ai_left.cget('bg') == '#F8FAFC'
    assert app.audit_mascot_label.cget('bg')==app.audit_ai_left.cget('bg')
    assert list(app.audit_type_filter_combo.cget('values'))==['Todos','NF-e','NFC-e','CT-e']
    assert 'Sem correspondência' in list(app.audit_filter_combo.cget('values'))
    # The primary action remains Exato red, while document types do not use blue/purple/orange decorative accents.
    assert mod.NFE_ACCENT == mod.RED == '#DC2626'
    app.destroy()
print('V110_UI_SMOKE_OK')
