"""V178: nenhum computador busca de novo o que outro já buscou — ponto de continuação e cobertura no servidor, e "Trazer do servidor" (XMLs do Repositório para o banco)."""
import os, sys, sqlite3, tempfile, time, json
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_comp_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_busca_compartilhada as C, exato_repositorio as R
srv=Path(tempfile.mkdtemp(prefix='exato_v183_srvcomp_')); CN='11222333000181'
# ---- publicar junta (vale o maior) e é lido por todos
assert C.ler(str(srv)) is None
assert C.publicar(str(srv),{f'{CN}:nfe':5000,f'{CN}:cte_emitente':300},{CN:{'nfe':'2026-10-05'}},'PC-A')
d=C.ler(str(srv)); assert C.nsu_compartilhado(d,f'{CN}:nfe')==5000 and C.cobertura_compartilhada(d,CN,'nfe')==date(2026,10,5) and d['nsu'][f'{CN}:nfe']['por']=='PC-A'
assert not C.publicar(str(srv),{f'{CN}:nfe':4000},{CN:{'nfe':'2026-10-01'}},'PC-B')              # mais atrasado: não muda nada
assert C.publicar(str(srv),{f'{CN}:nfe':5200},{CN:{'nfe':'2026-10-06','cte':'2026-10-06'}},'PC-B'); d=C.ler(str(srv))
assert C.nsu_compartilhado(d,f'{CN}:nfe')==5200 and C.nsu_compartilhado(d,f'{CN}:cte_emitente')==300 and C.cobertura_compartilhada(d,CN,'cte')==date(2026,10,6)
assert not [p for p in (srv/'Repositório'/'.indice').iterdir() if p.name.endswith('.tmp')]
assert not C.publicar(str(srv/'nao_existe'),{f'{CN}:nfe':1},{},'PC-C') and C.ler(str(srv/'nao_existe')) is None            # servidor fora: nada quebra
# ---- ponto de partida: o mais adiantado, menos a folga
assert C.adotar(d,0,f'{CN}:nfe',100)==(5100,'servidor')                                          # computador novo começa do ponto do servidor
assert C.adotar(d,5150,f'{CN}:nfe',100)==(5150,'local')                                          # praticamente igual: fica o local
assert C.adotar(d,9000,f'{CN}:nfe',100)==(9000,'local') and C.adotar(None,7,'x',100)==(7,'local')
# ---- na tela: aplica antes de buscar
import tkinter as tk
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaCmp#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaCmp#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
m.db_register_company(CN,'ALFA LTDA')
app=m.App(current_user=user); toasts=[]; app._toast=lambda t,k='info',ms=0: toasts.append((t,k))
import traceback
app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
def esperar(cond,t=25):
    fim=time.time()+t
    while time.time()<fim:
        app.update()
        if cond(): return True
        time.sleep(.03)
    return False
try:
    app.geometry('1366x650+0+0'); app.update(); cfg=app._repo_cfg(); cfg['pasta']=str(srv)
    app._compartilhada_atualizar(forcar=True); assert esperar(lambda: getattr(app,'_busca_comp',None) is not None and not app._busca_comp_lendo)
    assert m.get_saved_nsu(app.config_data,CN,'nfe')==0
    assert app._compartilhada_aplicar(CN)>=1 and m.get_saved_nsu(app.config_data,CN,'nfe')==5100 and app.config_data['v028_bootstrap'][f'{CN}:nfe'] is True
    assert m.get_saved_nsu(app.config_data,CN,'cte_emitente')==200 and esperar(lambda: any('Trazer do servidor' in t for t,_ in toasts))          # 300 - folga (o aviso passa pela fila da tela)
    toasts.clear(); assert app._compartilhada_aplicar(CN)==0 and not toasts                       # repetir não adota de novo
    app.config_data['sync_state'][f'{CN}:nfe']['last_saved_nsu']=9999; assert app._compartilhada_aplicar(CN)==0 and m.get_saved_nsu(app.config_data,CN,'nfe')==9999          # este computador está mais adiantado
    # cobertura compartilhada entra na decisão da busca inteligente
    app._busca_comp=C.ler(str(srv)); info=app._busca_info(CN,'cte'); assert info['ate']==date(2026,10,6) and info['fonte']=='busca'
    # publicar depois de buscar
    app.config_data['sync_state']={f'{CN}:nfe':{'last_saved_nsu':7000}}; app._busca_comp_pub_em=-9999; app._compartilhada_publicar(); assert esperar(lambda: C.nsu_compartilhado(C.ler(str(srv)),f'{CN}:nfe')==7000)
    # ---- Trazer do servidor: XMLs do Repositório voltam para o banco, sem duplicar
    from test_v190_nfse_core import nfse_xml, chave, PREST
    EM=CN; DEST='99888777000166'; ch='35260911222333000181550010000000011000000100'
    nfe=('<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe%s"><ide><mod>55</mod><nNF>1</nNF><serie>1</serie><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide><emit><CNPJ>%s</CNPJ><xNome>ALFA LTDA</xNome></emit><dest><CNPJ>%s</CNPJ><xNome>DEST</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe></nfeProc>'%(ch,EM,DEST)).encode()
    m.db_upsert_documents(EM,[{'xml':nfe,'family':'nfe'}]); m.db_register_company(PREST,'PRESTADORA LTDA')
    m.db_upsert_nfse_items(PREST,[{'xml':nfse_xml(i,prest=PREST,toma='98765432000110',valor='100.00',dh='2026-09-%02dT10:00:00-03:00'%(5+i)),'chave':chave(i),'nsu':0} for i in range(1,4)])
    r=R.copiar_pendentes(str(m.DB_PATH),str(srv)); assert r['ok'] and r['novos']>=4,r
    contagem=lambda: sqlite3.connect(m.DB_PATH).execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    antes=contagem(); assert antes==4
    c=sqlite3.connect(m.DB_PATH); c.execute("DELETE FROM documents WHERE family='nfse' AND cnpj=?",(PREST,)); c.commit(); c.close(); assert contagem()==1
    m.messagebox.askyesno=lambda *a,**k: True; m.messagebox.showinfo=lambda *a,**k: None
    app._repo_trazer(); assert esperar(lambda: not getattr(app,'_trazendo',True))
    assert contagem()==4,contagem()                                                                # as 3 NFS-e voltaram; a NF-e que já estava aqui não duplicou
    app._repo_trazer(); assert esperar(lambda: not getattr(app,'_trazendo',True)); assert contagem()==4 and any('já estavam' in t for t,_ in toasts)
    app.update(); print('V178 busca compartilhada OK')
finally:
    try: app.destroy()
    except Exception: pass
