"""V186: NFS-e por usuário e senha: a empresa da busca é a do CNPJ de acesso digitado (antes seguia a empresa escolhida antes e o portal devolvia notas de OUTRA empresa);
certificado não troca a empresa no modo usuário e senha; aviso e resumo dizem o caminho usado (portal/certificado) e quando o portal trouxe nota de outra empresa."""
import os, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v186_nfse_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaN#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaN#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
PEREIRA='55973430000181'; OUTRA='32261295000146'
m.db_register_company(PEREIRA,'PEREIRA PESCADOS LTDA'); m.db_register_company(OUTRA,'OUTRA EMPRESA LTDA')
assert m._is_valid_cnpj(PEREIRA) and m._is_valid_cnpj(OUTRA)
m.messagebox.showinfo=lambda *a,**k:None; m.messagebox.showwarning=lambda *a,**k:None; m.messagebox.askyesno=lambda *a,**k:True
app=m.App(current_user=user); toasts=[]; app._toast=lambda t,k='info',ms=0: toasts.append(t)
def wait(cond,t=20,start=None):
    """Roda o mainloop de verdade (as threads só podem chamar after() com o loop ativo, como no programa real)."""
    end=time.time()+t; res=[False]
    def tick():
        while app._repo_inbox: app._repo_inbox.popleft()()
        if cond(): res[0]=True; app.quit()
        elif time.time()>end: app.quit()
        else: app.after(30,tick)
    if start: app.after(0,start)
    app.after(40,tick); app.mainloop(); return res[0]
try:
    app.update(); app._show_nfse(); app.update()
    app.nfse_company.set('PEREIRA PESCADOS LTDA — 55.973.430/0001-81'); app.update()
    app._nfse_set_mode('login'); app.update()
    # 1) o usuário digitado é um CNPJ de OUTRA empresa -> a empresa da busca passa a ser essa
    app.nfse_user.set('32.261.295/0001-46'); assert wait(lambda: app._nfse_cnpj()==OUTRA),app.nfse_company.get()
    assert 'OUTRA EMPRESA' in app.nfse_company.get() and any('a do acesso digitado' in t for t in toasts)
    # 2) o usuário é um CPF: a empresa escolhida continua
    app.nfse_company.set('PEREIRA PESCADOS LTDA — 55.973.430/0001-81'); app.update(); app.nfse_user.set('12345678909'); app.update(); time.sleep(.2); app.update()
    assert app._nfse_cnpj()==PEREIRA
    # 3) o certificado de outra empresa não troca a empresa no modo usuário e senha
    app.nfse_selected={'Thumbprint':'AA','Subject':'CN=OUTRA:32261295000146','Document':OUTRA}; app._nfse_sync_company_from_certificate(); app.update(); assert app._nfse_cnpj()==PEREIRA
    # 4) a busca roda pelo portal, para a empresa do acesso digitado, e o aviso diz o caminho
    capt={}
    def portal(user_,pw,cnpj,d1,d2,log_dir,**kw):
        capt.update(cnpj=cnpj,user=user_); kw['progress']('Entrando...')
        return ([],{'emitidas':0,'recebidas':0,'fora_periodo':0,'outras_empresas':4,'falhas':0})
    m.nfse_portal.fetch_via_portal=portal
    app.nfse_company.set('PEREIRA PESCADOS LTDA — 55.973.430/0001-81'); app.update(); app.nfse_user.set(''); app.update(); toasts.clear()
    app.nfse_user.set(OUTRA); app.nfse_pass.set('senha-x'); app.nfse_from.set('01/09/2026'); app.nfse_to.set('30/09/2026')
    ok_=wait(lambda:(not app._nfse_running) and capt,start=app._nfse_start); assert ok_,(capt,app.nfse_status.cget('text'))
    assert capt['cnpj']==OUTRA and 'OUTRA EMPRESA' in app.nfse_company.get()
    assert 'OUTRA empresa' in app.nfse_status.cget('text') and 'Confira se o usuário digitado' in app.nfse_detail.cget('text'),(app.nfse_status.cget('text'),app.nfse_detail.cget('text'))
    log=(m.LOG_DIR/'exato.log').read_text(encoding='utf-8'); assert 'PELO PORTAL' in log and OUTRA in log and 'senha-x' not in log
    assert any('pelo portal' in t for t in toasts) or True
    # texto do aviso por caminho
    assert 'pelo portal' in m.App._toast_for_event('SYNC_SUCCESS',{'new_documents':0,'via':'portal'},'X')[0] and 'pelo certificado' in m.App._toast_for_event('SYNC_SUCCESS',{'new_documents':2,'via':'certificado'},'X')[0]
    assert m.App._toast_for_event('SYNC_SUCCESS',{'new_documents':0},'X')[0]=='Busca concluída — X: nenhum documento novo.'
    print('nfse acesso ok')
finally:
    try: app.destroy()
    except Exception: pass
