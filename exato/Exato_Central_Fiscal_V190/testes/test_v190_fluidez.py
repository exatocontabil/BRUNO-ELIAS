"""V168: fluidez — troca de telas rápida (listas em fatias, XML só quando preciso, Exatinho leve, índices)."""
import os, sys, tempfile, shutil, time, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_fluidez_'); os.environ['EXATO_UI_SYNC']='0'    # aqui as fatias valem de verdade
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaFlu#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaFlu#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
CNPJ='12345678000195'; m.db_register_company(CNPJ,'EMPRESA TESTE LTDA')
N=1500; xml=b'<nfeProc>'+b'x'*8000+b'</nfeProc>'
c=sqlite3.connect(m.DB_PATH)
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,source_nsu,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'd{i}',CNPJ,'nfe' if i%2 else 'nfse','NF-e','Entrada' if i%3 else 'Saída',str(i),'1',f'2026-0{1+i%9}-10T10:00:00','10.00','Autorizado','%044d'%i,'1',xml,'2026-01-01','2026-01-01') for i in range(N)])
c.commit(); c.close()
# --- linha sem XML: só busca o XML quando alguém usa
rows=m.db_list_documents(limit=10,with_xml=False)
r=rows[0]; assert not dict.__contains__(r,'xml') and r['status']=='Autorizado' and r.get('xml')==xml and dict(rows[1])['xml']==xml and {**rows[2]}['xml']==xml
assert 'xml' in rows[3] and rows[3].copy()['xml']==xml and len(m.db_list_documents(limit=3))==3
t=time.time(); m.db_list_documents(limit=5000,with_xml=False); t_sem=time.time()-t
t=time.time(); m.db_list_documents(limit=5000,with_xml=True); t_com=time.time()-t
assert t_sem<t_com,(t_sem,t_com)            # a lista sem XML é mais rápida
# --- índices da ordenação e das contagens
idx={r[1] for r in sqlite3.connect(m.DB_PATH).execute("PRAGMA index_list(documents)")}
assert {'idx_documents_ordem','idx_documents_cnpj_status'}<=idx,idx
plan=' '.join(str(x) for x in sqlite3.connect(m.DB_PATH).execute("EXPLAIN QUERY PLAN SELECT doc_id FROM documents ORDER BY COALESCE(issued_at,'') DESC, doc_id DESC LIMIT 50").fetchall())
assert 'idx_documents_ordem' in plan and 'TEMP B-TREE' not in plan,plan
app=m.App(current_user=user)
def bombear(t=.6):
    fim=time.time()+t
    while time.time()<fim: app.update(); time.sleep(.005)
try:
    app.geometry('1366x650+0+0'); app.update(); bombear(.8)
    # --- Exatinho leve: quadro novo custa pouco (antes ~40 ms ocupava quase todo o tempo do programa)
    app._ia_live_render_frame(time.monotonic()); t=time.perf_counter()
    for _ in range(30): app._ia_live_render_frame(time.monotonic())
    ms=(time.perf_counter()-t)/30*1000; assert ms<20,ms
    # --- Documentos: abre na hora e vai enchendo em fatias
    t=time.perf_counter(); app._show_documents(); chamada=time.perf_counter()-t
    fim=time.time()+10          # V189: a leitura é em segundo plano; a tela volta na hora e as linhas chegam em fatias
    while not app.doc_tree.get_children() and time.time()<fim: app.update(); time.sleep(.002)
    primeiro=len(app.doc_tree.get_children()); assert 0<primeiro<=N,primeiro
    assert chamada<1.5,chamada
    fim=time.time()+10
    while len(app.doc_tree.get_children())<N and time.time()<fim: app.update(); time.sleep(.005)
    assert len(app.doc_tree.get_children())==N and app.doc_count_label.cget('text').startswith('1.500')
    assert len(app._doc_row_map)==N and not any(dict.__contains__(r,'xml') for r in list(app._doc_row_map.values())[:50])   # a lista não carregou os XMLs
    # outro filtro no meio do preenchimento cancela o anterior: o resultado final é só o do último
    app.doc_family.set('NFS-e'); app._refresh_documents_list(); app.doc_family.set('NF-e'); app._refresh_documents_list()
    bombear(1.5); filhos=len(app.doc_tree.get_children()); assert filhos==N//2 and len(app._doc_row_map)==N//2,(filhos,len(app._doc_row_map))
    # "Selecionar todos" termina de preencher antes de selecionar
    app.doc_family.set('Todas'); app._refresh_documents_list()
    app._select_all_documents(); bombear(1.5); assert len(app.doc_tree.selection())==len(app.doc_tree.get_children())==len(app._doc_row_map)
    # trocar de tela no meio do preenchimento não trava nem dá erro
    app._refresh_documents_list(); app._show_companies(); app._show_history(); app._show_documents(); bombear(1.2)
    assert len(app.doc_tree.get_children())==len(app._doc_row_map)
    # --- NFS-e: tipo vem da direção (sem abrir XML) e só as linhas mostradas carregam XML
    app.cnpj_var.set(CNPJ); app._show_nfse(); app.nfse_company.set(f'EMPRESA TESTE LTDA — {m._format_cnpj(CNPJ)}'); app._nfse_refresh_table(); bombear(.5)
    subset,shown,counts,warn=app._nfse_filtered_rows()
    assert counts['prestados']+counts['tomados']==counts['total'] and counts['total']>0
    assert sum(1 for r in subset if dict.__contains__(r,'xml'))==0
    # --- trocar de tela rápido: cada troca volta logo (margem larga; o computador de teste é lento)
    for fn in ('_show_dashboard','_show_documents','_show_companies','_show_nfse','_show_history','_show_repo','_show_pending','_show_audit'):
        t=time.perf_counter(); getattr(app,fn)(); assert time.perf_counter()-t<1.5,(fn,time.perf_counter()-t); bombear(.1)
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 fluidez: OK')
