import os, sys, tempfile, shutil
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v143_status_')
sys.path.insert(0,str(ROOT/'programa'))
import exato_central_fiscal as m

try:
    now=datetime(2026,10,1,17,0,0)
    assert m._company_update_status('', now) == 'Desatualizada'
    assert m._company_update_status((now-timedelta(hours=23)).isoformat(), now) == 'Atualizada'
    assert m._company_update_status((now-timedelta(hours=48)).isoformat(), now) == 'Atenção'
    assert m._company_update_status((now-timedelta(hours=72)).isoformat(), now) == 'Desatualizada'
    assert m._company_search_status_label('Concluído') == 'Concluída'
    assert m._company_search_status_label('Concluído com observações','alguma ocorrência') == 'Com observação'
    assert m._company_search_status_label('Cancelado') == 'Cancelada'
    assert m._company_search_status_label('Em andamento') == 'Em andamento'
    assert m._company_search_status_label('', '') == 'Não realizada'

    m.init_database()
    db=m.sqlite3.connect(m.DB_PATH)
    now_s=now.isoformat(timespec='seconds')
    old_s=(now-timedelta(days=4)).isoformat(timespec='seconds')
    db.execute("INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)",('11111111000111','Empresa Atualizada',now_s,now_s))
    db.execute("INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)",('22222222000122','Empresa Antiga',old_s,old_s))
    db.execute("INSERT INTO sync_runs(cnpj,started_at,finished_at,status,error_text) VALUES(?,?,?,?,?)",('11111111000111',now_s,now_s,'Concluído',''))
    db.execute("INSERT INTO sync_runs(cnpj,started_at,finished_at,status,error_text) VALUES(?,?,?,?,?)",('22222222000122',old_s,old_s,'Concluído com observações','Fornecedor sem XML'))
    db.commit(); db.close()
    rows={r['cnpj']:r for r in m.db_list_companies()}
    assert rows['11111111000111']['last_search_status']=='Concluído'
    assert rows['22222222000122']['last_search_status']=='Concluído com observações'
    assert m._company_search_status_label(rows['22222222000122']['last_search_status'], rows['22222222000122']['last_search_error'])=='Com observação'
    print('V143 company status: OK')
finally:
    shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
