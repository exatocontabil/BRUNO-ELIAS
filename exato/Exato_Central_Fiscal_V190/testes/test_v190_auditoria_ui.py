"""V180 (tela): Auditoria mostra a coluna Documento, a situação Cancelada, filtra por ela e marca nota cancelada à mão; botões de tipo legíveis no tema escuro."""
import os, sys, tempfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_audui_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as e
import exato_ui
exato_ui.set_mode('escuro')
import test_v190_auditoria_cancelada as T          # monta o banco e o resultado da auditoria (e roda as verificações dele)
CNPJ=T.CNPJ
e.init_database(); u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); user=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa')
e.enumerate_windows_certificates=lambda *a,**k:([],'')
# resultado novo (a nota 4 voltou a autorizada para testar a marcação pela tela)
import sqlite3
c=sqlite3.connect(e.DB_PATH); c.execute("UPDATE documents SET status='Autorizado' WHERE access_key=? AND status<>'Evento'",(T.key(4),)); c.commit(); c.close()
res=e.audit_sat_excel_against_xml(CNPJ,T.sat,'2026-09-01','2026-09-30',family='nfe'); e._audit_separar_cancelados(res,CNPJ)
app=e.App(current_user=user); app.geometry('1366x650+0+0')
try:
    app._show_audit(); app.update()
    app._audit_cnpj_sel=CNPJ; app.last_audit_result=res
    res['ai_analysis']=e.analyze_audit_result(res,'EMPRESA TESTE LTDA','2026-09-01','2026-09-30'); app._audit_render_summary(res); app._audit_rebuild_table(); app.update()
    cols=list(app.audit_tree['columns']); assert 'doc' in cols and cols.index('doc')==cols.index('modelo')+1
    vals={app.audit_tree.item(i,'values')[1]:app.audit_tree.item(i,'values') for i in app.audit_tree.get_children()}
    assert vals['3'][0]=='Cancelada' and vals['3'][cols.index('doc')]=='Cancelada' and vals['1'][0]=='Conforme' and vals['4'][0]=='Sem correspondência',vals
    assert 'cancel' in app.audit_tree.item([i for i in app.audit_tree.get_children() if app.audit_tree.item(i,'values')[1]=='3'][0],'tags')
    assert 'cancelada(s)' in app.audit_table_hint.cget('text')
    app.audit_filter_var.set('Cancelada'); app._audit_rebuild_table(); assert [app.audit_tree.item(i,'values')[1] for i in app.audit_tree.get_children()]==['3']
    app.audit_filter_var.set('Todos'); app._audit_rebuild_table()
    # marcar a nota 4 como cancelada pela tela
    iid=[i for i in app.audit_tree.get_children() if app.audit_tree.item(i,'values')[1]=='4'][0]; app.audit_tree.selection_set(iid); app._on_audit_selection()
    e.messagebox.askyesno=lambda *a,**k:True; e.messagebox.showinfo=lambda *a,**k:None
    app._audit_marcar_cancelada(); app.update()
    vals={app.audit_tree.item(i,'values')[1]:app.audit_tree.item(i,'values') for i in app.audit_tree.get_children()}
    assert vals['4'][0]=='Cancelada' and not res['xml_only'],vals
    # botões de tipo no tema escuro: fundo escuro (não o cinza-claro do tema claro)
    b=app.audit_family_buttons['nfe']; bg=b.cget('bg').lstrip('#'); lum=sum(int(bg[i:i+2],16) for i in (0,2,4))/3; assert lum<110,('botão claro no tema escuro',b.cget('bg'))
    assert 'Modelo' not in b.cget('text')
    app.update(); print('V182 auditoria UI OK')
finally:
    app.destroy()
