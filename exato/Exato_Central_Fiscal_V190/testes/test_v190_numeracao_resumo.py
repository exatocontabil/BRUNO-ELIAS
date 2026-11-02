"""V182: numeração faltando (NF-e/NFC-e de saída), bloco no PDF de Documentos e resumo diário por e-mail (montagem, um envio por dia, tela)."""
import os, sys, tempfile, sqlite3, time
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_num_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as e
import exato_numeracao as N, exato_resumo_diario as RD, exato_relatorio_docs_pdf as X
import pypdf
# ---- lacunas
L=lambda s,n: {'serie':s,'numero':n}
assert N.lacunas([L('1',x) for x in (1,2,5,6,9)])=={'1':[(3,4),(7,8)]} and N.lacunas([L('1',x) for x in (1,2,3)])=={} and N.lacunas([L('1','0007'),L('1','10')])=={'1':[(8,9)]}
assert N.lacunas([L('1',1),L('1',3),L('2',10),L('2',11)])=={'1':[(2,2)]}          # séries separadas
assert N.texto_faixas([(3,4),(7,7)])=='3–4, 7' and N.total_faltando([(3,4),(7,7)])==3 and 'e mais 2 faixa(s)' in N.texto_faixas([(i*3,i*3) for i in range(1,5)],limite=2)
# ---- bloco no PDF (só NF-e/NFC-e de SAÍDA)
def lin(fam,mov,n,serie='1',sit='Autorizada'): return {'familia':fam,'movimentacao':mov,'numero':str(n),'serie':serie,'data':'2026-09-10','valor':Decimal('10'),'situacao':sit,'exportada':False,'chave':'4'*44,'parte':'C','doc':'','empresa':'E','cnpj':'11222333000181'}
linhas=[lin('nfe','Saída',n) for n in (1,2,5,6)]+[lin('nfe','Saída',3,sit='Cancelada')]+[lin('nfe','Entrada',n,serie='9') for n in (100,200)]
tmp=Path(tempfile.mkdtemp(prefix='exato_v183_numpdf_')); pdf=tmp/'r.pdf'; X.gerar(linhas,str(pdf),'E','11222333000181','09/2026')
tx=' '.join(' '.join((p.extract_text() or '').split()) for p in pypdf.PdfReader(str(pdf)).pages)
assert 'Numeração faltando' in tx and 'série 1, 1 número(s)): 4' in tx and 'inutilizado' in tx          # falta o 4 (o 3 existe como cancelada); a entrada não conta
assert tx.count('Numeração faltando')==1
# ---- resumo diário: montagem
e._prepare_persistent_storage(); e.init_database()
import test_v190_auditoria_cancelada as T          # empresa com NF-e (uma cancelada)
CN=T.CNPJ; c=sqlite3.connect(e.DB_PATH)
c.execute("UPDATE documents SET issued_at='2026-10-03T10:00:00' WHERE status<>'Evento'"); c.execute("DELETE FROM documents WHERE access_key=?",(T.key(2),)); c.commit(); c.close()          # tira a nota 2: falta numeração
r=RD.montar(str(e.DB_PATH),e.load_config(),None,hoje=date(2026,10,9),canceladas_sem_evento=lambda cnpj: 2)
assert r['pendencias']>=1 and 'para conferir' in r['assunto'] and '2 cancelada(s) sem o XML' in r['texto'] and 'numeração faltando' in r['texto'] and 'EMPRESA TESTE LTDA' in r['texto'] and '<table' in r['html'],r['texto']
# ---- um envio por dia (marca no servidor) e regras de horário
srv=Path(tempfile.mkdtemp(prefix='exato_v183_rdsrv_')); base=str(srv)
assert RD.reivindicar_dia(base,'2026-10-09','PC1') and not RD.reivindicar_dia(base,'2026-10-09','PC2')          # só o primeiro envia
RD.liberar_dia(base,'2026-10-09'); assert RD.reivindicar_dia(base,'2026-10-09','PC2')
assert not RD.reivindicar_dia(str(srv/'nao_existe'),'2026-10-09')
cfg={'ativo':True,'destino':'a@b.com','ultimo':''}
assert RD.deve_enviar(cfg,datetime(2026,10,9,8,0)) and not RD.deve_enviar(cfg,datetime(2026,10,9,6,59)) and not RD.deve_enviar(dict(cfg,ultimo='2026-10-09'),datetime(2026,10,9,9,0)) and not RD.deve_enviar(dict(cfg,ativo=False),datetime(2026,10,9,9,0)) and not RD.deve_enviar(dict(cfg,destino=''),datetime(2026,10,9,9,0))
# ---- envio (servidor de e-mail falso)
enviados=[]
class Falso:
    def send_message(self,m): enviados.append(m)
    def quit(self): pass
RD.enviar({'remetente':'eu@x.com'},'a@b.com',r,conectar=lambda cfg: Falso())
m=enviados[0]; assert m['To']=='a@b.com' and m['From']=='eu@x.com' and m['Subject']==r['assunto'] and 'EMPRESA TESTE LTDA' in m.get_body(('plain',)).get_content() and m.get_body(('html',)) is not None
# ---- tela
u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); admin=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa'); e.enumerate_windows_certificates=lambda *a,**k:([],'')
app=e.App(current_user=admin); app.geometry('1366x650+0+0')
try:
    app._show_companies(); app.update(); app._resumo_dialog(); app.update()
    win,ativo,destino,salvar,testar,aviso=app._resumo_dlg
    ativo.set(True); destino.set('contador@x.com'); salvar(); cfgr=app._resumo_cfg(); assert cfgr['ativo'] and cfgr['destino']=='contador@x.com'          # sem Box-e configurado: salva e avisa (a janela continua aberta)
    assert 'Box-e' in aviso.cget('text'); win.destroy()
    app._repo_cfg()['pasta']=base; app.config_data['boxe'].update(ativo=True,servidor='smtp.x.com',usuario='u',senha_protegida='x',remetente='eu@x.com'); app._boxe_cfg_envio=lambda: {'servidor':'smtp.x.com','usuario':'u','senha':'s','remetente':'eu@x.com','destino':'d','porta':587,'seguranca':'STARTTLS'}
    RD.liberar_dia(base,datetime.now().strftime('%Y-%m-%d')); enviados.clear(); RD._conectar_antigo=None
    import exato_boxe as B; B._conectar=lambda cfg: Falso()
    cfgr['ultimo']=''; app._resumo_tick()
    f=time.time()
    while time.time()-f<10 and not cfgr['ultimo']:
        app.update()
        while app._repo_inbox: app._repo_inbox.popleft()()
        time.sleep(0.05)
    if datetime.now().hour>=RD.HORA_MINIMA: assert enviados and cfgr['ultimo']==datetime.now().strftime('%Y-%m-%d')          # enviou uma vez e marcou
    else: assert not enviados          # antes das 7h não envia
    print('V182 numeração e resumo diário OK')
finally:
    app.destroy()
