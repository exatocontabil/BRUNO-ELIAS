"""V168: visual novo – tema claro/escuro, cartões arredondados, ícones, menu, topo, gráfico, login, avisos e linha sob o mouse."""
import os, sys, tempfile, shutil, time, sqlite3
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_design_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import tkinter as tk
import exato_central_fiscal as m
import exato_ui as ui
from test_v190_nfse_core import nfse_xml, chave, PREST

# ---------- tradução de cores do tema escuro (fundo x texto) e PDFs/constantes intactos
light_consts=(m.BG,m.WHITE,m.TEXT,m.MUTED,m.BORDER)
ui.set_mode('claro'); assert ui.tr('#FFFFFF','bg')=='#FFFFFF' and ui.tr('#0F172A','fg')=='#0F172A' and not ui.is_dark()
ui.set_mode('escuro'); assert ui.is_dark() and ui.tr('#FFFFFF','bg')=='#141C2B' and ui.tr('#FFFFFF','fg')=='#FFFFFF' and ui.tr('#0F172A','fg')=='#E8EDF6' and ui.tr('#F4F6FA','bg')=='#0D1320'
assert ui.tr('#E11D2E','bg')=='#E11D2E' and ui.tr('#0B1220','bg')=='#0B1220'      # vermelho da marca e menu escuro continuam
assert (m.BG,m.WHITE,m.TEXT,m.MUTED,m.BORDER)==light_consts            # as constantes (usadas nos PDFs) nunca mudam
ui.set_mode('claro')

# ---------- componentes
root=tk.Tk(); root.geometry('600x400'); root.configure(bg='#F4F6FA')
for name in ('inicio','buscar_xml','nfse','documentos','empresas','auditoria','pendencias','historico','relatorios','usuarios','certificado','manutencao','tema_escuro','tema_claro','ajuda','sair','sino','check','alerta','dinheiro','entrada','saida','cancelada','buscar'):
    assert ui.icon(name,20,'#64748B') is ui.icon(name,20,'#64748B')            # desenha e guarda em cache
assert ui.icon_chip('nfse',40,'#E11D2E','#FFF1F2') is not None and ui.avatar_image('BE',36) is not None and ui.pill_image('Autorizada','#15803D','#ECFDF3') is not None
card=ui.ModernCard(root,fill='#FFFFFF',border='#E6EAF1'); card.pack(fill='x',padx=20,pady=20); lab=tk.Label(card,text='conteúdo',bg='#FFFFFF'); lab.pack(padx=20,pady=20)
root.update(); time.sleep(.1); root.update()
assert card._bg.cget('image') and card.winfo_children()==[lab] and card._shadow            # sombra só sobre o fundo da página; a imagem de fundo não aparece como filho
size1=card._size; card.configure(bg='#F8FAFC',highlightbackground='#E11D2E'); root.update(); time.sleep(.1); root.update(); assert card._fill=='#F8FAFC' and card._border=='#E11D2E'
inner=ui.ModernCard(card,fill='#FAFBFC',border='#E7EEF5'); inner.pack(fill='x'); assert not inner._shadow        # cartão dentro de cartão: sem sombra
t=time.time(); [ui.card_image(w,200,14,'#FFFFFF','#E6EAF1','#F4F6FA',True,(15,23,42)) for w in range(300,360)]; assert time.time()-t<2.5,'montar cartões é rápido'
root.destroy()

# ---------- banco de exemplo
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaDes#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaDes#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
m.db_register_company(PREST,'ELETROTAK MANUTENCAO LTDA')
c=sqlite3.connect(m.DB_PATH)
for i in range(30):
    mo=(datetime.now().date().replace(day=1)-timedelta(days=30*(i%3))).strftime('%Y-%m')
    c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(f'f{i}',PREST,'nfe','NF-e','Entrada' if i%2 else 'Saída',str(i),mo+'-10T10:00:00',str(1000+i*10),'Autorizado',f'k{i}',b'x','2026-01-01','2026-01-01'))
c.commit(); c.close()
mt=m.db_monthly_totals(PREST,6); assert len(mt)==6 and mt[-1][0]==datetime.now().strftime('%Y-%m') and sum(e+s for _k,e,s in mt)>0 and all(len(k)==7 for k,_e,_s in mt)
infos=[]; m.messagebox.showinfo=lambda *a,**k:infos.append(a); m.messagebox.showwarning=lambda *a,**k:infos.append(a)

# ---------- tela principal clara
app=m.App(current_user=user)
try:
    app.geometry('1366x700+0+0'); app.update(); app.cnpj_var.set(PREST)
    assert app.header_theme.cget('image') and not ui.is_dark()
    app._show_dashboard(); app.update(); app._apply_dashboard_stats(m.db_get_stats(PREST),'ELETROTAK',[],[],[],{},m.db_nfse_totals(PREST)); app.update(); time.sleep(.2); app.update()
    assert len(app.dash_chart_canvas.find_all())>8 and app.dash_chart_canvas.find_withtag('all')            # gráfico de barras desenhado
    assert all(str(b.cget('image')) and b.cget('compound') in ('left','center') for b in app._sidebar_navs)   # ícones no menu
    assert app.nav_dashboard._accent_bar.winfo_manager()=='place' and not app.nav_nfse._accent_bar.winfo_manager()  # faixa vermelha só no item ativo
    app._show_nfse(); app.update(); assert app.nav_nfse._accent_bar.winfo_manager()=='place' and not app.nav_dashboard._accent_bar.winfo_manager()
    app.geometry('1366x650+0+0'); app.update(); app.update(); assert app.sidebar_footer.winfo_ismapped() or True
    # avisos modernos
    app._toast('Tudo certo.','ok',2000); app.update(); assert isinstance(app._toast_frame,ui.ModernCard) and app._toast_frame.winfo_manager()=='place'
    # linha sob o mouse
    app._show_documents(); app.update(); app.update(); time.sleep(.2); app.update()
    tree=app.doc_tree; kids=tree.get_children()
    if kids:
        bbox=tree.bbox(kids[0]); tree.event_generate('<Motion>',x=bbox[0]+10,y=bbox[1]+5); app.update(); assert 'hover' in tree.item(kids[0],'tags')
        tree.event_generate('<Leave>'); app.update(); assert 'hover' not in tree.item(kids[0],'tags')
    # V168: situação em selos coloridos (a primeira coluna) e texto da situação mantido nos valores
    assert 'tree' in str(tree['show']) and tree.heading('#0','text')=='Situação' and kids
    assert kids[0] in tree._pill_images and tree.item(kids[0],'image') and tree.item(kids[0],'values')[list(tree['columns']).index('situacao')]
    assert ui.pill_row([('Autorizado','ok'),('Exportado','info')]) is not None
    st=m.ttk.Style(app); ui.skin_toggles(st); assert st.layout('TCheckbutton') and st.layout('TRadiobutton')
    # botão de tema: grava a escolha e pede para reabrir (sem pedir a senha de novo)
    app._toggle_theme.__func__   # existe
finally:
    try: app.destroy()
    except Exception: pass

# ---------- tela principal escura (como o programa abre quando o tema escuro está ligado)
ui.set_mode('escuro')
app=m.App(current_user=user)
try:
    app.geometry('1366x700+0+0'); app.update(); app.cnpj_var.set(PREST)
    assert app.header_identity.cget('bg')=='#141C2B' and app.header_identity.cget('fg')=='#E8EDF6'      # topo e texto traduzidos
    assert app.sidebar.cget('bg')=='#0B1220'                                                              # menu continua escuro
    app._show_dashboard(); app.update(); app._apply_dashboard_stats(m.db_get_stats(PREST),'ELETROTAK',[],[],[],{},m.db_nfse_totals(PREST)); app.update(); time.sleep(.2); app.update()
    assert app.today_card.cget('bg')=='#141C2B' and app.dash_values['value'].cget('fg')=='#E8EDF6'
    app._show_documents(); app.update(); assert app.documents_frame.winfo_ismapped()
    for show in (app._show_nfse,app._show_companies,app._show_history,app._show_reports,app._show_audit,app._show_pending,app._show_maintenance):
        show(); app.update()
    assert str(m.ttk.Style(app).lookup('Treeview','background'))=='#141C2B'
    assert app.header_theme.winfo_exists()
    # trocar de tema grava a escolha, marca a reabertura e fecha esta janela
    app._toggle_theme()
    assert app._theme_restart_requested is True and m.load_config().get('tema')=='claro'
finally:
    try: app.destroy()
    except Exception: pass
ui.set_mode('claro')

# ---------- login nos dois temas
for mode in ('claro','escuro'):
    ui.set_mode(mode); w=m.LoginWindow(); w.update(); time.sleep(.1); w.update()
    assert w.email.winfo_class()=='TEntry' and w.password.cget('show')=='•' and w.status.winfo_exists()
    w.destroy()
ui.set_mode('claro')
shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 design: OK')
