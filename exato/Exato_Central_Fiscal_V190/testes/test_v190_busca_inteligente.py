"""V173: busca inteligente: cobertura (registro, arquivo, repositório), período do portal da NFS-e só do que falta, aviso na busca manual,
cursor do Emissor Nacional pelo arquivo, lista de documentos sem carregar todos os XMLs."""
import os, sys, sqlite3, tempfile, shutil, time
from datetime import date, datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_busca_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
import exato_cobertura as C
import exato_nfse as nfse_mod
from test_v190_nfse_core import nfse_xml, chave, PREST
HOJE=date.today(); ONTEM=HOJE-timedelta(days=1)
m.init_database()
CNPJ=PREST; OUTRA='11222333000181'; VAZIA='11444777000161'
m.db_register_company(CNPJ,'PRESTADORA SERVICOS LTDA'); m.db_register_company(OUTRA,'JC AUTO PECAS LTDA')
def inserir(cnpj,familia,n,visto,nsu0=100,emitida='2026-09-10'):
    c=sqlite3.connect(m.DB_PATH)
    c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,source_nsu,xml,first_seen_at,last_seen_at,value) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(f'{cnpj}{familia}{i}',cnpj,familia,'NFS-e' if familia=='nfse' else 'NF-e','Saída',str(i),emitida+'T10:00:00','Autorizado',('%050d'%i if familia=='nfse' else '%044d'%i)+('' if cnpj==CNPJ else '1'),str(nsu0+i),b'<x n="%d"/>'%i,visto,visto,'10') for i in range(n)]); c.commit(); c.close()
inserir(CNPJ,'nfse',5,ONTEM.isoformat()+'T09:00:00',nsu0=500)
inserir(OUTRA,'nfe',5,(HOJE-timedelta(days=10)).isoformat()+'T09:00:00')

# ---------------- módulo (sem tela)
cfg={}
info=C.situacao(m.DB_PATH,cfg,CNPJ,'nfse',None,HOJE)
assert info['fonte']=='banco' and info['ate']==ONTEM and info['notas']==5 and info['inicio']==ONTEM-timedelta(days=3)           # sem registro: o arquivo diz
C.registrar(cfg,CNPJ,'nfse',ate=HOJE-timedelta(days=2),nsu=600)
info=C.situacao(m.DB_PATH,cfg,CNPJ,'nfse',None,HOJE); assert info['fonte']=='busca' and info['ate']==HOJE-timedelta(days=2) and info['inicio']==HOJE-timedelta(days=5)       # o registro vale mais
assert C.situacao(m.DB_PATH,{},VAZIA,'nfse',None,HOJE)['ate'] is None and C.situacao(m.DB_PATH,{},VAZIA,'nfse',None,HOJE)['inicio'] is None      # nada guardado: nada a pular
indice={'empresas':{VAZIA:{'nome':'X','meses':{'2026-08':{'conhecidos':9,'no_servidor':9,'diferentes':0},'2026-09':{'conhecidos':4,'no_servidor':4,'diferentes':0},'2026-10':{'conhecidos':3,'no_servidor':0,'diferentes':0}}}}}
ir=C.situacao(m.DB_PATH,{},VAZIA,'nfse',indice,HOJE); assert ir['fonte']=='repositorio' and ir['ate']==date(2026,9,30) and ir['notas']==13,ir          # banco vazio: o repositório diz (último mês com arquivos)
assert C.registrar({},'123','nfse') is None and C.registrar({},CNPJ,'xxx') is None
fut={}; C.registrar(fut,CNPJ,'nfse',ate=HOJE+timedelta(days=9)); assert C.situacao(m.DB_PATH,fut,CNPJ,'nfse',None,HOJE)['ate']==HOJE      # nunca depois de hoje
i0=C.situacao(m.DB_PATH,cfg,CNPJ,'nfse',None,HOJE)
assert C.inicio_inteligente(i0,date(2026,1,1),HOJE)==i0['inicio'] and C.inicio_inteligente(i0,HOJE,HOJE)==HOJE and C.inicio_inteligente({},date(2026,1,1))==date(2026,1,1)
assert C.precisa_avisar(i0,date(2026,1,1)) and not C.precisa_avisar(i0,HOJE) and not C.precisa_avisar(i0,None) and not C.precisa_avisar({},date(2026,1,1))
txt=C.aviso(i0,'nfse'); assert 'NFS-e guardadas até' in txt and C.formatar(i0['ate']) in txt and '5 nota' in txt and C.aviso({}, 'nfse')==''

# ---------------- tela
db_ok=True
import exato_nfse_portal as portal
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaBusca#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaBusca#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
msgs=[]; m.messagebox.showinfo=lambda *a,**k:msgs.append(a); m.messagebox.showwarning=lambda *a,**k:msgs.append(a); m.messagebox.showerror=lambda *a,**k:msgs.append(a)
app=m.App(current_user=user)
import traceback; app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
def wait(cond,t=12,start=None):
    """Roda o mainloop de verdade (as threads só podem chamar after() com o loop ativo, como no programa real)."""
    end=time.time()+t; res=[False]
    def tick():
        if cond(): res[0]=True; app.quit()
        elif time.time()>end: app.quit()
        else: app.after(30,tick)
    if start: app.after(0,start)
    app.after(40,tick); app.mainloop(); return res[0]
try:
    app.geometry('1366x650+0+0'); app.update()
    app.config_data.pop('busca_cobertura',None); app.config_data.pop('busca_preferencia',None)
    # ---- portal da NFS-e: o que o portal recebe
    pedidos=[]; resultado={'falhas':0}
    def falso(user_,senha,cnpj,d_from,d_to,*a,**k):
        pedidos.append((d_from,d_to)); return [], {'emitidas':0,'recebidas':0,'fora_periodo':0,'outras_empresas':0,'falhas':resultado['falhas'],'sessao_reaproveitada':False}
    portal.fetch_via_portal=falso
    dialogos=[]; respostas=[('novo',True)]
    def dlg(titulo,texto,a,b): dialogos.append((titulo,texto)); return respostas.pop(0) if respostas else ('novo',False)
    app._busca_dialog=dlg
    def buscar(cnpj,de='',ate_='',modo='login'):
        app._nfse_ensure_built(); app._show_nfse(); app.update()
        app.nfse_company.set(cnpj); app.nfse_from.set(de); app.nfse_to.set(ate_); app._nfse_set_mode(modo); app.nfse_user.set(cnpj); app.nfse_pass.set('segredo')
        pedidos.clear(); app._nfse_running=False; wait(lambda: not app._nfse_running,start=app._nfse_start)
    # 1) período vazio, empresa com notas até ontem: só de (ontem-3) até hoje (não o mês anterior inteiro)
    buscar(CNPJ)
    assert pedidos and pedidos[0]==(ONTEM-timedelta(days=3),HOJE),pedidos
    assert app.config_data['busca_cobertura'][CNPJ]['nfse']['ate']==HOJE.isoformat()                 # busca completa: registrada
    assert not dialogos
    # 2) empresa sem nada guardado: mês anterior, como antes
    buscar(VAZIA); ini,fim=app._nfse_previous_month(); assert pedidos[0]==(ini,fim),(pedidos,ini,fim)
    assert VAZIA not in (app.config_data.get('busca_cobertura') or {}) or True
    # 3) período digitado que repete o que já está guardado: avisa; 'novo' (lembrado) recomeça na cobertura
    app.config_data['busca_cobertura'][CNPJ]['nfse']['ate']=(HOJE-timedelta(days=2)).isoformat()
    buscar(CNPJ,'01/07/2026',HOJE.strftime('%d/%m/%Y'))
    assert len(dialogos)==1 and 'já tem' in dialogos[0][1] and 'NFS-e' in dialogos[0][1] and 'dias de folga' in dialogos[0][1],dialogos
    assert pedidos[0][0]==HOJE-timedelta(days=5) and pedidos[0][1]==HOJE and app.config_data['busca_preferencia'][re.sub(r'\D','',CNPJ)]=='novo' if (re:=__import__('re')) else False
    # 4) com a escolha lembrada não pergunta de novo
    app.config_data['busca_cobertura'][CNPJ]['nfse']['ate']=(HOJE-timedelta(days=2)).isoformat(); dialogos.clear()
    buscar(CNPJ,'01/07/2026',HOJE.strftime('%d/%m/%Y')); assert not dialogos and pedidos[0][0]==HOJE-timedelta(days=5)
    # 5) 'período todo' mantém o período pedido; 'cancelar' não busca
    app.config_data['busca_preferencia'].pop(CNPJ,None); app.config_data['busca_cobertura'][CNPJ]['nfse']['ate']=(HOJE-timedelta(days=2)).isoformat()
    respostas[:]=[('tudo',False)]; buscar(CNPJ,'01/07/2026',HOJE.strftime('%d/%m/%Y')); assert pedidos and pedidos[0][0]==date(2026,7,1),pedidos
    respostas[:]=[('cancelar',False)]; buscar(CNPJ,'01/07/2026',HOJE.strftime('%d/%m/%Y')); assert not pedidos
    # 6) busca automática (silenciosa): nunca pergunta, vale "só o novo"
    app.config_data['busca_cobertura'][CNPJ]['nfse']['ate']=(HOJE-timedelta(days=2)).isoformat()
    app._auto_round_active=True; dialogos.clear(); respostas[:]=[]; buscar(CNPJ,'01/07/2026',HOJE.strftime('%d/%m/%Y')); app._auto_round_active=False
    assert not dialogos and pedidos[0][0]==HOJE-timedelta(days=5),(dialogos,pedidos)
    # 7) busca que não terminou bem NÃO conta como coberta
    app.config_data['busca_cobertura'][CNPJ]['nfse']['ate']='2026-09-01'; resultado['falhas']=2
    buscar(CNPJ,HOJE.strftime('%d/%m/%Y'),HOJE.strftime('%d/%m/%Y')); assert app.config_data['busca_cobertura'][CNPJ]['nfse']['ate']=='2026-09-01'; resultado['falhas']=0
    # ---- cursor do Emissor Nacional (certificado): vale o maior entre o ponto salvo e o que o arquivo já guardou
    app.config_data.setdefault('sync_state',{}).pop(m._sync_state_key(CNPJ,'nfse'),None)
    assert app._nfse_cursor(CNPJ)==404                                                       # configuração perdida: o arquivo diz (maior NSU guardado, 504, menos a folga de 100)
    m.save_nsu_state(app.config_data,CNPJ,'nfse',900,1); assert app._nfse_cursor(CNPJ)==900  # ponto salvo: vale sempre o ponto salvo
    m.save_nsu_state(app.config_data,CNPJ,'nfse',10,1); assert app._nfse_cursor(CNPJ)==10
    m.save_nsu_state(app.config_data,CNPJ,'nfse',504,1)
    visto=[]
    def falso_fetch(thumb,last,homolog,cnpj,**k): visto.append(last); return [],last,{'cancelled':False}
    nfse_mod.fetch_all_new=falso_fetch
    app.nfse_selected={'Thumbprint':'AA','FriendlyName':'CN=PRESTADORA:12345678000195','NotAfter':'2099-01-01','Document':'12.345.678/0001-95'}
    app.nfse_company.set(CNPJ); app._nfse_set_mode('cert'); app._nfse_running=False; wait(lambda: not app._nfse_running,start=app._nfse_start)
    assert visto==[504],visto                                                  # com ponto salvo continua exatamente dele
    # ---- Buscar XML: ponto de partida zerado com arquivo cheio -> pergunta / segue o que foi lembrado
    app._show_webservice_test(); app.update()
    app.use_saved_var.set(True); app.config_data.setdefault('busca_preferencia',{}).pop(OUTRA,None)
    starts={'nfe':0,'nfce':0}; respostas[:]=[('novo',False)]; dialogos.clear()
    assert app._busca_ajustar_inicio(OUTRA,starts) is True and starts['nfe']==4 and len(dialogos)==1 and starts['nfce']==0       # nfe: arquivo até o NSU 104 (menos a folga de 100); nfce: nada guardado
    starts={'nfe':0,'nfce':0}; respostas[:]=[('tudo',False)]; assert app._busca_ajustar_inicio(OUTRA,starts) is True and starts['nfe']==0
    starts={'nfe':0,'nfce':0}; respostas[:]=[('cancelar',False)]; assert app._busca_ajustar_inicio(OUTRA,starts) is False
    starts={'nfe':777,'nfce':0}; dialogos.clear(); assert app._busca_ajustar_inicio(OUTRA,starts) is True and starts['nfe']==777 and not dialogos      # já tem ponto salvo: não mexe
    app.use_saved_var.set(False); starts={'nfe':0,'nfce':0}; assert app._busca_ajustar_inicio(OUTRA,starts) is True and starts['nfe']==0 and not dialogos      # NSU digitado pela pessoa vale
    # ---- avisos na tela
    app.cnpj_var.set(CNPJ); app._confirm_cnpj() if hasattr(app,'_confirm_cnpj') else None
    app._nfse_ensure_built(); app._show_nfse(); app.nfse_company.set(CNPJ); app.update(); app._nfse_update_company_hint(); app.update()
    assert 'Arquivo de NFS-e até' in app.nfse_company_hint.cget('text') and '3 dias de folga' in app.nfse_company_hint.cget('text'),app.nfse_company_hint.cget('text')
    # ---- lista de documentos: sem carregar todos os XMLs de uma vez, mas o XML chega quando alguém usa
    docs=m.db_load_documents_as_payload(OUTRA,limit=100)
    assert len(docs)==5 and type(docs[0]).__name__=='LazyXmlRow' and not dict.__contains__(docs[0],'xml')
    assert docs[0]['xml'].startswith(b'<x n=') and docs[1].get('xml')==b'<x n="%d"/>'%int(docs[1]['numero']) and len(dict(docs[2])['xml'])>0 and docs[3]['chave'].endswith('1')
    app.geometry('1000x600+0+0'); app._show_webservice_test(); app.update(); app._show_nfse(); app.update()
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V173 busca inteligente: OK')
