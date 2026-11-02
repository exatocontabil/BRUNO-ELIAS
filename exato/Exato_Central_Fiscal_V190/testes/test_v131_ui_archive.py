import sqlite3
import tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as mod


def seed(db_path):
    mod.DB_PATH=db_path
    mod.APP_DATA_DIR=db_path.parent / 'appdata'
    mod.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    mod.init_database()
    cnpj='49894842000123'
    xml=b'<xml/>'
    conn=sqlite3.connect(mod.DB_PATH)
    conn.execute("INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)",(cnpj,'ELYON LTDA','2026-09-25T10:00:00','2026-09-25T10:00:00'))
    conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 ('doc1',cnpj,'nfe','NF-e','Saída','290248','0','2026-09-25T10:00:00','1.00','Autorizado','key1','1',xml,'2026-09-25T10:00:00','2026-09-25T10:00:00'))
    conn.commit(); conn.close()
    return cnpj

app=mod.App()
app._show_webservice_test()
with tempfile.TemporaryDirectory() as td:
    cnpj=seed(Path(td)/'central_fiscal.db')
    app.cnpj_var.set(cnpj)
    app._set_cnpj_confirmed(True)
    app._period_confirmed=True
    app._capture_period_snapshot=('2026-09-01','2026-09-30')
    docs=app._load_persisted_company_state(cnpj)
    assert docs, 'documento persistido não carregado'
    app._set_sync_controls(False)
    assert str(app.save_btn.cget('state')) == 'normal', 'SALVAR XMLs + PDFs não foi habilitado para documentos persistidos'
    assert str(app.local_archive_save_btn.cget('state')) == 'normal', 'SALVAR AGORA não foi habilitado'
    assert 'armazenado' in app.local_archive_status.cget('text').lower()
app.destroy()
print('V131 UI archive: OK')
