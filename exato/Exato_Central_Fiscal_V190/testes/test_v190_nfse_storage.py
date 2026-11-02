"""NFS-e no Arquivo Fiscal Local: gravação, eventos/cancelamento, barreira para os fluxos atuais e exportação."""
import os, sys, tempfile, shutil, gzip, base64
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_nfse_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
from test_v190_nfse_core import nfse_xml, evento_xml, chave, PREST, TOMA   # reaproveita os XMLs de exemplo (e roda o teste do núcleo)
out=Path(tempfile.mkdtemp(prefix='exato_v174_out_'))
try:
    m.init_database()
    items=[{'nsu':1,'chave':chave(1),'tipo_documento':'NFSE','tipo_evento':'','xml':nfse_xml(1,valor='1500.00',dh='2026-09-10T14:30:00-03:00')},
           {'nsu':2,'chave':chave(2),'tipo_documento':'NFSE','tipo_evento':'','xml':nfse_xml(2,prest='11111111000191',toma=PREST,valor='300.50',dh='2026-10-01T09:00:00-03:00')},
           {'nsu':3,'chave':chave(1),'tipo_documento':'EVENTO','tipo_evento':'101101','xml':evento_xml(1)},
           {'nsu':4,'chave':'','tipo_documento':'DPS','tipo_evento':'','xml':b'<DPS/>'}]
    r=m.db_upsert_nfse_items(PREST,items)
    assert (r['new'],r['duplicate'],r['events'],r['cancelled'],r['ignored'])==(2,0,1,1,1),r
    rows={x['access_key']:x for x in m.db_list_documents(cnpj=PREST,family='nfse',limit=50) if x['status']!='Evento'}
    n1,n2=rows[chave(1)],rows[chave(2)]
    assert n1['direction']=='Saída' and n1['number']=='1' and n1['status']=='Cancelado' and n1['value']=='1500.00' and n1['doc_type']=='NFS-e' and n1['issued_at'].startswith('2026-09-10')
    assert n2['direction']=='Entrada' and n2['status']=='Autorizado' and n2['value']=='300.50'
    assert m.db_get_company_name(PREST)=='PRESTADORA SERVICOS LTDA'
    again=m.db_upsert_nfse_items(PREST,items); assert (again['new'],again['duplicate'],again['events'])==(0,2,0),again
    st=m.db_nfse_stats(PREST); assert st=={'total':2,'saidas':0,'entradas':1,'canceladas':1},st
    # barreira: fluxos de NF-e/NFC-e/CT-e (relatórios, auditoria, exportação) não recebem NFS-e por acaso
    assert m.db_load_documents_as_payload(PREST)==[] and len(m.db_load_documents_as_payload(PREST,include_nfse=True))==2 and len(m.db_load_documents_as_payload(PREST,family='nfse'))==2
    # exportação
    docs=m.db_load_documents_as_payload(PREST,family='nfse')
    saved,errors=m.save_documents_any(docs,str(out),PREST,{},None,run_legacy_migration=False,generate_companion_pdf=False)
    assert not errors and len(saved)==2,(saved,errors)
    rel=sorted(str(Path(x).relative_to(out)) for x in saved)
    assert any('2026' in x and '09 - ' in x and 'Prestados' in x and 'NFS-e' in x and x.endswith(chave(1)+'.xml') for x in rel),rel
    assert any('2026' in x and '10 - ' in x and 'Tomados' in x and 'NFS-e' in x for x in rel),rel
    s2,e2=m.save_nfse_documents(docs,str(out),PREST,period_start='2026-10-01',period_end='2026-10-31'); assert len(s2)==1 and not e2
    # metadados via função geral (o caminho que o banco usa)
    meta=m._parse_document_metadata(nfse_xml(5),PREST,'nfse'); assert meta['family']=='nfse' and meta['direcao']=='Saída'
    assert m._parse_document_metadata(nfse_xml(5),'00000000000191','nfse')['empresa']=='Empresa não identificada'
    # a representação em PDF do NFS-e não é oferecida (mensagem amigável na tela); o protegido continua recusando o tipo
    try: m.open_document_fiscal_representation({'family':'nfse','xml':b'<x/>'}); raise SystemExit('deveria recusar')
    except ValueError: pass
finally:
    shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True); shutil.rmtree(out,ignore_errors=True)
print('V169 NFS-e storage: OK')
