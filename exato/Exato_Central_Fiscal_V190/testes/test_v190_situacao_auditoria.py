"""V186: Situação da busca mostra se a Auditoria Fiscal já foi feita (Auditada / Com divergência / Auditada em parte / Não auditada), com filtro e clique que abre a Auditoria da empresa."""
import os, sys, sqlite3, tempfile, time, json
from datetime import datetime, timedelta, date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v186_aud_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
import exato_situacao_busca as S
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaSit#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaSit#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
A,B,C,D='11222333000181','12345678000195','45723174000110','11444777000161'
for cn,nm in ((A,'ALFA LTDA'),(B,'BETA LTDA'),(C,'GAMA LTDA'),(D,'DELTA LTDA')): m.db_register_company(cn,nm)
vista=(datetime.now()-timedelta(days=1)).isoformat(timespec='seconds')
c=sqlite3.connect(m.DB_PATH); n=0
def doc(cn,fam,i):
    global n; n+=1
    c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (f'd{n}',cn,fam,'NF-e','Saída',str(i),'1','2026-09-10T10:00:00','10.00','Autorizado','%044d'%n,b'<x/>',vista,vista))
doc(A,'nfe',1); doc(A,'nfce',2)          # ALFA: tem NF-e e NFC-e -> auditou só NFC-e (parcial)
doc(B,'nfce',3)                          # BETA: só NFC-e, auditada com sucesso
doc(C,'nfe',4)                           # GAMA: nunca auditada
# DELTA: sem notas
c.commit(); c.close()
hist=[{'timestamp':'2026-10-05T09:00:00','cnpj':A,'family':'nfce','selected_families':['nfce'],'period_start':'2026-09-01','period_end':'2026-09-30','status':'conforme','missing_count':0},
      {'timestamp':'2026-10-06T09:00:00','cnpj':B,'family':'nfce','selected_families':['nfce'],'period_start':'2026-09-01','period_end':'2026-09-30','status':'divergencia','missing_count':3},
      {'timestamp':'2026-10-07T09:00:00','cnpj':B,'family':'nfce','selected_families':['nfce'],'period_start':'2026-09-01','period_end':'2026-09-30','status':'conforme','missing_count':0},          # a mais recente vale
      {'timestamp':'2026-10-08T09:00:00','cnpj':'123','family':'nfce','selected_families':['nfce'],'status':'conforme'}]
aud=S.auditorias_por_empresa(hist)
assert aud[B]['nfce']['status']=='conforme' and aud[B]['nfce']['sem_xml']==0 and aud[A]['nfce']['fim']==date(2026,9,30) and '123' not in aud
linhas={l['cnpj']:l for l in S.linhas(m.DB_PATH,m.load_config(),None,auditorias=aud)}
est={k:v['auditoria']['estado'] for k,v in linhas.items()}
assert est=={A:'parcial',B:'auditada',C:'nunca',D:'sem_notas'},est
assert linhas[A]['auditoria']['texto']=='Auditada em parte' and 'falta: NF-e' in linhas[A]['auditoria']['detalhe'] and 'NFC-e: 01/09 a 30/09' in linhas[A]['auditoria']['detalhe']
assert linhas[C]['auditoria']['texto']=='Não auditada'
# auditoria com nota sem XML = com divergência
aud2=S.auditorias_por_empresa(hist[:2]); l2={l['cnpj']:l for l in S.linhas(m.DB_PATH,m.load_config(),None,auditorias=aud2)}
assert l2[B]['auditoria']['estado']=='divergencia' and '3 sem XML' in l2[B]['auditoria']['detalhe']
# filtros novos
lista=list(linhas.values())
assert {l['cnpj'] for l in S.filtrar(lista,situacao='Só sem auditoria')}=={A,C}
assert {l['cnpj'] for l in S.filtrar(list(l2.values()),situacao='Só com divergência na auditoria')}=={B}
# multi-tipo (NF-e + NFC-e numa auditoria só)
mult=S.auditorias_por_empresa([{'timestamp':'2026-10-09T09:00:00','cnpj':A,'family':'multi','selected_families':['nfe','nfce'],'period_start':'2026-09-01','period_end':'2026-09-30','status':'conforme','missing_count':0,
                               'subaudits':{'nfe':{'status':'conforme','missing_count':0},'nfce':{'status':'divergencia','missing_count':2}}}])
assert mult[A]['nfe']['status']=='conforme' and mult[A]['nfce']['status']=='divergencia' and mult[A]['nfce']['sem_xml']==2
# ---- na tela
AH=m.AUDIT_HISTORY_PATH; AH.write_text(json.dumps(hist),encoding='utf-8')
app=m.App(current_user=user)
try:
    app.update(); app._show_companies(); app.update(); app._sit_aba('situacao')
    f=time.time()
    while time.time()-f<15:
        app.update()
        if getattr(app,'_sit_lista',None): break
        time.sleep(.05)
    while app._repo_inbox: app._repo_inbox.popleft()()
    app._sit_render(); app.update()
    tx=' | '.join(app._sit_textos())
    assert 'Auditoria' in [t for t,_ in app._sit_colunas] and 'Auditada em parte' in tx and 'Auditada' in tx and 'Não auditada' in tx and 'Sem notas p/ auditar' in tx,tx
    app._sit_situacao.set('Só sem auditoria'); app._sit_render(); app.update()
    nomes=' | '.join(app._sit_textos()); assert 'ALFA LTDA' in nomes and 'GAMA LTDA' in nomes and 'BETA LTDA' not in nomes,nomes
    app._sit_situacao.set('Todas'); app._sit_render()
    # clique abre a Auditoria já na empresa
    app._sit_auditoria(C); app.update(); assert app._audit_cnpj()==C and app.current_screen=='audit'
    # "Por que?" traz a seção da auditoria
    app._show_companies(); app.update(); app._sit_porque(A); app.update()
    win=app._sit_porque_win; txt=[w for w in win.winfo_children()]
    def todos(w):
        for x in w.winfo_children():
            yield x; yield from todos(x)
    corpo=[x for x in todos(win) if x.winfo_class()=='Text'][0].get('1.0','end'); assert 'Auditoria Fiscal' in corpo and 'Auditada em parte' in corpo,corpo[-400:]
    print('situacao auditoria ok')
finally:
    try: app.destroy()
    except Exception: pass
