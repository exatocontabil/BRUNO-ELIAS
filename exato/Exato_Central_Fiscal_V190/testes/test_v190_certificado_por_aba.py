"""V170: cada tela (Buscar XML e NFS-e) tem o seu certificado; escolher numa não muda a outra; o botão volta para a tela de origem."""
import os, sys, tempfile, shutil, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_certaba_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaCert#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaCert#2026')
certs=[{'Subject':'CN=%s'%n,'FriendlyName':'%s:%s'%(n,d),'Thumbprint':'%040X'%i,'NotAfter':'2099-01-01','Status':'Válido','Document':d,'TypeGuess':'Não determinado'}
       for i,(n,d) in enumerate([('A G ATIVIDADES ESTETICAS LTDA','57419457000152'),('JONATHA FERNANDES MACHADO','11111111111'),('ELETROTAK MANUTENCAO LTDA','12345678000195')],1)]
m.enumerate_windows_certificates=lambda *a,**k:(certs,'')
# migração: antes da V170 só existia UM certificado escolhido
cfg=m.load_config() if hasattr(m,'load_config') else {}
cfg['selected_certificate_thumbprint']='%040X'%1; cfg['selected_certificate_subject']='CN=A G'; cfg['selected_certificate_document']='57419457000152'
m.save_config(cfg)
avisos=[]; m.messagebox.showinfo=lambda *a,**k:avisos.append(a); m.messagebox.showwarning=lambda *a,**k:avisos.append(a); m.messagebox.showerror=lambda *a,**k:avisos.append(a)
app=m.App(current_user=user)
import traceback
app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
def esperar(cond,t=10):
    fim=time.time()+t
    while time.time()<fim:
        app.update()
        if cond(): return True
        time.sleep(.02)
    return False
def deixar_abrir():
    fim=time.time()+1.2
    while time.time()<fim: app.update(); time.sleep(.02)         # a leitura inicial de certificados do programa roda sozinha logo ao abrir
def nome(c): return m.App._nfse_cert_name(c) if c else None
def ti(i): return str(next(k for k,c in enumerate(app.certificates) if c['Thumbprint']==certs[i]['Thumbprint']))     # a lista da tela é ordenada por nome
def escolher(origem,idx,usar=None):
    idx=ti(idx); app._show_certificate_list(origem); app.update(); app.tree.selection_set(idx); app.tree.focus(idx); app._on_select()
    if usar: app._cert_use.set(usar)
    app.confirm_selection(); app.update()
try:
    deixar_abrir(); app.refresh_certificates(); time.sleep(.3); app._finish_refresh(list(certs),''); app.update()
    # ---- migração: a NFS-e começa igual ao de Buscar XML e grava a escolha própria
    assert nome(app.selected)=='A G ATIVIDADES ESTETICAS LTDA' and nome(app.nfse_selected)=='A G ATIVIDADES ESTETICAS LTDA'
    assert app.config_data['nfse_certificate_thumbprint']=='%040X'%1
    # ---- clicar numa linha só MARCA: nada muda até clicar no botão
    app._show_certificate_list('nfse'); app.update(); assert app.cert_title_label.cget('text')=='Certificado para a NFS-e' and 'NFS-e' in app.continue_btn.cget('text') and not app.cert_use_frame.winfo_ismapped()
    app.tree.selection_set(ti(1)); app._on_select(); app.update()
    assert nome(app.nfse_selected)=='A G ATIVIDADES ESTETICAS LTDA' and nome(app._cert_pick)=='JONATHA FERNANDES MACHADO' and 'JONATHA' in app.selection_label.cget('text')
    # ---- escolher PELA NFS-e: muda só a NFS-e e VOLTA para a NFS-e (não vai para Buscar XML)
    app.confirm_selection(); app.update()
    assert app.current_screen=='nfse' and nome(app.nfse_selected)=='JONATHA FERNANDES MACHADO' and nome(app.selected)=='A G ATIVIDADES ESTETICAS LTDA',(app.current_screen,)
    assert 'JONATHA' in app.nfse_cert_label.cget('text') and 'NFS-e' in app.nfse_cert_label.cget('text') and 'JONATHA' in app.header_context.cget('text')
    assert app.config_data['nfse_certificate_thumbprint']=='%040X'%2 and app.config_data['selected_certificate_thumbprint']=='%040X'%1
    # ---- escolher por Buscar XML: muda só Buscar XML e volta para Buscar XML
    app._show_webservice_test(); app.update(); assert 'A G ATIVIDADES' in app.header_context.cget('text') and app.sync_cert_name_label.cget('text')=='A G ATIVIDADES ESTETICAS LTDA'      # o topo acompanha a tela
    app._close_webservice_test(); app.update(); assert app._cert_origin=='buscar' and app.cert_title_label.cget('text')=='Certificado para Buscar XML' and nome(app._cert_pick)=='A G ATIVIDADES ESTETICAS LTDA'
    escolher('buscar',2)
    assert app.current_screen=='sync' and nome(app.selected)=='ELETROTAK MANUTENCAO LTDA' and nome(app.nfse_selected)=='JONATHA FERNANDES MACHADO' and app.sync_cert_name_label.cget('text')=='ELETROTAK MANUTENCAO LTDA'
    # ---- pelo menu: diz onde usar
    app._show_certificate_list(); app.update(); assert 'Buscar XML: ELETROTAK' in app.cert_inuse_label.cget('text') and 'NFS-e: JONATHA' in app.cert_inuse_label.cget('text'),app.cert_inuse_label.cget('text')
    assert app._cert_origin=='menu' and app.cert_use_frame.winfo_ismapped() and app.cert_title_label.cget('text')=='Certificados'
    escolher('menu',0,'nfse'); assert app.current_screen=='nfse' and nome(app.nfse_selected)=='A G ATIVIDADES ESTETICAS LTDA' and nome(app.selected)=='ELETROTAK MANUTENCAO LTDA'
    escolher('menu',1,'buscar'); assert app.current_screen=='sync' and nome(app.selected)=='JONATHA FERNANDES MACHADO' and nome(app.nfse_selected)=='A G ATIVIDADES ESTETICAS LTDA'
    escolher('menu',2,'both'); assert app.current_screen=='sync' and nome(app.selected)==nome(app.nfse_selected)=='ELETROTAK MANUTENCAO LTDA'
    # ---- as telas de certificado mostram o certificado de quem chamou
    escolher('nfse',0); escolher('buscar',1)
    app._show_certificate_list('nfse'); app.update(); assert nome(app._cert_pick)=='A G ATIVIDADES ESTETICAS LTDA' and app.tree.selection()==(ti(0),)
    app._show_certificate_list('buscar'); app.update(); assert nome(app._cert_pick)=='JONATHA FERNANDES MACHADO' and app.tree.selection()==(ti(1),)
    # ---- botão "Escolher certificado" da NFS-e abre a escolha da NFS-e
    app._show_nfse(); app.update()
    [b for b in app.nfse_cert_box.winfo_children() if str(b.cget('text'))=='Escolher certificado'][0].invoke(); app.update()
    assert app._cert_origin=='nfse' and app.current_screen=='cert'
    # ---- reabrir o programa: cada tela lembra o seu
    app.destroy()
    app=m.App(current_user=user); app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
    deixar_abrir(); app.refresh_certificates(); time.sleep(.3); app._finish_refresh(list(certs),''); app.update()
    assert nome(app.selected)=='JONATHA FERNANDES MACHADO' and nome(app.nfse_selected)=='A G ATIVIDADES ESTETICAS LTDA',(nome(app.selected),nome(app.nfse_selected))
    # ---- certificado da NFS-e que não está mais instalado: só a NFS-e perde; Buscar XML continua
    app.refresh_certificates(); app._finish_refresh([certs[1]],''); app.update()
    assert nome(app.selected)=='JONATHA FERNANDES MACHADO' and app.nfse_selected is None
    app._show_certificate_list('nfse'); app.update(); assert 'não está disponível' in app.selection_label.cget('text') and str(app.continue_btn['state'])=='disabled'
    # ---- NFS-e sem certificado escolhido pergunta e abre a escolha DA NFS-e
    app._show_nfse(); app.update(); perguntas=[]; m.messagebox.askyesno=lambda *a,**k:(perguntas.append(a),True)[1]
    app._nfse_run_certificate('12345678000195'); app.update(); assert perguntas and 'NFS-e' in perguntas[0][1] and app._cert_origin=='nfse'
    # ---- tamanhos pequenos
    for g in ('1366x650+0+0','1000x600+0+0'):
        app.geometry(g); app._show_certificate_list(); app.update(); app._show_certificate_list('nfse'); app.update()
finally:
    try: app.destroy()
    except Exception: pass
    shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V170 certificado por aba: OK')
