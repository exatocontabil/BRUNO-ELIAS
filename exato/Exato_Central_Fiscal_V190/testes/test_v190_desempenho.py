"""V189 (desempenho): listas de Documentos e NFS-e não são relidas quando nada mudou (versão do banco), leitura em segundo plano sem travar a tela, contagem do arquivo fiscal em cache,
backup em blocos grandes."""
import os, sys, tempfile, time, sqlite3, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v189_perf_'); os.environ['EXATO_UI_SYNC']='0'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as e
import exato_repositorio as R
e._prepare_persistent_storage(); e.init_database(force=True)
CN='11222333000181'; e.db_register_company(CN,'EMPRESA TESTE LTDA')
def nfe(n):
    k=f'422609{CN}55001{n:09d}1000001234'
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{CN}</CNPJ><xNome>EMPRESA TESTE LTDA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>CLIENTE</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe>'
            f'<protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
def doc(n): return {'xml':nfe(n),'tipo':'nfeProc','nsu':str(n),'family':'nfe','actor_code':'1','actor_label':'Emitente / Saída'}
e.db_upsert_documents(CN,[doc(i) for i in range(1,6)])
# ---- versão do banco e contagem em cache
v1=e.db_data_version(); assert e.db_data_version()==v1
s1=e.db_local_archive_stats(''); assert s1['documents']==5 and e.db_local_archive_stats('')==s1
e.db_upsert_documents(CN,[doc(6)]); assert e.db_data_version()!=v1
assert e.db_local_archive_stats('')['documents']==6          # o cache não esconde nota nova
e.db_data_version_fechar(); assert e.db_data_version() is not None          # reabre sozinha depois de fechar
# ---- backup em blocos grandes (ZIP válido, banco legível)
p=e.create_data_backup('teste'); z=zipfile.ZipFile(p); assert z.testzip() is None and 'central_fiscal.db' in z.namelist()
tmp=Path(tempfile.mkdtemp())/'x.db'; tmp.write_bytes(z.read('central_fiscal.db')); c=sqlite3.connect(tmp); assert c.execute('select count(*) from documents').fetchone()[0]==6; c.close()
# ---- tela
u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); user=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa')
e.enumerate_windows_certificates=lambda *a,**k:([],'')
app=e.App(current_user=user); app.geometry('1366x650+0+0')
def esperar(pronto,t=15):
    f=time.time()
    while time.time()-f<t:
        app.update()
        while app._repo_inbox: app._repo_inbox.popleft()()
        if pronto(): return True
        time.sleep(0.02)
    return False
chamadas=[]; orig=e.db_list_documents
def espia(*a,**k):
    if k.get('limit')==5000: chamadas.append(1)
    return orig(*a,**k)
e.db_list_documents=espia
try:
    app.update(); assert not app._ui_sync()
    app._show_documents(); assert esperar(lambda:getattr(app,'_docs_sig',None) is not None),'a lista não chegou'
    assert len(app.doc_tree.get_children())==6 and len(chamadas)==1,(len(app.doc_tree.get_children()),chamadas)
    # voltar para a tela sem mudar nada: não relê
    app._show_dashboard(); app.update(); app._show_documents(); esperar(lambda:False,0.5)
    assert len(chamadas)==1 and len(app.doc_tree.get_children())==6,chamadas
    # nota nova no banco -> relê
    e.db_upsert_documents(CN,[doc(7)]); app._show_dashboard(); app.update(); app._show_documents()
    assert esperar(lambda:len(app.doc_tree.get_children())==7) and len(chamadas)==2
    # mudar o filtro -> relê; várias mudanças seguidas: só a última vale
    app.doc_direction.set('Entrada'); app._refresh_documents_list(); app.doc_direction.set('Saída'); app._refresh_documents_list()
    assert esperar(lambda:getattr(app,'_docs_sig',None) is not None and app._docs_sig[0:1]==(e.db_data_version(),) and len(chamadas)>=4)
    assert 'Saída' in app._docs_sig and 'Entrada' not in app._docs_sig and len(app.doc_tree.get_children())==7
    # ---- NFS-e: a mesma ideia
    app._show_nfse(); app.update(); esperar(lambda:getattr(app,'_nfse_sig',None) is not None,5)
    sig=app._nfse_sig; app._show_dashboard(); app.update(); app._show_nfse(); app.update(); assert app._nfse_sig==sig
    app.nfse_query.set('zzz'); app._nfse_refresh_table(); assert esperar(lambda:getattr(app,'_nfse_sig',None) not in (None,sig))
    # ---- manutenção: a contagem não trava a tela e chega depois
    app._show_maintenance(); assert esperar(lambda:'Arquivo Fiscal Local: 7 documento(s)' in app.maint_data_label.cget('text')),app.maint_data_label.cget('text')
    print('desempenho ok')
finally:
    e.db_list_documents=orig
    try: app.destroy()
    except Exception: pass
