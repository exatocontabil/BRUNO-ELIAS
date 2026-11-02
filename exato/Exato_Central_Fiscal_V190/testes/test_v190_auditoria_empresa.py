"""V171: a Auditoria Fiscal tem a sua escolha de empresa (lembrada, independente de Buscar XML); a cópia do Repositório e o Box-e esperam uma busca em andamento."""
import inspect, os, sys, tempfile, shutil, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_aud_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaAud#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaAud#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
A='57419457000152'; B='12345678000195'; C='11222333000181'
for c,n in ((A,'A G ATIVIDADES ESTETICAS LTDA'),(B,'ELETROTAK MANUTENCAO LTDA'),(C,'JC AUTO PECAS LTDA')): m.db_register_company(c,n)
avisos=[]; m.messagebox.showinfo=lambda *a,**k:avisos.append(a); m.messagebox.showwarning=lambda *a,**k:avisos.append(a)
app=m.App(current_user=user)
import traceback
app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
try:
    app.geometry('1366x650+0+0'); app.update()
    app.cnpj_var.set(A); app._show_audit(); app.update()
    # sem escolha própria: acompanha a empresa de Buscar XML
    assert app._audit_cnpj()==A and 'A G ATIVIDADES' in app.audit_company_var.get() and 'A G ATIVIDADES' in app.audit_context.cget('text')
    textos=list(app.audit_company_cb['values']); assert len(textos)==3 and any('ELETROTAK' in t for t in textos) and any('JC AUTO' in t for t in textos),textos
    # escolher outra empresa: vale só na Auditoria
    app.last_audit_result={'fake':1}
    app.audit_company_var.set(next(t for t in textos if 'ELETROTAK' in t)); app._audit_company_picked(); app.update()
    assert app._audit_cnpj()==B and app.cnpj_var.get()==A,(app._audit_cnpj(),app.cnpj_var.get())
    assert 'ELETROTAK' in app.audit_context.cget('text') and '12.345.678/0001-95' in app.audit_meta_labels['cnpj'].cget('text') and app.last_audit_result is None
    assert m.load_config().get('audit_cnpj')==B                                                  # lembrada
    # digitar o CNPJ (ou parte dele) também acha
    app.audit_company_var.set('11.222.333'); app._audit_company_picked(); app.update(); assert app._audit_cnpj()==C and 'JC AUTO' in app.audit_company_var.get()
    # texto que não é de nenhuma empresa: volta para a escolhida
    app.audit_company_var.set('nada parecido'); app._audit_company_picked(); app.update(); assert app._audit_cnpj()==C and 'JC AUTO' in app.audit_company_var.get()
    # sair da Auditoria e voltar: a escolha continua; Buscar XML intocado
    app._show_dashboard(); app.update(); app._show_audit(); app.update(); assert app._audit_cnpj()==C and app.cnpj_var.get()==A
    # reabrir o programa: lembra
    app.destroy(); app=m.App(current_user=user); app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
    app.geometry('1366x650+0+0'); app.update(); app._show_audit(); app.update(); assert app._audit_cnpj()==C and 'JC AUTO' in app.audit_company_var.get()
    # nenhuma função da Auditoria lê mais a empresa de Buscar XML diretamente
    for nome in ('_refresh_audit','_audit_ask_exato_ia','_audit_source_document','_finish_sat_audit','_import_sat_excel_files','_generate_audit_pdf_action','_run_sat_audit'):
        assert 'cnpj_var' not in inspect.getsource(getattr(m.App,nome)),nome
    # janela estreita
    for g in ('1000x600+0+0','1366x650+0+0'): app.geometry(g); app._show_audit(); app.update()
    # ---- a cópia do Repositório e o Box-e esperam uma busca em andamento (mas "Copiar agora" continua valendo)
    app.sync_running=True; assert app._busca_em_andamento()
    app._repo_start(); assert not app._repo_state['rodando']
    app._boxe_start(); assert not app._boxe_state['rodando']
    app.sync_running=False; app._nfse_running=True; app._repo_start(); assert not app._repo_state['rodando']; app._nfse_running=False
    app._repo_cfg()['pasta']=str(Path(os.environ['EXATO_DATA_DIR'])/'srv'); (Path(os.environ['EXATO_DATA_DIR'])/'srv').mkdir()
    app.sync_running=True; app._repo_start(manual=True); assert app._repo_state['rodando']
    t=time.time()
    while app._repo_state['rodando'] and time.time()-t<20: app.update(); time.sleep(.02)
    app.sync_running=False; assert not app._repo_state['rodando']
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V171 auditoria com escolha de empresa: OK')
