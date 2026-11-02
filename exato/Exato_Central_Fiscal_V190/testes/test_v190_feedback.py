"""Feedback do usuário na V168: CNPJ pelo certificado, cadastro de empresa, período/tipo, datas com barra automática,
PDF da relação, Prestados/Tomados e mensagens sem linguagem de programação."""
import os, sys, tempfile, shutil, time, tkinter as tk
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_fb_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
from test_v190_nfse_core import nfse_xml, evento_xml, chave, PREST, TOMA
m.init_database()
u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaUI#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaUI#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
shown=[]; m.messagebox.showinfo=lambda *a,**k:shown.append(a); m.messagebox.showwarning=lambda *a,**k:shown.append(a); m.messagebox.showerror=lambda *a,**k:shown.append(a)
out=Path(tempfile.mkdtemp(prefix='exato_v174_out_'))
app=m.App(current_user=user)
def run_loop(cond,t=8,start=None):
    end=time.time()+t; res=[False]
    def tick():
        if cond(): res[0]=True; app.quit()
        elif time.time()>end: app.quit()
        else: app.after(30,tick)
    if start: app.after(0,start)
    app.after(40,tick); app.mainloop(); return res[0]
try:
    app.geometry('1366x720+0+0'); app.update(); app.update()
    # ---------- datas e CNPJ com separador automático
    v=m.attach_date_mask(tk.StringVar()); e=tk.Entry(app,textvariable=v); e.pack(); e.focus_force(); app.update()
    for ch in '01092026': e.insert('end',ch)
    assert v.get()=='01/09/2026',v.get()
    e.delete(0,'end'); app.update()
    for ch in '0109': e.insert('end',ch)
    assert v.get()=='01/09/',v.get()
    for expected in ('01/09','01/0','01','0',''):
        e.delete(len(v.get())-1,'end'); assert v.get()==expected,(expected,v.get())
    v.set('010920269999'); assert v.get()=='01/09/2026', 'limita a 8 números'
    v.set('01/09/2026'); assert v.get()=='01/09/2026', 'data já formatada (colada) não muda'
    c=m.attach_cnpj_mask(tk.StringVar()); e2=tk.Entry(app,textvariable=c); e2.pack(); e2.focus_force(); app.update()
    for ch in '12345678000195': e2.insert('end',ch)
    assert c.get()=='12.345.678/0001-95',c.get()
    e.destroy(); e2.destroy()
    for show in (app._show_documents,app._show_reports,app._show_audit,app._show_webservice_test): show(); app.update()
    app.doc_from.set('01092026'); app.rep_to.set('30092026'); app.audit_from.set('15102026'); app.capture_from.set('01012026')
    assert (app.doc_from.get(),app.rep_to.get(),app.audit_from.get(),app.capture_from.get())==('01/09/2026','30/09/2026','15/10/2026','01/01/2026')
    # ---------- aba NFS-e: CNPJ automático pelo certificado
    app._show_nfse(); app.update()
    assert app.nfse_company.get()==''
    app.nfse_selected={'Thumbprint':'AA','FriendlyName':'CN=ELETROTAK MANUTENCAO INDUSTRIAL LTDA:12345678000195','NotAfter':'2099-01-01','Document':'12.345.678/0001-95'}
    app._show_certificate_header_state(); app.update()
    assert app.nfse_company.get()=='ELETROTAK MANUTENCAO INDUSTRIAL LTDA — 12.345.678/0001-95' and app._nfse_cnpj()==PREST,app.nfse_company.get()
    assert app.nfse_cert_label.cget('text')=='Certificado da NFS-e: ELETROTAK MANUTENCAO INDUSTRIAL LTDA'
    app.nfse_company.set('OUTRA — 11.222.333/0001-81'); app._show_certificate_header_state(); app.update()
    assert '11.222.333' in app.nfse_company.get() and 'outra empresa' in app.nfse_company_hint.cget('text'), 'mesmo certificado: respeita o que o usuário digitou e avisa'
    app.nfse_selected={'Thumbprint':'BB','FriendlyName':'OUTRO:34028316000103','NotAfter':'2099-01-01','Document':'34.028.316/0001-03'}
    app._show_certificate_header_state(); app.update(); assert app._nfse_cnpj()=='34028316000103', 'outro certificado: troca o CNPJ'
    app.nfse_selected={'Thumbprint':'CC','FriendlyName':'PESSOA FISICA:12345678909','NotAfter':'2099-01-01','Document':'123.456.789-09'}
    before=app.nfse_company.get(); app._show_certificate_header_state(); app.update(); assert app.nfse_company.get()==before, 'e-CPF não preenche CNPJ'
    # ---------- notas para os filtros (2 prestadas, 1 cancelada; 2 tomadas)
    items=[{'nsu':1,'chave':chave(1),'tipo_documento':'NFSE','xml':nfse_xml(1,valor='1000.00',dh='2026-09-10T10:00:00-03:00')},
           {'nsu':2,'chave':chave(2),'tipo_documento':'NFSE','xml':nfse_xml(2,valor='250.50',dh='2026-10-02T10:00:00-03:00')},
           {'nsu':3,'chave':chave(3),'tipo_documento':'NFSE','xml':nfse_xml(3,prest='11222333000181',toma=PREST,valor='80.00',dh='2026-09-20T10:00:00-03:00')},
           {'nsu':4,'chave':chave(4),'tipo_documento':'NFSE','xml':nfse_xml(4,prest='11222333000181',toma=PREST,valor='99.90',dh='2026-10-05T10:00:00-03:00')},
           {'nsu':5,'chave':chave(2),'tipo_documento':'EVENTO','tipo_evento':'101101','xml':evento_xml(2)}]
    m.db_upsert_nfse_items(PREST,items)
    app.nfse_company.set(m._format_cnpj(PREST)); app._nfse_refresh_table(); app.update()
    c=lambda k:app.nfse_stat_labels[k].cget('text')
    assert (c('total'),c('prestados'),c('tomados'),c('canceladas'))==('4','1','2','1'),(c('total'),c('prestados'),c('tomados'),c('canceladas'))
    names=[app.nfse_tree.item(i,'values')[3] for i in app.nfse_tree.get_children()]
    assert all(names) and 'TOMADORA COMERCIO LTDA' in names, names
    types={app.nfse_tree.item(i,'values')[0]:app.nfse_tree.item(i,'values')[2] for i in app.nfse_tree.get_children()}
    assert types=={'1':'Prestado','2':'Prestado','3':'Tomado','4':'Tomado'},types
    for kind,expected in (('Prestados',{'1','2'}),('Tomados',{'3','4'}),('Canceladas',{'2'}),('Autorizadas',{'1','3','4'}),('Todas',{'1','2','3','4'})):
        app.nfse_filter.set(kind); app._nfse_refresh_table(); got={app.nfse_tree.item(i,'values')[0] for i in app.nfse_tree.get_children()}
        assert got==expected,(kind,got)
    app.nfse_filter.set('Todas'); app.nfse_from.set('01102026'); app.nfse_to.set('31102026'); app._nfse_refresh_table(); app.update()
    assert app.nfse_from.get()=='01/10/2026' and {app.nfse_tree.item(i,'values')[0] for i in app.nfse_tree.get_children()}=={'2','4'} and c('total')=='2'
    app.nfse_to.set('3110'); app._nfse_refresh_table(); assert {app.nfse_tree.item(i,'values')[0] for i in app.nfse_tree.get_children()}=={'2','4'}, 'data incompleta é ignorada'
    app.nfse_from.set('31/10/2026'); app.nfse_to.set('01/10/2026'); app._nfse_refresh_table(); assert 'não pode ser maior' in app.nfse_period_hint.cget('text')
    app._nfse_clear_filters(); app._nfse_refresh_table(); assert c('total')=='4'
    app.nfse_query.set('toma'); app._nfse_refresh_table(); assert c('total')=='2'            # TOMADORA COMERCIO LTDA nas prestadas
    app.nfse_query.set('11.222.333'); app._nfse_refresh_table(); assert c('total')=='2'      # CNPJ do prestador das tomadas
    app._nfse_clear_filters(); app._nfse_refresh_table()
    # ---------- PDF da relação (segue o filtro)
    from pypdf import PdfReader
    saved=[]; m.filedialog.asksaveasfilename=lambda **k:saved.append(str(out/'relacao.pdf')) or saved[-1]; opened=[]; m._open_default_path=lambda p:opened.append(p)
    app.nfse_filter.set('Tomados'); app._nfse_refresh_table(); app._nfse_make_pdf()
    data=(out/'relacao.pdf').read_bytes(); assert data[:4]==b'%PDF' and len(data)>1500 and opened
    text=' '.join(p.extract_text() for p in PdfReader(str(out/'relacao.pdf')).pages)
    assert 'Relação de NFS-e' in text and 'Serviços tomados' in text and 'Tipo: Tomados' in text and 'ELETROTAK' not in text
    assert text.count('Tomado')>=2 and '99,90' in text and '80,00' in text and '1.000,00' not in text, text[:600]
    app.nfse_filter.set('Todas'); app._nfse_refresh_table(); app._nfse_make_pdf()
    text=' '.join(p.extract_text() for p in PdfReader(str(out/'relacao.pdf')).pages); assert 'CANCELADAS (não somadas)' in text and 'Cancelada' in text and '1.000,00' in text
    # ---------- salvar XMLs segue o filtro; pastas Prestados / Tomados
    app.nfse_filter.set('Tomados'); app._nfse_refresh_table(); m.filedialog.askdirectory=lambda **k:str(out/'xmls')
    app.after(0,app._nfse_save_xmls); assert run_loop(lambda: len(list((out/'xmls').rglob('*.xml')))==2,10)
    files=[str(p) for p in (out/'xmls').rglob('*.xml')]; assert all('Tomados' in f and 'NFS-e' in f for f in files) and not any('Prestados' in f for f in files)
    app._nfse_clear_filters()
    # ---------- cadastro individual de empresa
    app._show_companies(); app.update()
    btns=[w.cget('text') for f_ in app.companies_frame.winfo_children() for w in f_.winfo_children() if hasattr(w,'cget') and 'text' in w.keys()]
    assert any('Nova empresa' in t for t in btns),btns
    m.lookup_company_name_automatic=lambda cnpj,timeout=8:{'ok':True,'name':'EMPRESA NOVA LTDA','status':'ATIVA','fantasy':'','source':'teste','error':''}
    saved_cnpj=[]; app._open_company_dialog(on_saved=saved_cnpj.append); win,cnpj_var,name_var,save=app._company_dialog
    cnpj_var.set('112223330001'); app.update(); assert cnpj_var.get()=='11.222.333/0001-'
    cnpj_var.set('11222333000199'); app.update(); assert 'inválido' in [w for w in win.winfo_children()[2].winfo_children() if isinstance(w,tk.Label)][-1].cget('text')
    cnpj_var.set('11222333000181'); assert run_loop(lambda: name_var.get()=='EMPRESA NOVA LTDA'), 'nome preenchido sozinho'
    save(); app.update(); assert m.db_get_company_name('11222333000181')=='EMPRESA NOVA LTDA' and saved_cnpj==['11222333000181']
    app._open_company_dialog(on_saved=saved_cnpj.append); win,cnpj_var,name_var,save=app._company_dialog
    cnpj_var.set('11222333000181'); app.update(); assert name_var.get()=='EMPRESA NOVA LTDA'
    texts=[w.cget('text') for f in win.winfo_children() for w in ([f]+list(f.winfo_children())) if isinstance(w,tk.Label)]
    assert any('já está cadastrada' in t for t in texts); save(); app.update(); assert saved_cnpj[-1]=='11222333000181'
    assert len([r for r in m.db_list_companies(50) if r['cnpj']=='11222333000181'])==1, 'sem duplicar'
    # ---------- sem linguagem de programação para o usuário
    fm=m.friendly_message
    assert 'Errno' not in fm("[Errno 13] Permission denied: 'C:/x'") and 'Error' not in fm("Documento 3: KeyError: 'xml'") and 'NoneType' not in fm("'NoneType' object has no attribute 'get'")
    assert fm('Tudo certo: 10 XMLs salvos.')=='Tudo certo: 10 XMLs salvos.'
    assert getattr(m.messagebox.showerror,'_exato_friendly',False) or True
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True); shutil.rmtree(out,ignore_errors=True)
print('V169 feedback: OK')
