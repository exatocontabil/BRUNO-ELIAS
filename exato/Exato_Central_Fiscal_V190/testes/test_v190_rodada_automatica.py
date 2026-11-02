"""V168: rodada automática (todas as empresas, a cada 4 horas): relógio gravado, silêncio, aviso resumido, empresa nova."""
import os, sys, tempfile, shutil, time
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_rodada_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaRod#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaRod#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
EMP=[('49894842000123','ELYON LTDA'),('11222333000181','JC AUTO PECAS LTDA'),('12345678000195','TOMADORA COMERCIO LTDA')]
for c,n in EMP: m.db_register_company(c,n)
avisos=[]
def proibido(*a,**k): avisos.append(a); return False
m.messagebox.showinfo=proibido; m.messagebox.showwarning=proibido; m.messagebox.showerror=proibido; m.messagebox.askyesno=proibido
app=m.App(current_user=user)
toasts=[]; app._toast=lambda t,k='info',ms=0: toasts.append((t,k))
def esperar(cond,t=20):
    fim=time.time()+t
    while time.time()<fim:
        app.update()
        if cond(): return True
        time.sleep(.02)
    return False
try:
    app.geometry('1366x650+0+0'); app.update()
    assert m.AUTO_ROUND_HOURS==4
    # --- busca de NF-e simulada (a rede real não existe aqui) e NFS-e simulada
    visitadas=[]
    def fake_sync():
        visitadas.append(m.re.sub(r'\D','',app.cnpj_var.get())); app.sync_running=False
        cnpj=visitadas[-1]; app.after(30,lambda: app._multi_company_sync_finished(cnpj,{'ok':True}))
    app._run_sync_all=fake_sync
    app._nfse_company_certificates=lambda: ([({'cnpj':EMP[0][0],'name':EMP[0][1]},{'Thumbprint':'A'})],[{'cnpj':EMP[1][0]},{'cnpj':EMP[2][0]}])
    def fake_nfse(auto=False,save=False,quiet=False):
        hook=app._pilot_hook; app._pilot_hook=None; app.after(30,lambda: hook({'done':1,'new':2,'dup':0,'cancel':0,'alerts':0,'problems':[],'cancelled':False}))
    app._nfse_run_all=fake_nfse
    app.selected={'Thumbprint':'T','Status':'Válido','FriendlyName':'CERT JONATHA'}
    app._sync_ensure_built(); app.cnpj_var.set(EMP[1][0])           # a tela estava com esta empresa: ao fim tem de voltar para ela
    # relógio: sem rodada gravada = já passou da hora; recém-feita = só daqui a 4 h; gravada em disco
    assert app._auto_round_due_in()==0
    assert app._auto_round_start() is True
    assert esperar(lambda: not app._auto_round_active),'a rodada tem de terminar sozinha'
    assert sorted(visitadas)==sorted(c for c,_ in EMP),visitadas                   # percorreu TODAS as empresas cadastradas
    assert not avisos,avisos                                                          # em silêncio: nenhuma janela
    assert len(toasts)>=1 and 'Atualização automática concluída' in toasts[-1][0] and '3 empresa(s) em dia' in toasts[-1][0] and 'NFS-e: 2 nova(s)' in toasts[-1][0] and '2 empresa(s) sem certificado' in toasts[-1][0],toasts
    assert toasts[-1][1]=='ok' and len(toasts)==1,toasts           # um único aviso resumido
    app._auto_round_active=True; app._ia_emit_event('SYNC_SUCCESS',family='all',new_documents=1,company='X'); app.update(); assert len(toasts)==1   # durante a rodada, avisos individuais ficam em silêncio
    app._auto_round_active=False; app._ia_emit_event('SYNC_SUCCESS',family='all',new_documents=1,company='X'); app.update(); assert len(toasts)==2     # fora da rodada continuam normais
    toasts.pop()
    assert m.re.sub(r'\D','',app.cnpj_var.get())==EMP[1][0]                          # tela restaurada
    assert 14300<app._auto_round_due_in()<=14400 and app.config_data['auto_round_last']
    assert m.load_config().get('auto_round_last')==app.config_data['auto_round_last']
    # outra rodada só quando passar das 4 horas; o tique do relógio reagenda se ainda não é hora
    app.auto_sync_var.set(True); n=len(visitadas); app._auto_sync_tick(); app.update(); assert len(visitadas)==n and app._auto_job is not None
    app.config_data['auto_round_last']=(datetime.now()-timedelta(hours=5)).isoformat(timespec='seconds'); assert app._auto_round_due_in()==0
    # ocupado: não começa por cima de outra busca, tenta de novo em 5 minutos
    app.sync_running=True; app._auto_sync_tick(); assert app._auto_job is not None and not app._auto_round_active; app.sync_running=False
    # rodada que sozinha dispara quando é hora
    app._auto_sync_tick(); assert app._auto_round_active; assert esperar(lambda: not app._auto_round_active); assert len(visitadas)==2*len(EMP)
    # abrir o Exato com a opção ligada: o relógio volta sozinho (antes só voltava depois de uma busca manual)
    app._auto_job=None; app._auto_round_boot(); assert app._auto_job is not None
    app.auto_sync_var.set(False); app._auto_job=None; app._auto_round_boot(); assert app._auto_job is None
    # sem certificado selecionado: a NF-e é pulada, a NFS-e segue, um só aviso resumido
    app.selected=None; toasts.clear(); app.config_data['auto_round_last']=''
    app._auto_round_start(); assert esperar(lambda: not app._auto_round_active)
    assert len(toasts)==1 and 'Nenhum certificado válido selecionado' in toasts[0][0] and toasts[0][1]=='warn' and 'NFS-e: 2 nova(s)' in toasts[0][0],toasts
    assert not avisos
    # empresa nova: pergunta uma vez; sim = busca só dela
    iniciadas=[]; app._auto_round_start=lambda manual=False,only=None: iniciadas.append((manual,only)) or True
    app.selected={'Thumbprint':'T','Status':'Válido'}; perguntas=[]
    m.messagebox.askyesno=lambda *a,**k: perguntas.append(a) or True
    app._auto_offer_new_companies([EMP[0][0]]); assert len(perguntas)==1 and 'ELYON' in perguntas[0][1] and iniciadas==[(True,[EMP[0][0]])],(perguntas,iniciadas)
    m.messagebox.askyesno=lambda *a,**k: False; iniciadas.clear(); app._auto_offer_new_companies([EMP[1][0],EMP[2][0]]); assert not iniciadas
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 rodada automática: OK')
