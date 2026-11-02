"""V130 — Busca Automática: confirmação explícita antes de iniciar.
Executar sob Xvfb; usa EXATO_DATA_DIR temporário.
"""
from __future__ import annotations
import os, sys, tempfile, json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v130_confirm_')
os.environ['EXATO_CF_DEV']='1'
sys.path.insert(0,str(BASE))
import exato_central_fiscal as mod  # noqa: E402

mod.messagebox.showwarning=lambda *a,**k: None
mod.messagebox.showerror=lambda *a,**k: (_ for _ in ()).throw(AssertionError(f'erro inesperado: {a}'))
mod.messagebox.showinfo=lambda *a,**k: None

mod.init_database()
mod.db_register_company('49894842000123','ELYON LTDA')
mod.db_register_company('00000000000191','EMPRESA TESTE')

app=mod.App()
app.selected={'Thumbprint':'TEST','FriendlyName':'CERT TESTE'}
app._open_multi_company_search_dialog()
app.update_idletasks()

assert mod.APP_VERSION=='V130'
assert str(app._multi_start_btn.cget('state'))=='disabled'
assert str(app._multi_confirm_btn.cget('state'))=='normal'
assert app._multi_confirmed is False

app._confirm_multi_company_config()
app.update_idletasks()
assert app._multi_confirmed is True
assert str(app._multi_start_btn.cget('state'))=='normal'
assert str(app._multi_confirm_btn.cget('state'))=='disabled'
for w in (app._multi_period_from_entry, app._multi_period_to_entry,
          app._multi_save_xml_chk, app._multi_generate_pdf_chk,
          app._multi_root_entry, app._multi_root_btn, app._multi_import_btn):
    assert str(w.cget('state'))=='disabled', (w, w.cget('state'))

assert not app._multi_company_run_active
app.destroy()
print(json.dumps({'ok':True,'version':'V130','confirmed_before_start':True}))
