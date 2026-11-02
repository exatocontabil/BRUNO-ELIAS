"""V168: o certificado mostrado no topo e no cartão da tela Buscar XML é sempre o mesmo (o escolhido agora)."""
import os, sys, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_cert_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaCert#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaCert#2026')
certs=[{'Subject':'CN=%s'%n,'FriendlyName':'%s:%s'%(n,d),'Thumbprint':'%040X'%i,'NotAfter':'2099-01-01','Status':'Válido','Document':d,'TypeGuess':'Não determinado'}
       for i,(n,d) in enumerate([('A G ATIVIDADES ESTETICAS LTDA','57419457000152'),('JONATHA FERNANDES MACHADO','11111111111')],1)]
m.enumerate_windows_certificates=lambda *a,**k:(certs,'')
app=m.App(current_user=user)
try:
    import time
    t0=time.time()
    while time.time()-t0<2.0: app.update(); time.sleep(.02)      # deixa a leitura inicial de certificados terminar antes
    app._finish_refresh(list(certs),''); app.update()
    app._show_certificate_list('buscar'); app.tree.selection_set('0'); app._on_select(); app.confirm_selection(); app.update()
    assert app.sync_cert_name_label.cget('text')=='A G ATIVIDADES ESTETICAS LTDA' and 'A G ATIVIDADES' in app.header_context.cget('text')
    # o usuário escolhe outro certificado depois que a tela Buscar XML já foi montada
    app._show_certificate_list('buscar'); app.update(); app.tree.selection_set('1'); app._on_select(); app.confirm_selection(); app.update()
    assert app.sync_cert_name_label.cget('text')=='JONATHA FERNANDES MACHADO' and 'JONATHA' in app.header_context.cget('text'),(app.sync_cert_name_label.cget('text'),app.header_context.cget('text'))
    app._show_webservice_test(); app.update()
    assert app.sync_cert_name_label.cget('text')=='JONATHA FERNANDES MACHADO'
    # V168: com o CNPJ confirmado só fica o aviso verde (o botão cinza repetido some); ao mudar o CNPJ o botão volta
    app._show_webservice_test(); app.update()
    app.cnpj_var.set('11222333000181'); app._set_cnpj_confirmed(True); app.update()
    assert not app.cnpj_confirm_btn.winfo_manager()
    app._set_cnpj_confirmed(False); app.update()
    assert app.cnpj_confirm_btn.winfo_manager()=='pack' and app.cnpj_confirm_btn.winfo_ismapped()
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 certificado único: OK')
