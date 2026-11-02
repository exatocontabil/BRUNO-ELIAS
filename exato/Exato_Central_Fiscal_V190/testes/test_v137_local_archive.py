"""V137 — Arquivo Fiscal Local: exportação, histórico, filtros e backup/restauração."""
from __future__ import annotations
import os, sys, tempfile, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR'] = tempfile.mkdtemp(prefix='exato_v134_archive_')
os.environ['EXATO_CF_DEV'] = '1'
sys.path.insert(0, str(ROOT))
import exato_central_fiscal as mod  # noqa: E402

mod.APP_DATA_DIR = Path(os.environ['EXATO_DATA_DIR'])
mod.BACKUP_DIR = mod.APP_DATA_DIR / 'Backups'
mod.DB_PATH = mod.APP_DATA_DIR / 'central_fiscal.db'
mod.CONFIG_PATH = mod.APP_DATA_DIR / 'config.json'
mod.DATA_STATE_PATH = mod.APP_DATA_DIR / 'data_state.json'
mod.AUDIT_HISTORY_PATH = mod.APP_DATA_DIR / 'auditoria_historico.json'
mod.init_database()

cnpj='49894842000123'
company='ELYON LTDA'
now='2026-09-25T17:00:00'
xml=b'''<?xml version="1.0" encoding="UTF-8"?><nfeProc><NFe><infNFe Id="NFe12345678901234567890123456789012345678901234"><ide><dhEmi>2026-09-25T10:00:00-03:00</dhEmi><nNF>290248</nNF><serie>0</serie><mod>55</mod></ide></infNFe></NFe></nfeProc>'''
conn=sqlite3.connect(mod.DB_PATH)
conn.execute('INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)',(cnpj,company,now,now))
conn.execute("""INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",('doc1',cnpj,'nfe','NF-e','Saída','290248','0','2026-09-25T10:00:00','14248.94','Autorizado','12345678901234567890123456789012345678901234','10',xml,now,now))
conn.commit(); conn.close()

rows=mod.db_load_documents_as_payload(cnpj,limit=1000,date_from='2026-09-01',date_to='2026-09-30')
assert len(rows)==1
assert rows[0]['doc_id']=='doc1'
stats=mod.db_local_archive_stats(cnpj,'2026-09-01','2026-09-30')
assert stats['documents']==1 and stats['not_exported']==1 and stats['exported']==0
assert len(mod.db_filter_unexported(rows, str(mod.APP_DATA_DIR/'dest'))) == 1

# Register export for one destination and verify state/filtering.
dest=mod.APP_DATA_DIR/'dest'; dest.mkdir(parents=True)
assert mod.db_mark_documents_exported(rows,str(dest))==1
state=mod.db_exported_status(['doc1'],str(dest))
assert state.get('doc1') is True
assert mod.db_filter_unexported(rows,str(dest)) == []
assert mod.db_filter_unexported(rows,str(mod.APP_DATA_DIR/'other')) == rows
stats=mod.db_local_archive_stats(cnpj,'2026-09-01','2026-09-30')
assert stats['exported']==1 and stats['not_exported']==0

listed=mod.db_list_documents(cnpj=cnpj,export_status='Exportado',date_from='2026-09-01',date_to='2026-09-30')
assert len(listed)==1 and listed[0]['exported_any']==1
listed2=mod.db_list_documents(cnpj=cnpj,export_status='Não exportado',date_from='2026-09-01',date_to='2026-09-30')
assert len(listed2)==0

# Query should search by CNPJ/value/direction/date in addition to old fields.
assert len(mod.db_list_documents(query='290248'))==1
assert len(mod.db_list_documents(query='49894842000123'))==1
assert len(mod.db_list_documents(query='14248.94'))==1
assert len(mod.db_list_documents(query='Saída'))==1

# Backup and safe restore: remove the doc, restore, and verify it returns.
backup=mod.create_data_backup(reason='teste_v134')
assert backup.exists()
conn=sqlite3.connect(mod.DB_PATH); conn.execute('DELETE FROM document_exports'); conn.execute('DELETE FROM documents'); conn.commit(); conn.close()
assert mod.db_document_count(cnpj,'2026-09-01','2026-09-30')==0
assert mod.restore_local_archive_backup(backup)
restored=mod.db_load_documents_as_payload(cnpj,limit=1000,date_from='2026-09-01',date_to='2026-09-30')
assert len(restored)==1 and restored[0]['chave']==rows[0]['chave']
assert sqlite3.connect(mod.DB_PATH).execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print('V137 local archive tests: OK')
