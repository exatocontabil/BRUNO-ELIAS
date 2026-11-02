"""V178 (tela): a tabela da Situação da busca é desenhada no próprio quadro (sem um componente por célula): rola liso, sem rastro, com muitas empresas; clique no selo e no botão."""
import os, sys, sqlite3, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_rol_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import tkinter as tk
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaRol#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaRol#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
def cnpj_valido(base):
    d=[int(x) for x in f'{base:08d}0001']
    for n in (12,13):
        pesos=[5,4,3,2,9,8,7,6,5,4,3,2][-n:] if n==12 else [6,5,4,3,2,9,8,7,6,5,4,3,2]
        soma=sum(a*b for a,b in zip(d,pesos)); r=soma%11; d.append(0 if r<2 else 11-r)
    return ''.join(map(str,d))
cnpjs=[cnpj_valido(10000000+i*7919) for i in range(120)]
for i,cn in enumerate(cnpjs): m.db_register_company(cn,f'EMPRESA NUMERO {i:03d} DE TESTE COM NOME BEM COMPRIDO LTDA')
c=sqlite3.connect(m.DB_PATH)
for i,cn in enumerate(cnpjs[:60]):
    c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(f'd{i}',cn,'nfe','NF-e','Saída','1','2026-10-01T10:00:00','10','Autorizado','%044d'%i,b'<x/>','2026-10-02',__import__('datetime').date.today().isoformat()))          # hoje: o teste não envelhece (atraso = mais de 3 dias)
c.commit(); c.close()
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
    app.geometry('1366x650+0+0'); app.update(); app._show_companies(); app.update(); app._sit_aba('situacao'); assert esperar(lambda: len(app._sit_lista)>=100 and not app._sit_lendo)
    cv=app._sit_canvas; app.update(); n=len(app._sit_lista)
    tipos={cv.type(i) for i in cv.find_all()}; assert 'window' not in tipos and tipos<={'text','rectangle','line'},tipos          # nada de componente por célula
    reg=[float(x) for x in str(cv.cget('scrollregion')).split()]; assert abs(reg[3]-min(n,300)*m._SIT_LINHA)<2,reg
    # redesenho com muitas empresas é rápido
    t0=time.time(); app._sit_desenhar(); app.update(); assert time.time()-t0<3.0,time.time()-t0
    # rolar: a posição muda e o conteúdo continua inteiro (a roda passa pelo WheelRouter: Canvas é rolagem interna)
    y0=cv.yview()[0]; cv.yview_scroll(5,'units'); app.update(); assert cv.yview()[0]>y0 and abs(cv.yview()[0]*reg[3]-5*m._SIT_LINHA)<2           # um passo = uma empresa (alinhado)
    assert len(app._sit_textos())>400
    # clicar num selo abre a janela "Por que?" e no botão chama a busca da empresa
    cv.yview_moveto(0); app.update(); abertos=[]; app._sit_porque=lambda c_,f_=None: abertos.append((c_,f_))
    app._sit_desenhar(); app.update()
    alvo=[i for i in cv.find_all() if cv.type(i)=='text' and cv.itemcget(i,'text')=='Em dia'][0]; bx=cv.bbox(alvo); cv.event_generate('<Button-1>',x=(bx[0]+bx[2])//2,y=(bx[1]+bx[3])//2); app.update()
    assert abertos and abertos[0][1] in ('nfe','nfce','cte','nfse'),abertos
    chamadas=[]; app._auto_round_start=lambda manual=False,only=None: chamadas.append(tuple(only or ())) or True
    botao=[i for i in cv.find_all() if cv.type(i)=='text' and cv.itemcget(i,'text') in ('Buscar o que falta','Buscar agora')][0]; bx=cv.bbox(botao); cv.event_generate('<Button-1>',x=(bx[0]+bx[2])//2,y=(bx[1]+bx[3])//2); app.update()
    assert chamadas and len(chamadas[0])==1,chamadas
    # janela estreita: redesenha nas novas larguras sem erro
    app.geometry('900x650+0+0'); app.update(); app._sit_largura=0; app._sit_desenhar(); app.update(); assert cv.winfo_width()>0 and len(app._sit_textos())>400
    app.update(); print('V178 situação rolagem OK')
finally:
    try: app.destroy()
    except Exception: pass
