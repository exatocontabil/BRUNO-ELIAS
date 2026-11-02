"""V188: resposta desconhecida da SEFAZ sem notas deixa de ser "sem notas" (vira recusa explicada); a resposta da SEFAZ aparece na Situação da busca; espera do próximo fluxo da NF-e é aviso azul (não erro);
cliente recém-vinculado: busca sozinho e repete de hora em hora por 3 dias."""
import os, sys, tempfile, time, sqlite3
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v188_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as e
import exato_busca_motivos as M, exato_situacao_busca as S, exato_cobertura as C, exato_vinculo as V
CN='11222333000181'
# ---- _fetch_log: só 117/118/137/138 valem como "consulta feita"
def ret(cst,docs=(),ok=True,motivo='Contribuinte não autorizou o contabilista'): return (ok,'x',{'cstat':cst,'motivo':motivo,'documents':list(docs)})
e.busca_progresso_iniciar(CN)
r=e._fetch_log('NFC-e',CN,'0',lambda:ret('999')); assert r[0] is False and 'código 999' in r[1] and 'não autorizou' in r[1] and r[2]['cstat']=='999',r
assert e._fetch_log('NFC-e',CN,'0',lambda:ret('137',motivo='Nenhum documento localizado'))[0] is True
assert e._fetch_log('NFC-e',CN,'0',lambda:ret('138',docs=[{'a':1}]))[0] is True
assert e._fetch_log('NFC-e',CN,'0',lambda:ret('999',docs=[{'a':1}]))[0] is True          # veio documento: vale
assert e._fetch_log('NFC-e',CN,'0',lambda:ret('215',ok=False))[0] is False
# a busca inteira: a recusa não vira "nenhum documento adicional"
res=e.sync_documents_automatically(lambda th,c,n:e._fetch_log('NFC-e',c,n,lambda:ret('999')),'AA',CN,'nfce',start_nsu=0)
assert res['ok'] is False and 'erro do serviço (999)' in res['end_reason'],res['end_reason']
assert M.classificar(str(res['message']),'999')=='vinculo_pendente' and M.explicar('vinculo_pendente')['gravidade']=='aviso' and 'MESMO CPF/CNPJ' in M.explicar('vinculo_pendente')['acao']
assert M.classificar('Contribuinte sem permissão','')=='vinculo_pendente' and M.classificar('cstat 215 rejeição de schema','215')=='sefaz_rejeicao' and M.classificar('ator não autorizado')=='certificado_outra_empresa'
# ---- Situação da busca: a resposta da SEFAZ aparece em "Sem notas"
e.init_database(force=True); e.db_register_company(CN,'EMPORIO TESTE')
cfg={}; C.registrar(cfg,CN,'nfce',nsu=5)
M.registrar(str(e.DB_PATH),CN,'nfce','sem_novas','cStat 137: Nenhum documento localizado')
l=[x for x in S.linhas(str(e.DB_PATH),cfg,None,ocorrencias=M.ultimas(str(e.DB_PATH))) if x['cnpj']==CN][0]
cel=l['celulas']['nfce']; assert cel['estado']=='sem_notas' and cel['resposta']=='A SEFAZ respondeu: Nenhum documento localizado (137)' and cel['resposta'] in cel['detalhe'],cel
assert [i for i in S.itens_relatorio(l) if i['tipo']=='nfce'][0]['resposta']==cel['resposta']
# ---- aviso azul na espera do próximo fluxo
msg,kind=e.App._toast_for_event('SYNC_SUCCESS',{'new_documents':0,'espera':'consultar Destinatário / Entrada (a SEFAZ pede esperar cerca de 1h00)'},'EMPORIO')
assert kind=='info' and 'Falta consultar Destinatário / Entrada' in msg and 'nenhum documento novo' in msg,(msg,kind)
assert e.App._toast_for_event('SYNC_SUCCESS',{'new_documents':2},'X')[1]=='ok'
# ---- cliente novo / vínculo pendente
c=sqlite3.connect(e.DB_PATH)
c.execute("DELETE FROM companies WHERE cnpj=?",(CN,))
def emp(cn,nome,criada): c.execute("INSERT OR REPLACE INTO companies(cnpj,name,last_sync_at,created_at) VALUES(?,?,?,?)",(cn,nome,'',criada.isoformat(timespec='seconds')))
agora=datetime(2026,10,19,10,0,0); NOVA,VELHA,PEND='45723174000110','11444777000161','12345678000195'
emp(NOVA,'NOVA LTDA',agora-timedelta(minutes=5)); emp(VELHA,'VELHA LTDA',agora-timedelta(days=60)); emp(PEND,'PEND LTDA',agora-timedelta(days=30))
c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES('v1',?,'nfe','NF-e','Saída','1','1','2026-09-10T10:00:00','1.00','Autorizado','%044d',x'3c78','2026-09-10','2026-09-10')"%1,(VELHA,))
c.commit(); c.close()
M.registrar(str(e.DB_PATH),PEND,'nfce','vinculo_pendente','cStat 999: Contribuinte não autorizou o contabilista')
est={}
buscar,avisar=V.decidir(str(e.DB_PATH),est,agora); assert buscar and buscar[0] in (NOVA,PEND) and not avisar and VELHA not in buscar+[x for x in est],(buscar,est)
V.registrar_tentativa(est,buscar[0],agora); seg=[x for x in (NOVA,PEND) if x!=buscar[0]][0]
b2,_=V.decidir(str(e.DB_PATH),est,agora+timedelta(minutes=10)); assert b2==[seg],b2          # a outra empresa entra na vez; a primeira espera 1 hora
V.registrar_tentativa(est,seg,agora)
assert V.decidir(str(e.DB_PATH),est,agora+timedelta(minutes=30))[0]==[]
b3,_=V.decidir(str(e.DB_PATH),est,agora+timedelta(minutes=61)); assert len(b3)==1          # passou 1 hora: tenta de novo
fim,av=V.decidir(str(e.DB_PATH),est,agora+timedelta(days=4)); assert fim==[] and {n for n,_ in av}=={NOVA,PEND},(fim,av)          # janela de 3 dias acabou: avisa
assert V.decidir(str(e.DB_PATH),est,agora+timedelta(days=5))[1]==[]          # avisa uma vez só
# empresa que já recebeu nota nunca entra
assert VELHA not in est
# ---- na tela: a espera do próximo fluxo não é erro
u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); user=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa')
e.enumerate_windows_certificates=lambda *a,**k:([],'')
app=e.App(current_user=user); ev=[]
try:
    app.update(); app.selected={'Thumbprint':'AA','Subject':'X'}; app._show_webservice_test(); app.update()
    app._ia_emit_event=lambda k,**kw: ev.append((k,kw)); app._repo_kick=lambda: None
    base={'ok':True,'documents':[],'batches':1,'last_nsu':5,'last_info':{'cstat':'137','motivo':'Nenhum documento localizado'},'new_count':0,'duplicate_count':0}
    results={'nfe':dict(base,ok=False,deferred_actor='2',deferred_label='Destinatário / Entrada',cooldown_remaining=3600,last_info={'cstat':'137','motivo':'Nenhum documento localizado'}),'nfce':dict(base),'cte':dict(base)}
    app._capture_period_snapshot=('',''); app._sync_run_id=None; app.sync_running=True
    app._finish_sync_all({'ok':False,'documents':[],'results':results,'cnpj':CN})
    tipos=[k for k,_ in ev]; assert 'SYNC_ERROR' not in tipos and tipos.count('SYNC_SUCCESS')==1,ev
    kw=[x for k,x in ev if k=='SYNC_SUCCESS'][0]; assert 'Destinatário / Entrada' in kw['espera'] and '1h00' in kw['espera'],kw
    oc=M.ultimas(str(e.DB_PATH)); assert oc[(CN,'nfce')]['resultado']=='ok' and 'Nenhum documento localizado' in oc[(CN,'nfce')]['detalhe'] and oc[(CN,'nfe')]['codigo']=='janela'
    # erro de verdade: o aviso traz a causa em português
    ev.clear(); app.sync_running=True
    ruim=dict(base,ok=False,message='A SEFAZ respondeu com o código 999: Contribuinte não autorizou o contabilista',end_reason='erro do serviço (999)',last_info={'cstat':'999','motivo':'Contribuinte não autorizou o contabilista'})
    app._finish_sync_all({'ok':False,'documents':[],'results':{'nfe':dict(base),'nfce':ruim,'cte':dict(base)},'cnpj':CN})
    er=[x for k,x in ev if k=='SYNC_ERROR']; assert er and 'ainda não liberou o acesso' in er[0]['error'] and 'NFC-e' in er[0]['error'],ev
    assert 'ainda não liberou' in e.App._toast_for_event('SYNC_ERROR',er[0],'X')[0]
    # agendador do cliente novo: busca sozinho (uma empresa por vez) e registra a tentativa
    chamadas=[]; app._auto_round_start=lambda manual=False,only=None: chamadas.append((manual,only)) or True
    app.config_data['vinculo_auto']={}; app._vinc_ts=-1e9; app._vinculo_tick()
    f=time.time()
    while time.time()-f<10 and not chamadas:
        app.update()
        while app._repo_inbox: app._repo_inbox.popleft()()
        time.sleep(.05)
    assert chamadas and chamadas[0][0] is False and len(chamadas[0][1])==1 and app.config_data['vinculo_auto'][chamadas[0][1][0]]['tentativas']==1,chamadas
    n=len(chamadas); app._vinc_ts=-1e9; app._vinculo_tick(); f=time.time()
    while time.time()-f<3: app.update(); time.sleep(.05)
    while app._repo_inbox: app._repo_inbox.popleft()()
    assert chamadas[-1][1]!=chamadas[0][1] or len(chamadas)==n          # a mesma empresa não repete antes de 1 hora
    print('cstat vinculo ok')
finally:
    try: app.destroy()
    except Exception: pass
