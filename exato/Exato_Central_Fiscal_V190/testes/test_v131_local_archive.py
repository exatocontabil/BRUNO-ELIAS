import os
import sqlite3
import tempfile
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'exato_central_fiscal.py'

spec = importlib.util.spec_from_file_location('exato_v131', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_persistent_storage_and_later_export(tmp_path):
    mod.DB_PATH = tmp_path / 'central_fiscal.db'
    mod.APP_DATA_DIR = tmp_path / 'appdata'
    mod.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    mod.init_database()

    cnpj = '49894842000123'
    company = 'ELYON LTDA'
    xml = b'''<?xml version="1.0" encoding="UTF-8"?><nfeProc><NFe><infNFe Id="NFe12345678901234567890123456789012345678901234"><ide><dhEmi>2026-09-25T10:00:00-03:00</dhEmi><nNF>290248</nNF><serie>0</serie><mod>55</mod></ide></infNFe></NFe></nfeProc>'''
    conn = sqlite3.connect(mod.DB_PATH)
    conn.execute("INSERT INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)", (cnpj, company, '2026-09-25T10:00:00', '2026-09-25T10:00:00'))
    conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 ('doc1',cnpj,'nfe','NF-e','Saída','290248','0','2026-09-25T10:00:00','14248.94','Autorizado','12345678901234567890123456789012345678901234','10',xml,'2026-09-25T10:00:00','2026-09-25T10:00:00'))
    conn.commit(); conn.close()

    # Simulate application restart: the durable DB is the source of truth.
    loaded = mod.db_load_documents_as_payload(cnpj, limit=1000, date_from='2026-09-01', date_to='2026-09-30')
    assert len(loaded) == 1
    assert loaded[0]['chave'] == '12345678901234567890123456789012345678901234'
    assert mod.db_document_count(cnpj, '2026-09-01', '2026-09-30') == 1

    # Export later, without any new webservice call.
    out = tmp_path / 'clientes'
    saved, errors = mod.save_documents_organized(loaded, str(out), cnpj, config_data={'company_names': {cnpj: company}}, generate_companion_pdf=False, period_start='2026-09-01', period_end='2026-09-30')
    assert not errors, errors
    xml_files = list(out.rglob('*.xml'))
    assert len(xml_files) == 1
    assert xml_files[0].read_bytes() == xml


def test_period_count_ignores_out_of_period(tmp_path):
    mod.DB_PATH = tmp_path / 'central_fiscal.db'
    mod.APP_DATA_DIR = tmp_path / 'appdata'
    mod.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    mod.init_database()
    cnpj='11111111000191'
    conn=sqlite3.connect(mod.DB_PATH)
    for idx,date in enumerate(('2026-08-01','2026-09-01'),1):
        conn.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (f'doc{idx}',cnpj,'nfe','NF-e','Saída',str(idx),'1',date,'1.00','Autorizado',f'key{idx}','',b'<xml/>','2026-09-25','2026-09-25'))
    conn.commit(); conn.close()
    assert mod.db_document_count(cnpj,'2026-09-01','2026-09-30') == 1
    assert mod.db_document_count(cnpj,'2026-08-01','2026-08-31') == 1


if __name__ == '__main__':
    test_persistent_storage_and_later_export(Path(tempfile.mkdtemp()))
    test_period_count_ignores_out_of_period(Path(tempfile.mkdtemp()))
    print('V131 local archive tests: OK')
