import os, tempfile, importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v105_ui_') as td:
    os.environ['EXATO_DATA_DIR']=td
    os.environ['EXATO_CF_DEV']='1'
    spec=importlib.util.spec_from_file_location('exato_v105_ui',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    app=mod.App(); app.withdraw(); app._show_webservice_test(); app.update_idletasks()
    # Prime the current Documents context with the same period and mixed doc types.
    app._cnpj_confirmed=True; app._period_confirmed=True
    app.cnpj_var.set('23187104000152')
    app.capture_from.set('01/08/2026'); app.capture_to.set('31/08/2026')
    app.last_documents=[
        {'family':'nfe','status':'Autorizado','data':'2026-08-05'},
        {'family':'nfce','status':'Autorizado','data':'2026-08-06'},
        {'family':'cte','status':'Autorizado','data':'2026-08-07'},
    ]
    app._run_sat_audit=lambda: None
    app._show_audit_from_documents()
    assert app.audit_from.get()=='01/08/2026'
    assert app.audit_to.get()=='31/08/2026'
    assert app.audit_selected_families==['nfe','nfce']
    assert app.audit_family_var.get()=='multi'
    app.destroy()
    os.environ.pop('EXATO_CF_DEV',None)
print('V109_AUDIT_CONTEXT_HANDOFF_OK')
