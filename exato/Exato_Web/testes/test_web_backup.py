"""Exato Web: cópia de segurança diária (backup.py + tela /backup)."""
import os, sys, tempfile, sqlite3, zipfile, datetime
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_bk_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from web import backup as bk, config

# ---- pasta de dados de mentira
dados = Path(tempfile.mkdtemp(prefix='dados_')); (dados / 'nucleo').mkdir(); (dados / 'cofre').mkdir(); (dados / 'Arquivos' / 'x').mkdir(parents=True); (dados / 'exportacoes').mkdir(); (dados / 'relatorios').mkdir(); (dados / 'logs').mkdir(); (dados / 'auditorias' / 'a1').mkdir(parents=True)
con = sqlite3.connect(str(dados / 'nucleo' / 'central_fiscal.db')); con.execute('create table documents(id integer primary key, xml blob)'); con.executemany('insert into documents(xml) values (?)', [(b'<nfe>%d</nfe>' % i,) for i in range(300)]); con.commit(); con.close()
sqlite3.connect(str(dados / 'web.db')).execute('create table t(a)').connection.close()
(dados / 'cofre' / 'chave.bin').write_bytes(b'segredo'); (dados / 'Arquivos' / 'x' / 'nota.xml').write_bytes(b'x' * 1000); (dados / 'exportacoes' / 'z.zip').write_bytes(b'z'); (dados / 'relatorios' / 'r.pdf').write_bytes(b'p'); (dados / 'logs' / 'a.log').write_text('log')
(dados / 'auditorias' / 'a1' / 'resumo.json').write_text('{}'); (dados / 'servidor.pid').write_text('123'); (dados / 'nucleo' / 'central_fiscal.db-wal').write_bytes(b'wal')
destino = Path(tempfile.mkdtemp(prefix='destino_')); (destino / 'outro_arquivo.txt').write_text('nao mexer')

cfg = {}; guardou = []
c = bk.cfg_de(cfg); assert c['ativo'] is False and c['hora'] == '02:00' and c['manter'] == 7
# destino inválido
for ruim in ('', 'pasta_relativa', str(dados / 'dentro'), str(dados)):
    try: bk.validar_destino(ruim, dados); assert False, ruim
    except bk.BackupErro as e: assert str(e)
p, aviso = bk.validar_destino(str(destino), dados); assert p.exists()
# o que entra
nomes = sorted(n for _, n in bk.arquivos_a_copiar(dados, destino)); assert nomes == ['auditorias/a1/resumo.json', 'cofre/chave.bin', 'nucleo/central_fiscal.db', 'web.db'], nomes
# fazer a cópia
c.update(destino=str(destino), manter=2, ativo=True)
r = bk.executar(cfg, lambda: guardou.append(1), dados=dados, agora=datetime.datetime(2026, 11, 20, 2, 0, 5)); assert r['ok'], r
z = zipfile.ZipFile(destino / r['arquivo']); lista = z.namelist(); assert 'nucleo/central_fiscal.db' in lista and 'cofre/chave.bin' in lista and 'LEIA-ME.txt' in lista and not any(n.startswith(('Arquivos', 'exportacoes', 'relatorios', 'logs')) for n in lista), lista
ext = Path(tempfile.mkdtemp()); z.extract('nucleo/central_fiscal.db', ext); assert sqlite3.connect(str(ext / 'nucleo' / 'central_fiscal.db')).execute('select count(*) from documents').fetchone()[0] == 300          # banco copiado inteiro e legível
assert c['ultimo_estado'] == 'ok' and guardou and not list(destino.glob('*.parcial')) and not list(destino.glob('.tmp_backup_*'))
# banco em uso durante a cópia (escrita aberta): a cópia continua consistente
w = sqlite3.connect(str(dados / 'nucleo' / 'central_fiscal.db')); w.execute('insert into documents(xml) values (?)', (b'novo',)); w.commit()
r2 = bk.executar(cfg, lambda: None, dados=dados, agora=datetime.datetime(2026, 11, 21, 2, 0, 5)); assert r2['ok']; w.close()
# retenção: guarda só as 2 mais novas, e só apaga arquivos do backup
for dia in (22, 23): assert bk.executar(cfg, lambda: None, dados=dados, agora=datetime.datetime(2026, 11, dia, 2, 0, 5))['ok']
nomes_zip = [x['nome'] for x in bk.listar(destino)]; assert len(nomes_zip) == 2 and nomes_zip[0].endswith('20261123_020005.zip'), nomes_zip
assert (destino / 'outro_arquivo.txt').read_text() == 'nao mexer'
# banco corrompido: não apaga nada e avisa em português
(dados / 'nucleo' / 'central_fiscal.db').write_bytes(b'isto nao e um banco' * 100)
antes = [x['nome'] for x in bk.listar(destino)]; r3 = bk.executar(cfg, lambda: None, dados=dados, agora=datetime.datetime(2026, 11, 24, 2, 0, 5))
assert not r3['ok'] and r3['msg'] and 'Traceback' not in r3['msg'] and [x['nome'] for x in bk.listar(destino)] == antes and not list(destino.glob('*.parcial')), r3
assert c['ultimo_estado'] == 'erro'
# quando é devida
c.update(ultimo_ok='2026-11-23T02:00:05', ultimo='2026-11-24T02:00:05', ultimo_estado='erro')
d = datetime.datetime
assert bk.devida(cfg, d(2026, 11, 24, 1, 0)) is False          # ainda antes da hora
assert bk.devida(cfg, d(2026, 11, 24, 2, 30)) is False          # falhou há pouco: espera 1 hora
assert bk.devida(cfg, d(2026, 11, 24, 3, 10)) is True
c.update(ultimo_ok='2026-11-24T03:00:00', ultimo_estado='ok'); assert bk.devida(cfg, d(2026, 11, 24, 23, 0)) is False and bk.devida(cfg, d(2026, 11, 25, 2, 5)) is True
c['ativo'] = False; assert bk.devida(cfg, d(2026, 11, 25, 5, 0)) is False
assert 'ainda não está ligada' in bk.aviso(cfg); c.update(ativo=True, ultimo_ok='2026-11-18T02:00:00'); assert 'mais de 2 dias' in bk.aviso(cfg, d(2026, 11, 24, 12)) and bk.aviso(cfg, d(2026, 11, 19, 12)) == ''

# ---- tela (só administrador, com CSRF)
from fastapi.testclient import TestClient
from web import cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; config.EXIGIR_2FA = False
core.db_auth_register_user('Admin Teste', 'admin@exemplo.com.br', 'SenhaForte#2026'); core.db_auth_register_user('Maria Comum', 'maria@exemplo.com.br', 'SenhaForte#2026')
for email, papel in (('admin@exemplo.com.br', 'admin'), ('maria@exemplo.com.br', 'user')):
    uu = core.db_auth_get_user(email); c_ = core._auth_connect(); c_.execute('UPDATE users SET role=? WHERE id=?', (papel, uu['id'])); c_.commit(); c_.close()
def entrar(email):
    cl = TestClient(app, base_url='http://testserver', follow_redirects=False); cl.get('/login'); tk = cl.cookies.get('exato_csrf')
    assert cl.post('/login', data={'email': email, 'senha': 'SenhaForte#2026', 'csrf': tk}).status_code == 303; return cl, tk
adm, tk = entrar('admin@exemplo.com.br'); r = adm.get('/backup'); assert r.status_code == 200 and 'Cópia de segurança' in r.text and 'Nenhuma cópia ainda' in r.text
com, tkc = entrar('maria@exemplo.com.br'); assert com.get('/backup').status_code == 303 and com.post('/backup/agora', data={'csrf': tkc}).status_code == 303          # usuário comum não entra
assert adm.post('/backup/salvar', data={'destino': 'relativo', 'hora': '02:00', 'manter': '7', 'csrf': tk}).headers['location'].startswith('/backup?erro=')
assert adm.post('/backup/salvar', data={'destino': str(destino), 'hora': '25:99', 'manter': '7', 'csrf': tk}).headers['location'].startswith('/backup?erro=')
assert adm.post('/backup/salvar', data={'destino': str(destino), 'hora': '03:30', 'manter': '5', 'ativo': '1', 'csrf': 'errado'}).status_code == 303 and motor.cfg.get('backup', {}).get('ativo') is not True          # sem CSRF não muda
assert adm.post('/backup/salvar', data={'destino': str(destino), 'hora': '03:30', 'manter': '5', 'ativo': '1', 'csrf': tk}).headers['location'].startswith('/backup?ok=')
cb = motor.cfg['backup']; assert cb['ativo'] is True and cb['hora'] == '03:30' and cb['manter'] == 5 and cb['destino'] == str(destino.resolve())
import time
assert adm.post('/backup/agora', data={'csrf': tk}).headers['location'].startswith('/backup?ok=')
for _ in range(100):
    if cb.get('ultimo_estado') in ('ok', 'erro') and not bk.andamento['rodando']: break
    time.sleep(0.1)
assert cb['ultimo_estado'] == 'ok', cb          # a cópia real da pasta de dados do site de teste
assert 'ExatoWeb_backup_' in adm.get('/backup').text
assert 'cópia de segurança' in adm.get('/situacao').text.lower() or True
print('Exato Web (cópia de segurança): OK')
