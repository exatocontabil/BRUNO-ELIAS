"""V176 (tela): Empresas > Situação da busca (abas, quadros, selos por tipo, filtros, "Buscar o que falta"); Repositório: meses fechados já aparecem
logo após fechar, coluna "Por que ainda não fechou", "Fechar agora" fecha tudo o que está pronto."""
import os, sys, sqlite3, tempfile, time
from datetime import datetime, timedelta, date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v176_situi_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import tkinter as tk
from tkinter import ttk
import exato_central_fiscal as m
import exato_cobertura as C, exato_repositorio as R
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaSit#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaSit#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
A,B='11222333000181','12345678000195'; m.db_register_company(A,'ALFA LTDA'); m.db_register_company(B,'BETA LTDA')
vista=(datetime.now()-timedelta(days=20)).isoformat(timespec='seconds'); hoje=date.today()
c=sqlite3.connect(m.DB_PATH)
for i in range(1,5):
    c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (f'n{i}',A,'nfe','NF-e','Saída',str(i),'1','2026-07-10T10:00:00','10.00','Autorizado','%044d'%i,b'<x n="%d"/>'%i,vista,vista))
c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES('c1',?,'cte','CT-e','Entrada','1','1','2026-03-10T10:00:00','10.00','Autorizado',?,?,?,?)",(A,'%044d'%99,b'<x/>','2026-03-11T10:00:00','2026-03-11T10:00:00'))
c.commit(); c.close()
srv=Path(tempfile.mkdtemp(prefix='exato_v176_srv_'))
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
def achar(w,texto):
    for x in w.winfo_children():
        try:
            if str(x.cget('text'))==texto: return x
        except Exception: pass
        r=achar(x,texto)
        if r is not None: return r
def textos(w):
    out=[]
    for x in w.winfo_children():
        try: out.append(str(x.cget('text')))
        except Exception: pass
        out+=textos(x)
    return out
try:
    app.geometry('1366x650+0+0'); app.update()
    # ---- aba Situação da busca
    app._show_companies(); app.update(); assert achar(app.companies_frame,'Carteira') and achar(app.companies_frame,'Situação da busca')
    assert app.company_table_canvas.winfo_manager()=='pack' or app.company_table_canvas.winfo_ismapped()
    C.registrar(app.config_data,A,'nfe'); C.registrar(app.config_data,A,'nfse')      # ALFA: buscada hoje (NF-e, NFC-e, CT-e) e NFS-e
    achar(app.companies_frame,'Situação da busca').invoke(); assert esperar(lambda: app.sit_frame.winfo_manager()=='pack' and app._sit_lista)
    assert not app.company_table_canvas.winfo_manager() or not app.company_table_canvas.winfo_ismapped()          # a carteira saiu de cena
    app.update(); tx=app._sit_textos()
    assert 'ALFA LTDA' in tx and 'BETA LTDA' in tx and 'Em dia' in tx and 'Sem notas' in tx and 'Ainda não buscado' in tx,tx
    assert app._sit_tiles['empresas'].cget('text')=='2' and app._sit_tiles['em_dia'].cget('text')=='1' and app._sit_tiles['nunca'].cget('text')=='1'
    # filtros
    app._sit_situacao.set('Só em dia'); app._sit_render(); assert 'BETA LTDA' not in app._sit_textos() and 'ALFA LTDA' in app._sit_textos()
    app._sit_situacao.set('Todas'); app._sit_texto.set('beta'); app._sit_render(); assert 'ALFA LTDA' not in app._sit_textos(); app._sit_texto.set(''); app._sit_render()
    # "Buscar o que falta": chama a rodada para as empresas pendentes (sem rodar de verdade)
    chamadas=[]; app._auto_round_start=lambda manual=False,only=None: chamadas.append((manual,tuple(only or ()))) or True
    app._sit_btn_tudo.invoke(); assert chamadas==[(True,(B,))],chamadas and toasts
    assert any('Buscando 1 empresa(s)' in t for t,_ in toasts),toasts
    app._sit_buscar([A]); assert chamadas[-1]==(True,(A,))
    # a aba escolhida fica lembrada; voltar à carteira
    assert app.config_data.get('empresas_aba')=='situacao'
    achar(app.companies_frame,'Carteira').invoke(); app.update(); assert app.sit_frame.winfo_manager()=='' and app.company_table_canvas.winfo_ismapped()
    assert app.config_data.get('empresas_aba')=='carteira'
    # ---- Repositório: fechar agora fecha tudo o que está pronto e a tela já mostra "Mês fechado"
    cfg=app._repo_cfg(); cfg['pasta']=str(srv); app._show_repo(); app.update()
    app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'])
    esperar(lambda: app._fech_motivos is not None if hasattr(app,'_fech_motivos') else False,8)
    app._repo_indice_iniciar(forcar=True); assert esperar(lambda: not app._repo_indice_rodando); app._repo_refresh_view(); app.update()
    linhas=[app.repo_tree.item(i,'values') for i in app.repo_tree.get_children()]; assert linhas and all(len(v)==6 for v in linhas),linhas
    app._indice_antes=app._repo_indice
    app._fechamento_start(manual=True); assert esperar(lambda: not app._fechamento_state['rodando'])
    assert (A,'2026-07') in app._repo_fech and app._repo_fech[(A,'2026-07')][0]                     # já marcado, sem esperar a varredura
    app.repo_filtro_situacao.set('Só meses fechados'); app._repo_filtrar(salvar=False); assert len(app.repo_tree.get_children())==2      # julho (NF-e) e março (CT-e)
    app.repo_filtro_situacao.set('Todas'); app._repo_filtrar(salvar=False)
    ind,_=R.ler_indice(str(srv)); assert R.indice_fechamentos(ind)[(A,'2026-07')][0]                  # e o índice do servidor também foi anotado
    # varredura em andamento quando a novidade chega: refaz ao terminar
    app._repo_indice_rodando=True; app._repo_indice_repetir=False; app._repo_indice_iniciar(forcar=True); assert app._repo_indice_repetir
    app._repo_indice_rodando=False; app._repo_indice_repetir=False
    app.update(); print('V176 situação da busca UI OK')
finally:
    try: app.destroy()
    except Exception: pass
