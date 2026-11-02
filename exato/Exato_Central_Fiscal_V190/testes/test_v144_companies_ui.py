import os, re, sys, tempfile, shutil
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v144_ui_')
sys.path.insert(0,str(ROOT/'programa'))
import exato_central_fiscal as m
m.init_database()
u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL)
m.db_auth_set_password(u['id'],'SenhaUI#2026')
user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaUI#2026')
app=None
try:
    app=m.App(current_user=user)
    now=datetime.now()
    db=m.sqlite3.connect(m.DB_PATH)
    rows=[
        ('15281183000183','Empresa Atualizada',now.isoformat(timespec='seconds'),'Concluído',''),
        ('54865676000177','Empresa Atenção',(now-timedelta(hours=48)).isoformat(timespec='seconds'),'Concluído com observações','Observação'),
        ('10361127000190','Empresa Desatualizada',(now-timedelta(days=5)).isoformat(timespec='seconds'),'Em andamento',''),
        ('49123456000100','Empresa Não Realizada',None,None,''),
    ]
    for cnpj,name,last,status,error in rows:
        created=(last or now.isoformat(timespec='seconds'))
        db.execute('INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)',(cnpj,name,last,created))
        if status:
            db.execute('INSERT INTO sync_runs(cnpj,started_at,finished_at,status,error_text) VALUES(?,?,?,?,?)',(cnpj,last,last,status,error))
    db.commit(); db.close()
    app.geometry('1500x860'); app._show_companies(); app.update_idletasks(); app.update()
    assert re.match(r'V\d+$',m.APP_VERSION)
    assert hasattr(app,'company_table_canvas') and hasattr(app,'company_summary_cards')
    vals={v['name']:v for v in app._company_row_records.values()}
    assert len(vals)==4
    assert vals['Empresa Atualizada']['values'][4]=='Atualizada'
    assert vals['Empresa Atenção']['values'][4]=='Atenção'
    assert vals['Empresa Desatualizada']['values'][4]=='Desatualizada'
    assert vals['Empresa Não Realizada']['values'][5]=='Não realizada'
    assert app.company_summary_cards['shown'].cget('text')=='4'
    assert app.company_summary_cards['updated'].cget('text')=='1'
    assert app.company_summary_cards['attention'].cget('text')=='1'
    assert app.company_summary_cards['stale'].cget('text')=='2'
    # Row selection replaces the legacy Treeview selection and remains compatible with ABRIR EMPRESA.
    first_iid=next(iter(app._company_row_records))
    app._company_row_event(first_iid, False)
    assert app._selected_company_cnpj == app._company_row_records[first_iid]['cnpj']
    # Placeholder text must not become a real search filter.
    assert app._company_query_placeholder is True
    app._company_search_focus_in()
    assert app._company_query_placeholder is False and app.company_query.get()==''
    app.company_query.set('Empresa Atualizada'); app._refresh_companies()
    assert app.company_summary_cards['shown'].cget('text')=='1'
    app.company_query.set(''); app._company_search_focus_out(); app._refresh_companies()
    app.company_filter.set('Desatualizadas'); app._refresh_companies()
    assert app.company_summary_cards['shown'].cget('text')=='2'
    print('V144 companies UI: OK')
finally:
    try:
        if app is not None: app.destroy()
    except Exception: pass
    shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
