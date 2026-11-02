import os, re, sys, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v146_ui_')
sys.path.insert(0,str(ROOT/'programa'))
import exato_central_fiscal as m
m.init_database()
u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL)
m.db_auth_set_password(u['id'],'SenhaUI#2026')
user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaUI#2026')
certs=[{'Subject':'CN=%s'%n,'FriendlyName':n,'Thumbprint':'%040X'%i,'NotAfter':na,'Status':'Válido','Document':d,'TypeGuess':t}
       for i,(n,na,d,t) in enumerate([
           ('ALFA COMERCIO LTDA','2099-01-01','11.111.111/0001-11','Provável A3/token'),
           ('BETA SERVICOS LTDA','2099-01-01','22.222.222/0001-22','Não determinado'),
           ('GAMA INDUSTRIA LTDA',(m.datetime.now()+m.timedelta(days=10)).strftime('%Y-%m-%d'),'33.333.333/0001-33','Não determinado')],1)]
m.enumerate_windows_certificates=lambda *a,**k:(certs,'')
app=m.App(current_user=user)
try:
    assert m.re.match(r'V\d+$',m.APP_VERSION)
    app.update_idletasks(); app.update()
    # Tema: topo claro, barra lateral escura, vermelho Exato.
    assert m.HEADER_BG=='#FFFFFF' and m.SIDEBAR_BG=='#0B1220' and m.RED=='#E11D2E'
    # Todas as telas abrem e o título do topo acompanha a navegação.
    for fn,title in [('_show_dashboard','Início'),('_show_webservice_test','Buscar XML'),('_show_documents','Documentos Fiscais'),
                     ('_show_companies','Empresas'),('_show_audit','Auditoria Fiscal'),('_show_pending','Pendências'),
                     ('_show_history','Histórico'),('_show_reports','Relatórios'),('_show_users','Usuários'),
                     ('_show_maintenance','Manutenção'),('_show_certificate_list','Certificado')]:
        getattr(app,fn)(); app.update_idletasks(); app.update()
        assert app.header_crumb.cget('text')==title,(fn,app.header_crumb.cget('text'))
    # Botões em maiúsculas passam a usar capitalização normal; siglas e documentos fiscais são preservados.
    assert m._sentence_case_button_text('SALVAR XMLs NOVOS')=='Salvar XMLs novos'
    assert m._sentence_case_button_text('DIAGNÓSTICO NF-e')=='Diagnóstico NF-e'
    assert m._sentence_case_button_text('IMPORTAR EMPRESAS (EXCEL)')=='Importar empresas (Excel)'
    assert m._sentence_case_button_text('Auditar')=='Auditar'
    app._show_documents(); app.update()
    assert app.doc_rep_btn.cget('text')=='Ver/gerar representação'
    # Tela Certificado: busca e filtros.
    app._finish_refresh(list(certs),''); app.update()
    assert len(app.tree.get_children())==3
    app._cert_query.set('beta'); app.update()
    assert len(app.tree.get_children())==1
    app._cert_query.set('333.333'); app.update()
    assert len(app.tree.get_children())==1
    app._cert_query.set(''); app._cert_set_filter('token'); app.update()
    assert len(app.tree.get_children())==1
    app._cert_set_filter('expiring'); app.update()
    kids=app.tree.get_children(); assert len(kids)==1 and 'Vence em' in app.tree.item(kids[0],'values')[4]
    app._cert_set_filter('all'); app.update()
    assert len(app.tree.get_children())==3
    # A seleção continua habilitando o botão Continuar e preenchendo o rodapé.
    app.tree.selection_set(app.tree.get_children()[1]); app.update()
    assert str(app.continue_btn['state'])=='normal' and app.selection_label.cget('text')=='BETA SERVICOS LTDA'
    # Layout responsivo: menu completo em 1366 px, menu de ícones em janelas estreitas e botões que quebram de linha.
    app.geometry('1366x650+0+0'); app._show_webservice_test(); app.update(); app.update()
    assert app.sidebar.winfo_width()==232 and app.sidebar_footer.winfo_ismapped()
    app.geometry('1100x680+0+0'); app.update(); app.update()
    assert app.sidebar.winfo_width()==m.RAIL_WIDTH and app.sidebar_footer.winfo_ismapped() and not app.ia_float_bubble.winfo_manager()
    assert app.header_search.cget('text')==''      # menu de ícones: a busca do topo vira só o ícone (V168)
    assert app.nav_documents.cget('text')=='' and app.nav_documents.cget('compound')=='center' and app.nav_documents.cget('image')
    app._show_webservice_test(); app.update(); app.update()
    # Nenhum botão da linha de ações fica fora da PÁGINA (em janelas estreitas a página rola na horizontal).
    page_left=app.page_host.winfo_rootx(); page_right=page_left+app.page_host.winfo_width()
    for b in (app.sync_all_btn,app.multi_company_btn,app.save_btn,app.audit_btn,app.pdf_btn):
        assert b.winfo_rootx()>=page_left and b.winfo_rootx()+b.winfo_width()<=page_right,(b.cget('text'),b.winfo_rootx(),page_right)
    # A página sempre começa no topo (sem centralização vertical do Canvas).
    app._show_companies(); app.update(); app.update()
    assert app.page_host.winfo_y()==0
    app.geometry('1366x650+0+0'); app.update(); app.update()
    assert app.sidebar.winfo_width()==232 and app.nav_documents.cget('text').endswith('Documentos Fiscais') and app.ia_float_bubble.winfo_manager()
    # Em 1366 px (sem rolagem horizontal) todos os botões ficam dentro da área VISÍVEL.
    app._show_webservice_test(); app.update(); app.update()
    assert not app.workspace_hscroll.winfo_ismapped()
    vis_left=app.workspace_canvas.winfo_rootx(); vis_right=vis_left+app.workspace_canvas.winfo_width()
    for b in (app.sync_all_btn,app.multi_company_btn,app.save_btn,app.audit_btn,app.pdf_btn):
        assert b.winfo_rootx()>=vis_left and b.winfo_rootx()+b.winfo_width()<=vis_right,('1366',b.cget('text'),b.winfo_rootx(),vis_right)
    assert 'Ctrl+K' in app.header_search.cget('text')
    # Painel "Hoje": prioriza o que precisa de atenção.
    now=m.datetime(2026,10,2,12,0)
    items=m.build_today_items(
        companies=[{'cnpj':'1','name':'ALFA','last_sync':''},{'cnpj':'2','name':'BETA','last_sync':'2026-10-02T08:00:00'}],
        certificate={'FriendlyName':'ALFA:1','NotAfter':'2026-10-05T00:00:00','Thumbprint':'A'},
        certificates=[{'FriendlyName':'GAMA:3','NotAfter':'2026-10-20T00:00:00','Thumbprint':'B'}],
        runs=[{'status':'Concluído com observações','finished_at':'2026-10-01T10:00:00'}],audits=[],now=now)
    kinds=[(i['severity'],i['action']) for i in items]
    assert kinds[0][0]=='alta' and ('alta','certificate') in kinds and ('alta','companies') in kinds and ('atencao','pending') in kinds, kinds
    assert items[-1]['severity']=='ok' and 'Última busca' in items[-1]['title']
    ok=m.build_today_items([{'cnpj':'2','name':'BETA','last_sync':'2026-10-02T08:00:00'}],{'NotAfter':'2027-05-05T00:00:00'},[],[],[],now=now)
    assert ok[0]['title']=='Tudo em dia'
    app._show_dashboard(); app.update()
    assert len(app.today_body.winfo_children())>=1
    # Selos nas tabelas e telas vazias com orientação.
    assert m.App._doc_status_badge('Cancelado')==('✕ Cancelado','cancelado')
    assert m.App._run_status_badge('Concluído com observações')[1]=='run_warn'
    app._show_documents(); app._refresh_documents_list(); app.update()
    assert app.doc_tree in app._empty_states, 'tela vazia de documentos'
    app._show_history(); app._refresh_history(); app.update()
    assert app.history_tree in app._empty_states
    # Contador de pendências no menu (bolinha), no menu completo e no menu de ícones.
    import sqlite3
    c=sqlite3.connect(m.DB_PATH); c.execute("INSERT INTO sync_runs(cnpj,started_at,finished_at,status,total_found,new_count,duplicate_count,error_text) VALUES('11111111000191','2026-10-01T10:00:00','2026-10-01T10:05:00','Concluído com observações',1,0,1,'x')"); c.commit(); c.close()
    app._update_pending_badge(); app.update()
    assert app._pending_total>=1 and app.pending_badge.cget('text')==str(app._pending_total) and app.pending_badge.winfo_manager()=='place'
    app._update_pending_badge(25); app.update(); assert app.pending_badge.cget('text')=='9+'
    app.geometry('1100x680+0+0'); app.update(); app.update()
    assert app.pending_badge.winfo_manager()=='place' and app.nav_pending.cget('text')==''
    app.geometry('1366x650+0+0'); app.update(); app.update()
    assert app.nav_pending.cget('text').endswith('Pendências')
    app._update_pending_badge(0); app.update(); assert not app.pending_badge.winfo_manager()
    # Exatinho: o painel flutua e não muda a largura do menu.
    app._exatinho_open_panel(first=True); app.update()
    assert app.sidebar.winfo_width()==232 and app.ia_sidebar_interaction.winfo_x()>=232
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 theme UI: OK')
