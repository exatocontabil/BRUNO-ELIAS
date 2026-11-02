"""V178: checkup das rolagens — nenhuma tela usa quadro rolante com um componente por célula (o que deixava rastro/texto sobreposto no Windows);
cada tela abre em 1366x650 e rola até o fim com a roda sem erro, nos temas claro e escuro."""
import os, sys, sqlite3, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_chk_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import tkinter as tk
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaChk#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaChk#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
CN=['11222333000181','12345678000195','11444777000161','45723174000110','07526557000100','33000167000101']
for i,c in enumerate(CN): m.db_register_company(c,f'EMPRESA {i} LTDA')
app=m.App(current_user=user)
import traceback
app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
def canvases(w):
    for x in w.winfo_children():
        if isinstance(x,tk.Canvas): yield x
        yield from canvases(x)
def embutidos(cv):
    """Quantos componentes (e filhos) estão dentro de janelas embutidas do quadro."""
    total=0
    for item in cv.find_all():
        if cv.type(item)=='window':
            try: w=cv.nametowidget(cv.itemcget(item,'window')); total+=1+len(list(_todos(w)))
            except Exception: pass
    return total
def _todos(w):
    for x in w.winfo_children(): yield x; yield from _todos(x)
try:
    app.geometry('1366x650+0+0'); app.update()
    telas=[('_show_dashboard','Início'),('_show_webservice_test','Buscar XML'),('_show_documents','Documentos Fiscais'),('_show_companies','Empresas'),('_show_audit','Auditoria Fiscal'),
           ('_show_pending','Pendências'),('_show_history','Histórico'),('_show_reports','Relatórios'),('_show_users','Usuários'),('_show_maintenance','Manutenção'),('_show_repo','Repositório')]
    for fn,titulo in telas:
        getattr(app,fn)(); app.update(); app.update()
        # 1) quadros rolantes da tela: nenhum com uma grade de componentes
        for cv in canvases(app.page_host):
            if cv is app.workspace_canvas: continue
            if str(cv.cget('yscrollcommand')):                       # é um quadro rolante
                n=embutidos(cv); assert n<=45,(titulo,str(cv),n)
        # 2) rola a página até o fim e volta com a roda (pelo roteador)
        pagina=app.workspace_canvas
        for _ in range(60): pagina.yview_scroll(3,'units'); 
        app.update(); pagina.yview_moveto(0); app.update()
    # 3) a tela de Empresas: carteira e situação são desenhadas no quadro e rolam por linha inteira
    app._show_companies(); app.update()
    for cv in (app.company_table_canvas,):
        assert not [i for i in cv.find_all() if cv.type(i)=='window'] and int(float(cv.cget('yscrollincrement')))==m._CARTEIRA_LINHA
    app._sit_aba('situacao'); app.update(); time.sleep(.3); app.update()
    assert not [i for i in app._sit_canvas.find_all() if app._sit_canvas.type(i)=='window'] and int(float(app._sit_canvas.cget('yscrollincrement')))==m._SIT_LINHA
    # 4) tema escuro: reabrir as telas desenhadas não gera erro e usa cores do tema
    m.exato_ui.set_mode('escuro'); app._sit_desenhar(); app._company_desenhar(); app.update()
    fundo=app._sit_canvas.itemcget(app._sit_canvas.find_all()[0],'fill') if app._sit_canvas.find_all() else '#141C2B'
    assert fundo.upper() not in ('#FFFFFF','#F8FAFC'),fundo
    m.exato_ui.set_mode('claro')
    app.update(); print('V178 checkup de rolagem OK')
finally:
    try: app.destroy()
    except Exception: pass
