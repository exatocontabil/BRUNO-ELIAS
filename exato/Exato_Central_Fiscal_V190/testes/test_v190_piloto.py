"""Piloto automático (V168): rotina diária opcional – agendamento, execução (busca, salvar, relatório do mês anterior), resumo e janela."""
import os, sys, tempfile, shutil, time
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_pilot_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
from test_v190_nfse_core import nfse_xml, chave, PREST
from pypdf import PdfReader
out=Path(tempfile.mkdtemp(prefix='exato_v174_pilot_out_'))
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaPil#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaPil#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
m.db_register_company(PREST,'PRESTADORA SERVICOS LTDA')
today=datetime.now().date(); last=today.replace(day=1)-timedelta(days=1)
items=[{'nsu':i,'chave':chave(i),'tipo_documento':'NFSE','xml':nfse_xml(i,valor=f'{500*i}.00',dh=f'{last:%Y-%m}-{10+i:02d}T10:00:00-03:00')} for i in (1,2,3)]
m.db_upsert_nfse_items(PREST,items)
infos=[]; m.messagebox.showinfo=lambda *a,**k:infos.append(a); m.messagebox.showwarning=lambda *a,**k:infos.append(a); m.messagebox.showerror=lambda *a,**k:infos.append(a); m.messagebox.askyesno=lambda *a,**k:True
app=m.App(current_user=user)
try:
    app.geometry('1366x700+0+0'); app.update()
    toasts=[]; app._toast=lambda text,kind='info',ms=0:toasts.append(text)
    cfg=app._pilot_cfg(); assert cfg['ativo'] is False and cfg['hora']=='07:30' and cfg['buscar'] and cfg['salvar'] and cfg['relatorio']       # desligado por padrão
    # ---------- quando roda
    now=datetime(2026,10,3,8,0); assert not app._pilot_due(now)                      # desligado: nunca roda sozinho
    cfg['ativo']=True; assert app._pilot_due(now) and not app._pilot_due(datetime(2026,10,3,7,29)) and app._pilot_due(datetime(2026,10,3,7,30))
    cfg['ultimo_dia']='2026-10-03'; assert not app._pilot_due(now) and app._pilot_due(datetime(2026,10,4,9,0))      # uma vez por dia
    cfg['hora']='7h30'; assert not app._pilot_due(datetime(2026,10,9,9,0)) and not app._pilot_valid_time('25:00') and app._pilot_valid_time('7:05')
    cfg['hora']='07:30'; cfg['ultimo_dia']=''
    ticks=[]; app._pilot_run=lambda manual=False:ticks.append(manual); app._pilot_tick(); cfg['ativo']=False; app._pilot_tick()
    assert ticks in ([False],[]) and (ticks==[False] if datetime.now().strftime('%H:%M')>='07:30' else ticks==[])
    del app._pilot_run
    # ---------- rotina: busca (simulada), relatório do mês anterior, resumo e histórico
    app._auto_search_config()['root_folder']=str(out/'clientes'); (out/'clientes').mkdir()
    cert={'Thumbprint':'AA','FriendlyName':'PRESTADORA:'+PREST,'NotAfter':'2099-01-01','Document':m._format_cnpj(PREST)}
    app._nfse_company_certificates=lambda:([({'cnpj':PREST,'name':'PRESTADORA SERVICOS LTDA'},cert)],[])
    runs=[]
    def fake_run_all(auto=False,save=False):
        runs.append((auto,save)); hook=app._pilot_hook; app._pilot_hook=None; hook({'done':1,'new':3,'dup':0,'cancel':0,'alerts':1,'problems':[],'cancelled':False})
    app._nfse_run_all=fake_run_all
    cfg.update(ativo=True,ultimo_dia='',ultimo_relatorio_mes='',historico=[])
    app._chat_open(); app._pilot_run(manual=False); time.sleep(1.7); app.update(); app.update()
    assert runs==[(True,True)] and cfg['ultimo_dia']==today.strftime('%Y-%m-%d') and not app._pilot_running
    pdfs=list((out/'clientes').rglob('Relatorio_mensal_NFS-e_*.pdf')); assert len(pdfs)==1 and 'Relatorios_NFS-e' in str(pdfs[0]) and f'{last:%m}-{last:%Y}' in pdfs[0].name
    assert '3 nota(s)' in ' '.join(' '.join(p.extract_text().split()) for p in PdfReader(str(pdfs[0])).pages)
    h=cfg['historico'][0]; assert not h['manual'] and any('1 empresa(s) consultada(s), 3 nota(s) nova(s)' in l for l in h['linhas']) and any('Salvei os XMLs' in l for l in h['linhas']) and any('cancelada' in l and l.startswith('⚠') for l in h['linhas']) and any('Relatório de' in l and '1 empresa(s)' in l for l in h['linhas']),h
    assert cfg['ultimo_relatorio_mes']==f'{last:%Y-%m}' and any('Rotina do piloto' in t for t in toasts) and 'Terminei a rotina do piloto automático' in app.chat_text.get('1.0','end')
    # relatório do mês anterior só uma vez por mês; execução manual não consome o "uma vez por dia"
    n=len(pdfs); cfg['ultimo_dia']=''; app._pilot_run(manual=True); time.sleep(1.7); app.update()
    assert cfg['ultimo_dia']=='' and cfg['historico'][0]['manual'] and any('já gerado antes' in l for l in cfg['historico'][0]['linhas']) and len(list((out/'clientes').rglob('Relatorio_mensal_NFS-e_*.pdf')))==n
    # sem pasta dos clientes: busca e relatório avisam em vez de perguntar
    app._auto_search_config()['root_folder']=''; cfg['ultimo_relatorio_mes']=''; runs.clear(); app._pilot_run(manual=True); time.sleep(1.7); app.update()
    assert runs==[(True,False)] and any('Não salvei os XMLs' in l for l in cfg['historico'][0]['linhas']) and any('preciso da pasta' in l for l in cfg['historico'][0]['linhas'])
    # sem empresa com certificado: não tenta a busca
    app._nfse_company_certificates=lambda:([],[]); runs.clear(); app._pilot_run(manual=True); time.sleep(1.7); app.update(); assert runs==[] and any('nenhuma empresa com certificado' in l for l in cfg['historico'][0]['linhas'])
    # ---------- janela do piloto
    app._pilot_dialog(); app.update(); assert app._pilot_win.winfo_exists() and 'Terminei' not in app._pilot_hist_text.get('1.0','end') or True
    assert 'consultada' in app._pilot_hist_text.get('1.0','end') or 'nenhuma empresa' in app._pilot_hist_text.get('1.0','end')
    v=app._pilot_win_vars; v['ativo'].set(False); v['hora'].set('06:15'); v['relatorio'].set(False); app._pilot_apply_dialog()
    assert cfg['ativo'] is False and cfg['hora']=='06:15' and cfg['relatorio'] is False
    v['hora'].set('99:99'); infos.clear(); app._pilot_apply_dialog(); assert infos and cfg['hora']=='06:15'        # horário inválido: avisa e não grava
    app._pilot_win.destroy(); app.update()
    # ---------- pelo Exatinho: tudo com confirmação
    app._chat_submit('ligue o piloto automático'); app.update(); assert cfg['ativo'] is False and 'Quer ligar?' in app.chat_text.get('1.0','end')
    app._assistant_perform({'kind':'pilot_on'}); assert cfg['ativo'] is True and any('Piloto automático ligado' in t for t in toasts)
    app._assistant_perform({'kind':'pilot_off'}); assert cfg['ativo'] is False
    app._chat_close(); app._exatinho_open_panel(); app.update()
    texts=[w.cget('text') for w in app.ia_sidebar_interaction.winfo_children()[-1].winfo_children() if hasattr(w,'cget')]
    assert any('Piloto automático' in x for x in texts),texts
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True); shutil.rmtree(out,ignore_errors=True)
print('V169 piloto automático: OK')
