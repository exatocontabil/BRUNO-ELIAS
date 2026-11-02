"""V180: relatório em PDF da tela Documentos fiscais: tipos sempre separados (uma seção por tipo), autorizadas x canceladas à parte, filtros respeitados, seleção, NFS-e com ISS fora."""
import os, sys, tempfile, sqlite3, time
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_reldoc_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as e
import exato_relatorio_docs_pdf as X
import test_v190_auditoria_cancelada as T           # banco com 4 NF-e (uma cancelada)
from test_v190_iss_fora_totais import xml as nfse_xml, chave as nfse_chave
from test_v190_nfse_core import PREST
import pypdf
CN=T.CNPJ
# NFS-e (prestadora PREST) na mesma base
e.db_register_company(PREST,'PRESTADORA SERVICOS LTDA')
e.db_upsert_nfse_items(PREST,[{'xml':nfse_xml(i,incid=inc,nome_incid=nm,dh='2026-09-%02dT10:00:00-03:00'%(5+i)),'chave':nfse_chave(i),'tipo_documento':'NFSE','tipo_evento':'','nsu':0} for i,(inc,nm) in enumerate([('3531803','Monte Mor'),('3550308','São Paulo')],1)])
e.db_mark_nfse_cancelled(PREST,[nfse_chave(2)])
def texto(p): return ' '.join(' '.join((pg.extract_text() or '') for pg in pypdf.PdfReader(str(p)).pages).split())
def paginas(p): return [' '.join((pg.extract_text() or '').split()) for pg in pypdf.PdfReader(str(p)).pages]
tmp=Path(tempfile.mkdtemp(prefix='exato_v183_relpdf_'))
# ---- módulo: tudo da base, todos os tipos
rows=e.db_list_documents(limit=1000000,with_xml=False); linhas=e.relatorio_documentos_linhas(rows)
assert {l['familia'] for l in linhas}=={'nfe','nfse'} and len(linhas)==6,len(linhas)
nf=[l for l in linhas if l['familia']=='nfe']; assert all(l['parte'] for l in nf) and nf[0]['parte']=='CLIENTE',nf[0]
ns=[l for l in linhas if l['familia']=='nfse']; assert {l['iss_fora'] for l in ns}=={'NÃO','SIM'} and {l['municipio'] for l in ns}=={'Monte Mor','São Paulo'}
pdf=tmp/'todos.pdf'; X.gerar(linhas,str(pdf),'','','01/09/2026 a 30/09/2026',['Tipo: Todos'],e.LOGO_PATH)
pg=paginas(pdf)
assert 'Relatório de documentos fiscais' in pg[0] and 'Filtros: Tipo: Todos' in pg[0] and 'Várias empresas' in pg[0] and 'FATURAMENTO' in pg[0] and 'DESPESA' in pg[0]
sec=[i for i,t in enumerate(pg) if t.startswith('Documentos fiscais') and ('NF-e' in t[:140] or 'NFS-e' in t[:140]) and 'Autorizadas (notas)' in t]
nfe_pg=[i for i,t in enumerate(pg) if 'Chave de acesso' in t]; nfse_pg=[i for i,t in enumerate(pg) if 'ISS fora?' in t]
assert nfe_pg and nfse_pg and max(nfe_pg)<min(nfse_pg),(nfe_pg,nfse_pg)          # tipos em páginas diferentes (nunca misturados), na ordem NF-e, NFS-e
assert not set(nfe_pg)&set(nfse_pg)
tx=' '.join(pg)
for esperado in ('Total das autorizadas','Total das canceladas','Autorizadas (notas)','Canceladas (valor)','Faturamento x despesa','Monte Mor','São Paulo','Página 1 de','NF-e (SAÍDA)','NFS-e (PRESTADOS)'): assert esperado in tx,esperado
# ---- tela: filtros respeitados e seleção
e.init_database(); u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); user=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa')
e.enumerate_windows_certificates=lambda *a,**k:([],'')
app=e.App(current_user=user); app.geometry('1366x650+0+0')
saida={}
e.filedialog.asksaveasfilename=lambda **k: saida.setdefault('p',str(tmp/'tela.pdf')) if not k.get('initialfile','').endswith('X') else ''
opened=[]; e._open_default_path=lambda p: opened.append(p)
e.messagebox.showinfo=lambda *a,**k: opened.append(('info',a)); e.messagebox.showerror=lambda *a,**k: opened.append(('erro',a))
try:
    app._show_documents(); app.update()
    assert hasattr(app,'doc_report_btn') and app.doc_report_btn.cget('text').casefold()=='relatório pdf' and str(app.doc_report_btn.cget('state'))!='disabled'
    app.doc_family.set('NF-e'); app.doc_status.set('Cancelado'); app._refresh_documents_list()
    app._documents_report_pdf(); app.update()
    assert opened and opened[-1]==str(tmp/'tela.pdf'),opened
    t=texto(tmp/'tela.pdf'); assert 'Tipo: NF-e' in t and 'Situação: Cancelado' in t and 'Chave de acesso' in t and 'ISS fora?' not in t and 'EMPRESA TESTE LTDA' in t
    pg2=paginas(tmp/'tela.pdf'); assert any('Chave de acesso' in x for x in pg2) and 'NF-e (SAÍDA)' in ' '.join(pg2)
    # só um tipo = só uma seção; sem filtro de tipo = NFS-e em página própria
    app.doc_family.set('Todos'); app.doc_status.set('Todas'); app._refresh_documents_list(); saida.clear(); opened.clear()
    app._documents_report_pdf(); app.update(); t=texto(tmp/'tela.pdf'); assert 'Chave de acesso' in t and 'ISS fora?' in t
    # seleção: só as marcadas
    app._select_all_documents(); kids=app.doc_tree.get_children(); app.doc_tree.selection_set(kids[:1]); app._on_document_selection(); saida.clear(); opened.clear()
    app._documents_report_pdf(); app.update(); t=texto(tmp/'tela.pdf'); assert 'selecionados' in t and '1 documento(s)' in t
    assert app.config_data.get('doc_report_dir')==str(tmp)           # lembra a pasta
    # filtro sem resultado: avisa, não gera
    app.doc_tree.selection_remove(app.doc_tree.selection()); app.doc_query.set('zzzz-nada'); app._refresh_documents_list(); opened.clear(); saida.clear()
    app._documents_report_pdf(); assert opened and opened[-1][0]=='info'
    print('V182 relatório documentos OK')
finally:
    app.destroy()
