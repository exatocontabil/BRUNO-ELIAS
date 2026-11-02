import os, sys, tempfile, shutil, threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v148_prod_')
sys.path.insert(0,str(ROOT/'programa'))
import exato_central_fiscal as m
m.init_database()
u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaUI#2026')
user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaUI#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
shown=[]
m.messagebox.showerror=lambda *a,**k:shown.append(a)
app=m.App(current_user=user)
try:
    app.update(); app.update()
    log=m.LOG_DIR/'exato.log'
    # --- registro de erros ---
    assert log.exists() and 'Início Exato Central Fiscal' in log.read_text(encoding='utf-8')
    try: 1/0
    except ZeroDivisionError: m.log_exception('teste manual')
    def boom(): raise RuntimeError('falha de clique simulada')
    app.after(0,boom); app.update(); app.update()
    text=log.read_text(encoding='utf-8')
    assert 'ZeroDivisionError' in text and 'falha de clique simulada' in text and 'Traceback' in text
    assert len(shown)==1 and 'exato.log' in shown[0][1], 'aviso amigável uma única vez'
    app.after(0,boom); app.update(); app.update(); assert len(shown)==1, 'aviso limitado a 1 a cada 20 s'
    t=threading.Thread(target=lambda: 1/0,name='fundo'); t.start(); t.join()
    assert 'Erro em segundo plano (fundo)' in log.read_text(encoding='utf-8')
    app._maintenance_open_logs  # botão existe
    # --- atalhos Ctrl+1..9 e F1 ---
    for number,crumb in [(1,'Início'),(2,'Buscar XML'),(3,'Documentos Fiscais'),(4,'Empresas'),(5,'Auditoria Fiscal'),(6,'Pendências'),(7,'Histórico'),(8,'Relatórios'),(9,'Certificado')]:
        app.focus_force(); app.event_generate(f'<Control-Key-{number}>'); app.update(); app.update()
        assert app.header_crumb.cget('text')==crumb,(number,app.header_crumb.cget('text'))
    app.event_generate('<F1>'); app.update()
    assert app._shortcuts_win is not None and app._shortcuts_win.winfo_exists()
    app._shortcuts_win.destroy(); app.update()
    # --- avisos que somem sozinhos ---
    assert m.App._toast_for_event('SYNC_SUCCESS',{'new_documents':3},'ALFA')[1]=='ok'
    assert 'nenhum documento novo' in m.App._toast_for_event('SYNC_SUCCESS',{'new_documents':0})[0]
    assert m.App._toast_for_event('SYNC_ERROR',{'error':'x'})[1]=='error'
    assert m.App._toast_for_event('LOCAL_XML_EXPORT_DONE',{'documents':5,'errors':2,'status':'attention'})[1]=='warn'
    assert m.App._toast_for_event('NAVIGATED',{}) is None
    app._ia_emit_event('SYNC_SUCCESS',new_documents=2,documents=2,company='ALFA'); app.update(); app.update()
    assert app._toast_frame is not None and app._toast_frame.winfo_exists()
    app._toast('teste','warn',ms=100); app.update()
    app.after(300,lambda:None); 
    import time; time.sleep(.4); app.update(); app.update()
    assert app._toast_frame is None, 'o aviso some sozinho'
    # --- desempenho: nomes de empresa em uma única consulta ---
    m.db_register_company('46897135000100','JC AUTO PECAS LTDA')
    assert m.db_company_names().get('46897135000100')=='JC AUTO PECAS LTDA'
    assert m._format_user_date('2026-09-25T10:00:00')=='25/09/2026' and m._format_user_date('2026-02-31')=='2026-02-31'
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 productivity: OK')
