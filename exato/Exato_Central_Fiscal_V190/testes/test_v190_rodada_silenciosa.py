"""V178: a atualização automática não trava a tela (não recarrega a empresa inteira), só guarda os XMLs que ainda não foram guardados e espera a pessoa que está usando o Exato."""
import os, sys, sqlite3, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_sil_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaSil#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaSil#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
CN='11222333000181'; m.db_register_company(CN,'GRANDE LTDA')
xml=b'<nfeProc>'+b'x'*2000+b'</nfeProc>'; c=sqlite3.connect(m.DB_PATH)
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'd{i}',CN,['nfe','nfce','cte','nfse'][i%4] if i<4000 else 'nfe','NF-e','Saída',str(i),'2026-09-10T10:00:00','10','Evento' if i%50==0 else 'Autorizado','%044d'%i,xml,'x','x') for i in range(4000)]); c.commit(); c.close()
pasta=Path(tempfile.mkdtemp(prefix='exato_v183_cli_'))
# ---- só o que ainda não foi guardado nessa pasta (sem eventos e sem NFS-e)
todos=m.db_unexported_payload(CN,str(pasta)); esperado=sum(1 for i in range(4000) if i%50!=0 and i%4!=3)
assert len(todos)==esperado and all(d['status']!='Evento' and d['family']!='nfse' for d in todos),(len(todos),esperado)
assert todos[0]['xml']==xml and todos[0]['empresa']=='GRANDE LTDA' and todos[0]['exportado'] is False          # XML sob demanda, mesmo formato da tela
m.db_mark_documents_exported(todos[:1500],str(pasta)); assert len(m.db_unexported_payload(CN,str(pasta)))==esperado-1500
assert len(m.db_unexported_payload(CN,str(pasta/'outra')))==esperado                          # outra pasta de destino = tudo de novo
t0=time.time(); m.db_unexported_payload(CN,str(pasta)); assert time.time()-t0<1.5
app=m.App(current_user=user); app.geometry('1366x650+0+0'); app.update()
chamadas=[]; orig=m.db_load_documents_as_payload
m.db_load_documents_as_payload=lambda *a,**k: chamadas.append(1) or orig(*a,**k)
try:
    # ---- tela de Buscar XML normal carrega; durante a rodada automática NÃO recarrega a empresa inteira
    app._auto_round_active=False; app._load_persisted_company_state(CN); assert chamadas
    chamadas.clear(); app._auto_round_active=True; assert app._load_persisted_company_state(CN)==[] and app.last_documents==[] and not chamadas
    app._auto_round_active=False
    # ---- a rodada automática espera enquanto a pessoa usa o Exato; rodada pedida por clique não espera
    app._sync_ensure_built(); app._multi_company_run_active=True; app._multi_company_state={'companies':[{'cnpj':CN,'name':'GRANDE LTDA'}],'index':0,'silent':True,'results':[]}
    iniciou=[]; app._run_multi_company_single_sync=lambda: iniciou.append(1)
    app._auto_round={'manual':False}; app._marcar_uso(); assert app._usuario_ocupado()
    app._begin_next_multi_company(); assert not iniciou and 'em pausa' in app.status_var.get() if hasattr(app,'status_var') else True
    st=app._multi_company_state; assert '_pausa_desde' in st
    st['_pausa_desde']=time.monotonic()-60; app._begin_next_multi_company(); app.update(); time.sleep(.5); app.update()          # passou de 45 s: segue mesmo assim (a rodada não fica parada para sempre)
    assert '_pausa_desde' not in st and app._multi_current_company['cnpj']==CN
    app._multi_company_state={'companies':[{'cnpj':CN,'name':'GRANDE LTDA'}],'index':0,'silent':True,'results':[]}; app._auto_round={'manual':True}; app._multi_current_company={}
    app._begin_next_multi_company(); assert app._multi_current_company.get('cnpj')==CN          # manual: não espera
    app._multi_company_run_active=False; app._auto_round_active=False
    # ---- a tela tem vez: intervalo de troca das linhas de trabalho menor que o padrão
    assert sys.getswitchinterval()<=0.0025,sys.getswitchinterval()
    app.update(); print('V178 rodada silenciosa OK')
finally:
    m.db_load_documents_as_payload=orig
    try: app.destroy()
    except Exception: pass
