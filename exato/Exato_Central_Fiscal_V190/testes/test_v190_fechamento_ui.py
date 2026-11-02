"""V174 (tela): Repositório com o cartão "Fechamento do mês e ZIPs", fechamento automático em segundo plano, "Fechar agora", etiqueta "Mês fechado", ZIPs dos meses já salvos."""
import os, sys, sqlite3, tempfile, time, zipfile
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_fechui_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import tkinter as tk
from tkinter import ttk
import exato_central_fiscal as m
import exato_repositorio as R
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaFec#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaFec#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
CNPJ='11222333000181'; m.db_register_company(CNPJ,'ELETROTAK MANUTENCAO LTDA')
vista=(datetime.now()-timedelta(days=15)).isoformat(timespec='seconds')
c=sqlite3.connect(m.DB_PATH)
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'n{i}',CNPJ,'nfe','NF-e','Saída',str(i),'1','2026-07-10T10:00:00','100.00','Autorizado','%044d'%i,b'<nfe n="%d"/>'%i,vista,vista) for i in range(1,5)]); c.commit(); c.close()
srv=Path(tempfile.mkdtemp(prefix='exato_v174_srvfec_'))
app=m.App(current_user=user); toasts=[]; app._toast=lambda t,k='info',ms=0: toasts.append((t,k))
avisos=[]; m.messagebox.showinfo=lambda *a,**k: avisos.append(a); m.messagebox.showwarning=lambda *a,**k: avisos.append(a); m.messagebox.askyesno=lambda *a,**k: True
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
try:
    app.geometry('1366x650+0+0'); app.update(); cfg=app._repo_cfg(); cfg['pasta']=str(srv)
    app._show_repo(); app.update()
    assert achar(app.repo_frame,'Fechamento do mês e ZIPs') and achar(app.repo_frame,'Fechar agora') and achar(app.repo_frame,'Gerar ZIPs dos meses já salvos...') and achar(app.repo_frame,'Fechar os meses sozinho')
    assert 'sozinho quando passam 5 dias' in app.repo_fech_status.cget('text'),app.repo_fech_status.cget('text')
    # nada copiado ainda: o mês não fecha
    app._fechamento_start(manual=True); assert esperar(lambda: not app._fechamento_state['rodando']); assert any('Nenhum mês pronto' in t for t,_ in toasts),toasts
    # copia para o servidor e o fechamento automático (sem clicar em nada) fecha o mês
    toasts.clear(); app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'])
    app._fechamento_state['ultimo']=0.0; app._fechamento_start(); assert app._fechamento_state['rodando']; assert esperar(lambda: not app._fechamento_state['rodando'])
    assert any('1 mês(es) fechado(s) de 1 empresa(s)' in t for t,_ in toasts),toasts
    fech=list((srv/'Repositório').glob('*/2026/07/Fechamento'))[0]; assert (fech/'.fechamento.json').exists() and (fech/'Fechamento 2026-07.pdf').exists()
    assert app.config_data['fechamento_estado'].get(f'{CNPJ}|2026-07')                    # a memória local evita voltar ao servidor
    # busca em andamento: o automático espera; desligado: não roda
    toasts.clear(); app._fechamento_state['ultimo']=0.0; app.sync_running=True; app._fechamento_start(); assert not app._fechamento_state['rodando']; app.sync_running=False
    app.repo_fech_var.set(False); app._fechamento_toggle(); app._fechamento_start(); assert not app._fechamento_state['rodando'] and not toasts and 'desligado' in app.repo_fech_status.cget('text'),app.repo_fech_status.cget('text')
    app.repo_fech_var.set(True); app._fechamento_toggle()
    # etiqueta "Mês fechado" e filtros
    app._repo_indice_iniciar(forcar=True); assert esperar(lambda: not app._repo_indice_rodando); app._repo_refresh_view(); esperar(lambda: app._repo_fech.get((CNPJ,'2026-07'),(0,0))[0],8); app.update()
    assert app._repo_fech[(CNPJ,'2026-07')]==(True,0),app._repo_fech
    app.repo_filtro_situacao.set('Só meses fechados'); app._repo_filtrar(salvar=False); assert len(app.repo_tree.get_children())==1
    app.repo_filtro_situacao.set('Só meses abertos'); app._repo_filtrar(salvar=False); assert len(app.repo_tree.get_children())==0
    app.repo_filtro_situacao.set('Todas'); app._repo_filtrar(salvar=False)
    # nota atrasada: revisão, com um único aviso
    c=sqlite3.connect(m.DB_PATH); c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES('n9',?,'nfe','NF-e','Saída','9','1','2026-07-30T10:00:00','5.00','Autorizado',?,?,?,?)",(CNPJ,'%044d'%9,b'<nfe n="9"/>',vista,vista)); c.commit(); c.close()
    app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando']); toasts.clear()
    app._fechamento_start(manual=True); assert esperar(lambda: not app._fechamento_state['rodando'])
    assert [t for t,_ in toasts if 'revisado' in t]==['Repositório: 1 fechamento(s) revisado(s) (chegou nota atrasada).'],toasts
    # ZIPs dos meses já salvos
    cli=Path(tempfile.mkdtemp(prefix='exato_v174_cli_')); p=cli/f'Empresa_{CNPJ}'/'2026'/'06 - Junho'/'Saída'/'NF-e'; p.mkdir(parents=True); (p/('%044d.xml'%1)).write_bytes(b'<x/>')
    app._auto_search_config()['root_folder']=str(cli); toasts.clear(); app._fechamento_zips_antigos(); assert app._fechamento_state['zips']
    assert esperar(lambda: not app._fechamento_state['zips']); assert list(cli.rglob('*.zip')) and any('ZIPs dos meses já salvos' in t for t,_ in toasts),toasts
    app.update(); print('V174 fechamento UI OK')
finally:
    try: app.destroy()
    except Exception: pass
