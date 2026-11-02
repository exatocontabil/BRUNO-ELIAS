"""V130 — Busca Automática: confirmação + fila sequencial, sem SEFAZ real."""
from __future__ import annotations
import os, sys, tempfile, time
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v130_multi_reg_')
os.environ['EXATO_CF_DEV']='1'
sys.path.insert(0,str(BASE))
import exato_central_fiscal as m  # noqa: E402

m.messagebox.showinfo=lambda *a,**k: None
m.messagebox.showwarning=lambda *a,**k: (_ for _ in ()).throw(AssertionError(f'warning inesperado: {a}'))
m.messagebox.showerror=lambda *a,**k: (_ for _ in ()).throw(AssertionError(f'error inesperado: {a}'))

m.init_database()
m.db_register_company('49894842000123','ELYON LTDA')
m.db_register_company('00000000000191','EMPRESA TESTE')
app=m.App(); app.selected={'Thumbprint':'TESTTHUMB','FriendlyName':'CERTIFICADO TESTE','Document':'00000000000191'}
app._show_webservice_test(); app._open_multi_company_search_dialog(); app.update_idletasks()
print('initial start',repr(app._multi_start_btn['state']), 'confirmed', app._multi_confirmed); assert str(app._multi_start_btn['state'])=='disabled'
app._confirm_multi_company_config(); app.update_idletasks()
assert str(app._multi_start_btn.cget('state'))=='normal'

processed=[]
def fake_run_sync_all():
    cnpj=app.cnpj_var.get(); processed.append(cnpj)
    app.sync_running=True; app._sync_run_id=None
    results={f:{'ok':True,'documents':[],'batches':0,'last_nsu':0,'new_count':0,'duplicate_count':0,'last_info':{},'end_reason':'teste local'} for f in ('nfe','nfce','cte')}
    payload={'ok':True,'documents':[],'results':results,'cnpj':cnpj}
    app.after(30, lambda p=payload: app._finish_sync_all(p))
app._run_sync_all=fake_run_sync_all
app._start_multi_company_search()
deadline=time.time()+6
while app._multi_company_run_active and time.time()<deadline:
    app.update(); time.sleep(0.02)
assert processed==['49894842000123','00000000000191'], processed
assert not app._multi_company_run_active
app._close_multi_company_dialog(); app.destroy()
print('V130_MULTI_COMPANY_REGRESSION_OK')
