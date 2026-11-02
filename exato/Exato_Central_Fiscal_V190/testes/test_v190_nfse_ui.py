"""Aba NFS-e: navegação, formas de acesso, busca pelo ADN com transporte simulado, importação e exportação."""
import os, sys, tempfile, shutil, json, time, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_nfseui_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
from test_v190_nfse_core import nfse_xml, evento_xml, chave, pack, PREST, TOMA
m.init_database()
u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaUI#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaUI#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
infos=[]; m.messagebox.showinfo=lambda *a,**k:infos.append(a); m.messagebox.showwarning=lambda *a,**k:infos.append(a)
m.messagebox.askyesno=lambda *a,**k:False; m.messagebox.showerror=lambda *a,**k:infos.append(a)
out=Path(tempfile.mkdtemp(prefix='exato_v174_ui_out_'))
app=m.App(current_user=user)
app._busca_dialog=lambda *a: ('tudo',False)          # V173: o aviso 'já tem notas' é testado em test_v190_busca_inteligente; aqui vale o período digitado
def wait(cond,t=8,start=None):
    """Roda o mainloop de verdade (as threads só podem chamar after() com o loop ativo, como no programa real)."""
    end=time.time()+t; res=[False]
    def tick():
        if cond(): res[0]=True; app.quit()
        elif time.time()>end: app.quit()
        else: app.after(30,tick)
    if start: app.after(0,start)
    app.after(40,tick); app.mainloop(); return res[0]
try:
    app.geometry('1366x700+0+0'); app.update(); app.update()
    # navegação e atalho
    app.focus_force(); app.event_generate('<Control-Key-0>'); app.update(); app.update()
    assert app.header_crumb.cget('text')=='NFS-e' and app.nfse_frame.winfo_ismapped()
    assert 'Ctrl+0' in app._nav_shortcut_labels.values()
    # formas de acesso
    assert app.nfse_mode.get()=='cert' and app.nfse_cert_box.winfo_manager() and not app.nfse_login_box.winfo_manager()
    app._nfse_set_mode('login'); app.update(); assert app.nfse_login_box.winfo_manager() and not app.nfse_cert_box.winfo_manager()
    app._nfse_set_mode('cert'); app.update()
    # empresa
    app.nfse_company.set('12.345.678/0001-9'); app.update(); assert '14 dígitos' in app.nfse_company_hint.cget('text')
    app.nfse_company.set('12.345.678/0001-95'); app.update(); assert '✓' in app.nfse_company_hint.cget('text')
    # sem certificado: não busca
    app._nfse_start(); app.update(); assert not app._nfse_running
    # busca com certificado (transporte simulado: 2 lotes e depois nada)
    app.nfse_selected={'Thumbprint':'AABB','FriendlyName':'PRESTADORA:12345678000195','NotAfter':'2099-01-01'}
    pages={0:[{'NSU':1,'ChaveAcesso':chave(1),'TipoDocumento':'NFSE','ArquivoXml':pack(nfse_xml(1))},{'NSU':2,'ChaveAcesso':chave(2),'TipoDocumento':'NFSE','ArquivoXml':pack(nfse_xml(2,prest='11111111000191',toma=PREST))}],
           2:[{'NSU':3,'ChaveAcesso':chave(1),'TipoDocumento':'EVENTO','TipoEvento':'101101','ArquivoXml':pack(evento_xml(1))}]}
    calls=[]
    def fake(url,thumb):
        calls.append((url,thumb)); nsu=int(url.split('/DFe/')[1].split('?')[0])
        return (200,json.dumps({'StatusProcessamento':'DOCUMENTOS_LOCALIZADOS','LoteDFe':pages[nsu]})) if nsu in pages else (404,json.dumps({'StatusProcessamento':'NENHUM_DOCUMENTO_LOCALIZADO'}))
    app._nfse_transport=fake; m.nfse_mod.ADN_PAUSE_SECONDS=0
    ok_=wait(lambda: (not app._nfse_running) and calls, start=app._nfse_start); assert ok_, ('busca terminou', app.nfse_status.cget('text'), app.nfse_detail.cget('text'), app._nfse_running, calls)
    assert 'Busca concluída' in app.nfse_status.cget('text'),app.nfse_status.cget('text')
    assert m.get_saved_nsu(app.config_data,PREST,'nfse')==3 and calls[0][1]=='AABB'
    st=m.db_nfse_stats(PREST); assert st['total']==2 and st['canceladas']==1 and st['entradas']==1,st
    assert len(app.nfse_tree.get_children())==2 and app.nfse_stat_labels['total'].cget('text')=='2'
    runs=m.db_list_runs(5,PREST); assert runs[0]['status']=='Concluído' and runs[0]['new_count']==2
    # segunda busca continua do último NSU (sem repetir)
    calls.clear(); assert wait(lambda: (not app._nfse_running) and calls, start=app._nfse_start); assert '/DFe/3?' in calls[0][0] and m.db_nfse_stats(PREST)['total']==2
    # erro amigável (403)
    app._nfse_transport=lambda url,thumb:(403,'{}'); assert wait(lambda: not app._nfse_running, start=app._nfse_start)
    assert 'não foi concluída' in app.nfse_status.cget('text') and 'recusou o certificado' in app.nfse_detail.cget('text')
    assert m.db_list_runs(1,PREST)[0]['status']=='Não concluído'
    # importação de XML/ZIP
    d=Path(tempfile.mkdtemp()); zp=d/'lote.zip'
    with zipfile.ZipFile(zp,'w') as zf: zf.writestr('n9.xml',nfse_xml(9)); zf.writestr('outra.xml',nfse_xml(10,prest='11111111000191',toma='22222222000191'))
    import tkinter.filedialog as fd; m.filedialog.askopenfilenames=lambda **k:[str(zp)]
    app._nfse_import_files(); app.update(); assert m.db_nfse_stats(PREST)['total']==3 and '1 NFS-e nova' in app.nfse_detail.cget('text') and 'não pertencem' in app.nfse_detail.cget('text')
    # salvar XMLs (exportador existente com suporte a NFS-e)
    m.filedialog.askdirectory=lambda **k:str(out)
    app.after(0,app._nfse_save_xmls); assert wait(lambda: len(list(out.rglob('*.xml')))==3,10)
    assert all('NFS-e' in str(p) for p in out.rglob('*.xml')) and len(list(out.rglob('*.xml')))==3
    # ver em Documentos filtra NFS-e e o rodapé de contagem mostra o tipo
    app._nfse_open_documents(); app.update(); assert app.doc_family.get()=='NFS-e' and len(app._doc_row_map)==3 and app.doc_summary_labels['nfse'].cget('text')=='3'
    # acesso por usuário e senha: a senha digitada vai só ao portal (guardada, protegida, só se pedirem) e o resultado entra no Arquivo Fiscal Local
    captured={}
    def fake_portal(user,password,cnpj,d1,d2,log_dir,**kw):
        captured.update(user=user,password=password,cnpj=cnpj,d1=d1,d2=d2); kw['progress']('Entrando...')
        return ([{'nsu':0,'chave':chave(30),'tipo_documento':'NFSE','tipo_evento':'','xml':nfse_xml(30)}],{'emitidas':1,'recebidas':0,'fora_periodo':0,'outras_empresas':0,'falhas':0})
    m.nfse_portal.fetch_via_portal=fake_portal
    app._nfse_set_mode('login'); app.nfse_user.set('12345678000195'); app.nfse_pass.set('minha-senha'); app.nfse_from.set('01/09/2026'); app.nfse_to.set('30/09/2026')
    assert wait(lambda: (not app._nfse_running) and captured, start=app._nfse_start)
    assert captured['password']=='minha-senha' and str(captured['d1'])=='2026-09-01' and str(captured['d2'])=='2026-09-30' and app.nfse_pass.get()=='', 'senha limpa da tela'
    assert 'Busca concluída' in app.nfse_status.cget('text') and m.db_nfse_stats(PREST)['total']==4
    assert 'minha-senha' not in json.dumps(app.config_data,default=str) and 'minha-senha' not in (m.LOG_DIR/'exato.log').read_text(encoding='utf-8')
    # V168: senha lembrada (protegida), sem texto aberto em lugar nenhum
    acc=(m.APP_DATA_DIR/'nfse_acessos.json').read_text(encoding='utf-8')
    assert m.ACESSOS.get_login(PREST)==('12345678000195','minha-senha') and 'minha-senha' not in acc and 'minha-senha' not in json.dumps(app.config_data,default=str)
    app.nfse_pass.set(''); app.nfse_from.set('31/02/2026'); app.nfse_to.set('30/09/2026'); app._nfse_start(); app.update(); assert not app._nfse_running   # data inválida: nada roda
    # a senha salva é usada quando o campo fica em branco; o usuário e o aviso aparecem ao escolher a empresa
    app.nfse_from.set('01/09/2026'); app.nfse_to.set('30/09/2026'); captured.clear()
    assert wait(lambda: (not app._nfse_running) and captured, start=app._nfse_start)
    assert captured['password']=='minha-senha'
    app.nfse_user.set(''); app._nfse_on_company_change(); app.update(); assert app.nfse_user.get()=='12345678000195' and 'Senha salva' in app.nfse_saved_label.cget('text')
    # sem período: usa o mês anterior fechado, sem perguntar
    inf_=app._busca_info(PREST,'nfse')          # (antes da busca: a própria busca atualiza a cobertura)
    app.nfse_from.set(''); app.nfse_to.set(''); captured.clear()
    assert wait(lambda: (not app._nfse_running) and captured, start=app._nfse_start)
    # V173: busca inteligente: com notas já guardadas, sem período = desde a cobertura (menos 3 dias de folga) até hoje (sem notas guardadas: mês anterior, em test_v190_busca_inteligente)
    s1=inf_['inicio']; e1=__import__('datetime').date.today()
    assert inf_['ate'] and str(captured['d1'])==str(s1) and str(captured['d2'])==str(e1) and app.nfse_from.get()==s1.strftime('%d/%m/%Y'),(captured,inf_)
    # esquecer a senha
    m.messagebox.askyesno=lambda *a,**k:True
    app._nfse_forget_access(); app.update(); assert not m.ACESSOS.has_password(PREST) and app.nfse_saved_label.cget('text')==''
    # sem "lembrar": nada é guardado
    app.nfse_remember.set(False); app.nfse_pass.set('outra-senha'); captured.clear()
    assert wait(lambda: (not app._nfse_running) and captured, start=app._nfse_start)
    assert captured['password']=='outra-senha' and not m.ACESSOS.has_password(PREST) and 'outra-senha' not in (m.APP_DATA_DIR/'nfse_acessos.json').read_text(encoding='utf-8')
    app.nfse_remember.set(True)
    # V168: "Mostrar o navegador" e mensagem quando o portal recusa todos os downloads
    seen={}
    def fake_portal3(user,password,cnpj,d1,d2,log_dir,**kw):
        seen['opts']=kw.get('browser_options'); return ([],{'emitidas':0,'recebidas':0,'fora_periodo':0,'outras_empresas':0,'falhas':4})
    m.nfse_portal.fetch_via_portal=fake_portal3
    app.nfse_pass.set('x'); app.nfse_from.set('01/09/2026'); app.nfse_to.set('30/09/2026')
    assert wait(lambda: (not app._nfse_running) and seen, start=app._nfse_start)
    assert seen['opts'] is None and 'Mostrar o navegador' in app.nfse_detail.cget('text') and 'nenhum XML foi baixado' in app.nfse_detail.cget('text')
    app.nfse_show_browser.set(True); seen.clear(); app.nfse_pass.set('x')
    assert wait(lambda: (not app._nfse_running) and seen, start=app._nfse_start)
    assert seen['opts']=={'headless':False}
    app.nfse_show_browser.set(False); app._nfse_save_prefs(); m.nfse_portal.fetch_via_portal=fake_portal; m.ACESSOS.forget(PREST)
    # sem senha e sem sessão: avisa e não roda
    app.nfse_pass.set(''); app._nfse_start(); app.update(); assert not app._nfse_running
    # Buscar e salvar tudo: busca e salva os XMLs novos (com PDF e relatório mensal) na pasta dos clientes, sem perguntar
    app.nfse_pdf_var.set(True); app._auto_search_config()['root_folder']=str(out/'auto'); (out/'auto').mkdir(exist_ok=True)
    def fake_portal2(user,password,cnpj,d1,d2,log_dir,**kw):
        return ([{'nsu':0,'chave':chave(31),'tipo_documento':'NFSE','tipo_evento':'','xml':nfse_xml(31,dh='2026-09-12T10:00:00-03:00')}],{'emitidas':1,'recebidas':0,'fora_periodo':0,'outras_empresas':0,'falhas':0})
    m.nfse_portal.fetch_via_portal=fake_portal2
    app.nfse_pass.set('x'); app.nfse_from.set('01/09/2026'); app.nfse_to.set('30/09/2026')
    ok=wait(lambda: any((out/'auto').rglob('Relatorio_mensal*.pdf')), t=25, start=app._nfse_search_and_save)
    assert ok and list((out/'auto').rglob('*.xml')) and list((out/'auto').rglob('Relatorio_mensal_NFS-e_Prestados_2026-09.pdf')), 'salvou sozinho'
    # representação em PDF: mensagem amigável
    app._show_documents(); app.update()
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True); shutil.rmtree(out,ignore_errors=True)
print('V169 NFS-e UI: OK')
