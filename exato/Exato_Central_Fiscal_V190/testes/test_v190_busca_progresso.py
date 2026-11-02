"""V184: consulta à SEFAZ com tempo máximo (travou = desiste), painel de progresso real, registro no exato.log e vigia de lentidão da tela."""
import os, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v184_prog_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as e
CN='11222333000181'
e.busca_progresso_iniciar(CN)
assert e.busca_progresso_texto().startswith('Buscando há 0 s'),e.busca_progresso_texto()
# resposta normal e retorno antecipado de 2 valores
assert e._fetch_log('NF-e',CN,'0',lambda:(True,'ok',{'cstat':'138','documents':[{'a':1},{'b':2}]}))==(True,'ok',{'cstat':'138','documents':[{'a':1},{'b':2}]})
assert e._fetch_log('NF-e',CN,'0',lambda:(False,'tempo esgotado'))==(False,'tempo esgotado',{})
assert e.BUSCA_PROGRESSO['pedidos']==2 and e.BUSCA_PROGRESSO['notas']==2
t=e.busca_progresso_texto(); assert '2 consulta(s) à SEFAZ' in t and '2 nota(s) recebida(s)' in t and 'última resposta' in t,t
# consulta que trava: desiste no tempo máximo e a busca segue (nunca fica parada para sempre)
t0=time.monotonic(); r=e._fetch_log('CT-e',CN,'0',lambda:time.sleep(30),limite=1.0); dt=time.monotonic()-t0
assert not r[0] and 'não respondeu' in r[1] and 'travou' in r[1] and r[2].get('cstat')=='' and dt<5,(r,dt)
assert e.BUSCA_PROGRESSO['sem_resposta']==1 and '1 consulta(s) sem resposta' in e.busca_progresso_texto()
# erro dentro da consulta continua sendo erro (não é engolido)
try: e._fetch_log('NF-e',CN,'0',lambda:1/0); raise SystemExit('devia propagar')
except ZeroDivisionError: pass
e.busca_progresso_fim(); assert e.busca_progresso_texto()==''
# ---- tela: painel, aviso de qual busca roda e vigia de lentidão
e.init_database(force=True)
u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); admin=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa')
e.enumerate_windows_certificates=lambda *a,**k:([],'')
app=e.App(current_user=admin); app.geometry('1366x650+0+0')
try:
    app.update(); app.selected={'Thumbprint':'AA','Subject':'X'}; app._show_webservice_test(); app.update()
    assert hasattr(app,'busca_prog_label')
    e.busca_progresso_iniciar(CN); app.sync_running=True; app.cnpj_var.set(CN)
    app._busca_prog_tick(); f=time.time()
    while time.time()-f<1.5: app.update(); time.sleep(0.05)
    assert 'Buscando há' in app.busca_prog_label.cget('text'),app.busca_prog_label.cget('text')
    assert 'busca de NF-e/NFC-e/CT-e' in app._busca_descricao()
    app.sync_running=False; f=time.time()
    while time.time()-f<2.6: app.update(); time.sleep(0.05)
    assert app.busca_prog_label.cget('text')=='','o painel deve sumir quando a busca acaba'
    # vigia: a tela "trava" por 3 s -> o log guarda o que ela fazia
    time.sleep(3.2)
    f=time.time()
    while time.time()-f<1.5: app.update(); time.sleep(0.05)
    log=(e.LOG_DIR/'exato.log').read_text(encoding='utf-8')
    assert 'Tela sem responder' in log and 'O programa estava em' in log and 'Tela voltou a responder' in log,log[-800:]
    print('busca progresso ok')
finally:
    try: app.destroy()
    except Exception: pass
# --- V184: backup 'antes da atualização' não trava mais a abertura: abrir não cria zip; depois ele é feito em segundo plano
import shutil
for z in e.BACKUP_DIR.glob('*.zip'): z.unlink()
st=e._read_data_state(); st.pop('last_backup_version',None); e._write_data_state(st)
r=e._prepare_persistent_storage(); assert not r['backup_created'] and not list(e.BACKUP_DIR.glob('Exato_Backup_*.zip')),r
assert e.backup_da_atualizacao_pendente()
p=e.fazer_backup_da_atualizacao(); assert p and Path(p).exists() and 'antes_da_atualizacao' in p and not e.backup_da_atualizacao_pendente()
assert e.fazer_backup_da_atualizacao()==''          # não repete
print('backup em segundo plano ok')
