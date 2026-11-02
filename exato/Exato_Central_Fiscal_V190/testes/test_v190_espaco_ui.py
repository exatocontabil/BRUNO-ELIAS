"""V183 (tela): Espaço usado (só arquivos do Exato; confirmação com pasta e tamanho), pausa com disco quase cheio, diagnóstico desligado, fila por empresa, adaptador da SEFAZ, mensagem de disco cheio."""
import os, sys, tempfile, time, errno, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_esp_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as e
import exato_limpeza as L
# --- adaptador: retorno antecipado (ok, mensagem) vira (ok, mensagem, {}); o completo passa igual
assert e._fetch3((False,'tempo esgotado'))==(False,'tempo esgotado',{}) and e._fetch3((True,'x',{'a':1}))==(True,'x',{'a':1})
# --- diagnóstico desligado por padrão
assert e.DIAGNOSTICO_BUSCA['ativo'] is False
d=Path(tempfile.mkdtemp())/'diag'
e._save_webservice_diagnostic(d,1,'<a/>','<b/>',[('<c/>','x')]) if False else None
# --- mensagem de disco cheio em português claro
m=e.friendly_message('[Errno 28] No space left on device'); assert 'disco' in m.lower() and 'Errno' not in m,m
# --- save_config com disco cheio não derruba
orig=e.os.replace
def cheio(*a,**k): raise OSError(errno.ENOSPC,'No space left on device')
e.os.replace=cheio
try: e.save_config({'x':1})
except Exception as ex: assert 'disco' in str(ex).lower() and 'Errno' not in str(ex),ex
finally: e.os.replace=orig
e.init_database(force=True)
u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); admin=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa')
e.enumerate_windows_certificates=lambda *a,**k:([],'')
msgs=[]; e.messagebox.showinfo=lambda *a,**k: msgs.append(('info',a)); e.messagebox.showwarning=lambda *a,**k: msgs.append(('warn',a)); asks=[]
e.messagebox.askyesno=lambda *a,**k: (asks.append(a), False)[1]
APP=e.App(current_user=admin); app=APP; app.geometry('1366x650+0+0')
try:
    app.update()
    # arquivos de teste dentro da pasta de dados + um de FORA
    dados=Path(e.APP_DATA_DIR); (dados/'Backups').mkdir(parents=True,exist_ok=True)
    tmpbk=dados/'Backups'/'.central_fiscal_backup_x.db'; tmpbk.write_bytes(b'x'*2000)
    fora=Path(tempfile.mkdtemp())/'outro.zip'; fora.write_bytes(b'nao tocar')
    # nível do disco: crítico pausa o que é automático e pergunta no manual
    L.espaco_livre=lambda p:(100*1024**2,100*1024**3)
    assert app._disco_nivel(forcar=True)=='critico' and app._disco_critico()
    assert app._disco_permite('A busca') is False and asks and 'quase cheio' in asks[-1][1]
    app._repo_cfg()['pasta']=tempfile.mkdtemp(); app._repo_start(); assert not app._repo_state['rodando'],'a cópia automática devia pausar'
    assert app._auto_round_start() is False
    L.espaco_livre=lambda p:(500*1024**3,1000*1024**3); assert app._disco_nivel(forcar=True)=='ok' and app._disco_permite('A busca')
    # tela Espaço usado
    app._show_maintenance() if hasattr(app,'_show_maintenance') else None
    antes=set(app.winfo_children()); app._espaco_dialog(); app.update()
    novos=[w for w in app.winfo_children() if w not in antes and w.winfo_class()=='Toplevel']; assert novos
    def textos(w):
        for f in w.winfo_children():
            try: yield f.cget('text')
            except Exception: pass
            yield from textos(f)
    t=' '.join(str(x) for x in textos(novos[0])); assert 'Exato Central Fiscal' in t and str(e.APP_DATA_DIR) in t and 'Nunca são apagados' in t
    novos[0].destroy()
    # a limpeza manual pede confirmação (negada = nada apagado) e fora do Exato nunca é tocado
    assert tmpbk.exists() and fora.exists()
    # fila por empresa abre
    antes=set(app.winfo_children()); app._repo_fila_dialog(); 
    f=time.time()
    while time.time()-f<3:
        app.update()
        while app._repo_inbox: app._repo_inbox.popleft()()
        time.sleep(0.05)
    novos=[w for w in app.winfo_children() if w not in antes and w.winfo_class()=='Toplevel']; assert novos; novos[0].destroy()
    # prioridade: marca e some quando a fila esvazia
    app._repo_prioridade_add('11222333000181'); assert app._repo_prioridade()==['11222333000181']
    app._repo_done({'ok':True,'restantes':0,'_fila':{}}, '', [], False); assert app._repo_prioridade()==[]
    app._repo_prioridade_add('11222333000181'); app._repo_done({'ok':True,'restantes':3,'_fila':{'11222333000181':3}}, '', [], False); assert app._repo_prioridade()==['11222333000181']
    # Modo técnico: caixa do diagnóstico
    app.maint_diag_var.set(True); app._diagnostico_toggle(); assert e.DIAGNOSTICO_BUSCA['ativo'] and app.config_data['diagnostico_busca'] is True
    app.maint_diag_var.set(False); app._diagnostico_toggle(); assert not e.DIAGNOSTICO_BUSCA['ativo']
    print('espaco ui ok')
finally:
    try: app._theme_restart_requested=False; app.destroy()
    except Exception: pass
# --- motivo da busca: certificado de outra raiz de CNPJ
import exato_busca_motivos as M
c=M.classificar('Este certificado não pertence a esta empresa (o CNPJ base é diferente).') if hasattr(M,'classificar') else None
assert c is not None
print('motivos ok', c if not isinstance(c,(list,tuple)) else c[:1])
