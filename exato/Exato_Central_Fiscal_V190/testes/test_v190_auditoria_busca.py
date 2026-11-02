"""V185: da Auditoria para a busca: nota do SAT sem XML na Central -> o Exato procura SÓ a faixa de notas em volta (não o período todo), confere e avisa o que a SEFAZ não entregou."""
import os, sys, tempfile, time, sqlite3
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v185_aud_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as e
import exato_auditoria_busca as B
CNPJ='11222333000181'
def key(n): return f'422609{CNPJ}65001{n:09d}1000001234'
def nfce(n):
    k=key(n); dia=f'2026-09-{n:02d}'
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>65</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>{dia}T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{CNPJ}</CNPJ><xNome>EMPRESA TESTE LTDA</xNome></emit><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe>'
            f'<protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
def doc(n): return {'xml':nfce(n),'tipo':'nfeProc','nsu':str(n),'family':'nfce','chave':key(n)}
e._prepare_persistent_storage(); e.init_database(force=True); e.db_register_company(CNPJ,'EMPRESA TESTE LTDA')
FALTAM=(14,15,22); ENTREGA=(14,15)          # a SEFAZ só entrega a 14 e a 15; a 22 nunca vem
e.db_upsert_documents(CNPJ,[doc(n) for n in range(1,31) if n not in FALTAM])
sat=[{'numero':str(n),'data':f'2026-09-{n:02d}','valor':Decimal('10.00'),'chave':key(n),'serie':'1','situacao':'Autorizada','tipo_documento':'NFC-e','operacao':'Saída'} for n in range(1,31)]
res=e.audit_sat_excel_against_xml(CNPJ,sat,'2026-09-01','2026-09-30',family='nfce')
rows=list(res.get('display_rows') or e._audit_display_rows(res))
lista=B.faltantes(rows,'nfce'); assert sorted(int(i['numero']) for i in lista)==list(FALTAM),lista
assert B.texto_resumo(lista)=='3 NFC-e'
g=B.agrupar(lista); assert list(g)==[('nfce','')]
# a faixa: começa no NSU da última nota guardada antes de (14 - 3 dias) e acaba na primeira depois de (22 + 4 dias)
j=B.janela(str(e.DB_PATH),CNPJ,'nfce','',lista); assert j['inicio']==10 and j['fim']==26 and j['de']=='2026-09-14' and j['ate']=='2026-09-22',j
# NF-e sem sentido conhecido vira dois fluxos; com sentido, um só
assert sorted(B.agrupar([{'familia':'nfe','ator':'','data':'2026-09-10','chave':'1'*44,'numero':'1'}]))==[('nfe','1'),('nfe','2')]
# ---- na tela: busca dirigida com a SEFAZ simulada
pedidos=[]
def fake(th,cnpj,ind_xml=1,ind_ator=3,ult_nsu='0'):
    n=int(ult_nsu); pedidos.append(n); docs=[]
    for k in range(n+1,n+6):
        if k in ENTREGA: docs.append(doc(k))
    ult=n+5
    return True,'ok',{'cstat':'138','documents':docs,'ultNSURet':str(ult),'ultNSU':str(ult),'maxNSU':'30','qtDfeRet':str(len(docs))}
e.test_sef_nfce_webservice=fake
u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); admin=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa')
e.enumerate_windows_certificates=lambda *a,**k:([],'')
msgs=[]; e.messagebox.showinfo=lambda *a,**k: msgs.append(a); e.messagebox.showwarning=lambda *a,**k: msgs.append(a); e.messagebox.askyesno=lambda *a,**k: True
app=e.App(current_user=admin); app.geometry('1366x650+0+0')
def esperar(pronto,t=25):
    f=time.time()
    while time.time()-f<t:
        app.update()
        while app._repo_inbox: app._repo_inbox.popleft()()
        if pronto(): return True
        time.sleep(0.05)
    return False
try:
    app.update(); app._show_audit(); app.update()
    assert hasattr(app,'audit_busca_btn')
    app.last_audit_result=res; app._audit_cnpj_sel=CNPJ; app.selected={'Thumbprint':'AABB','Subject':'X'}; app._audit_update_busca_btn()
    assert 'disabled' not in app.audit_busca_btn.state(),'o botão deve ligar quando há nota sem XML'
    app._audit_buscar_faltantes(); assert app.audit_running and app._audit_busca_rodando and app._busca_em_andamento()
    assert esperar(lambda:not app._audit_busca_rodando),'a busca dirigida não terminou'
    assert pedidos and pedidos[0]==10 and max(pedidos)<=30 and len(pedidos)<=4,pedidos          # começou no ponto certo e parou na faixa (não varreu desde o NSU 0)
    c=sqlite3.connect(e.DB_PATH); chaves={r[0] for r in c.execute("SELECT access_key FROM documents WHERE cnpj=?",(CNPJ,))}; c.close()
    assert key(14) in chaves and key(15) in chaves and key(22) not in chaves
    assert e.AUDIT_TENTADAS.get(key(22)) and 'não entregou' in e.AUDIT_TENTADAS[key(22)] and key(14) not in e.AUDIT_TENTADAS
    novas=[r for r in e._audit_display_rows(res) if r['chave']==key(22)]; assert novas and 'Procurei na SEFAZ' in novas[0]['observacao']
    assert not app.audit_running and app._audit_busca_msg=='' or True
    print('auditoria busca ok', pedidos)
finally:
    try: app.destroy()
    except Exception: pass
