"""Exato Web: restaurar uma cópia de segurança pela tela (pedido + troca segura na abertura)."""
import os, re, sys, tempfile, sqlite3, zipfile, datetime, json
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_rest_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from web import backup as bk, restauracao as rs, config

def contar(dados): return sqlite3.connect(str(Path(dados) / 'nucleo' / 'central_fiscal.db')).execute('select count(*) from documents').fetchone()[0]
def novo_dados():
    d = Path(tempfile.mkdtemp(prefix='dados_')); (d / 'nucleo').mkdir(); (d / 'cofre').mkdir(); (d / 'Arquivos').mkdir(); (d / 'logs').mkdir()
    con = sqlite3.connect(str(d / 'nucleo' / 'central_fiscal.db')); con.execute('create table documents(id integer primary key, xml blob)'); con.executemany('insert into documents(xml) values (?)', [(b'<n>%d</n>' % i,) for i in range(300)]); con.commit(); con.close()
    con = sqlite3.connect(str(d / 'web.db')); con.execute('create table t(a)'); con.execute("insert into t values('original')"); con.commit(); con.close()
    (d / 'cofre' / 'chave.bin').write_bytes(b'chave-original'); (d / 'Arquivos' / 'nota.xml').write_bytes(b'x' * 100); (d / 'logs' / 'a.log').write_text('log'); return d
dados = novo_dados(); destino = Path(tempfile.mkdtemp(prefix='copias_'))
cfg = {}; c = bk.cfg_de(cfg); c.update(destino=str(destino), manter=5)
r = bk.executar(cfg, lambda: None, dados=dados, agora=datetime.datetime(2026, 11, 20, 2, 0, 5)); assert r['ok']; zip_ok = destino / r['arquivo']

# estraga os dados de hoje e restaura
con = sqlite3.connect(str(dados / 'nucleo' / 'central_fiscal.db')); con.execute('delete from documents'); con.commit(); con.close(); (dados / 'cofre' / 'chave.bin').write_bytes(b'chave-nova'); (dados / 'nucleo' / 'extra.txt').write_text('novo')
con = sqlite3.connect(str(dados / 'web.db')); con.execute("update t set a='alterado'"); con.commit(); con.close(); (dados / 'web.db-wal').write_bytes(b'sobra-do-banco-antigo')
assert contar(dados) == 0 and rs.pedido_pendente(dados) is None
rs.pedir(dados, zip_ok, por='admin@x'); assert rs.pedido_pendente(dados)['por'] == 'admin@x'
res = rs.aplicar_se_pedido(dados, agora=datetime.datetime(2026, 11, 21, 9, 0, 0)); assert res and res['ok'], res
assert contar(dados) == 300 and (dados / 'cofre' / 'chave.bin').read_bytes() == b'chave-original' and not (dados / 'nucleo' / 'extra.txt').exists()          # voltou ao que era
assert sqlite3.connect(str(dados / 'web.db')).execute('select a from t').fetchone()[0] == 'original' and not (dados / 'web.db-wal').exists()          # sem sobras do banco antigo
lado = dados / res['guardado_em']; assert contar(lado) == 0 and (lado / 'cofre' / 'chave.bin').read_bytes() == b'chave-nova' and (lado / 'nucleo' / 'extra.txt').exists() and (lado / 'web.db-wal').exists()          # o de antes ficou guardado
assert (dados / 'Arquivos' / 'nota.xml').exists() and (dados / 'logs' / 'a.log').exists() and not (dados / rs.PREPARO).exists() and rs.pedido_pendente(dados) is None          # o que se refaz não foi tocado; sem pedido pendente
assert rs.ultimo_resultado(dados)['ok'] and rs.aplicar_se_pedido(dados) is None

# cópia com banco estragado: nada muda
ruim = destino / 'ExatoWeb_backup_20261122_020000.zip'
with zipfile.ZipFile(ruim, 'w') as z: z.writestr('nucleo/central_fiscal.db', b'isto nao e um banco' * 200); z.writestr('web.db', b'x')
antes = contar(dados); rs.pedir(dados, ruim); res = rs.aplicar_se_pedido(dados); assert not res['ok'] and 'nada foi mudado' in res['msg'].lower() and contar(dados) == antes
assert not any(p.name.startswith('_antes_da_restauracao_') and not any(p.iterdir()) for p in dados.iterdir()) and not (dados / rs.PREPARO).exists() and sqlite3.connect(str(dados / 'web.db')).execute('select a from t').fetchone()[0] == 'original'
# validações do pedido
for nome, conteudo in (('ExatoWeb_backup_x.zip', None), ('qualquer.zip', 'ok'), ('ExatoWeb_backup_fuga.zip', 'fuga'), ('ExatoWeb_backup_semdados.zip', 'sem')):
    p = destino / nome
    if conteudo is None: p.write_bytes(b'nao e zip')
    else:
        with zipfile.ZipFile(p, 'w') as z:
            if conteudo == 'fuga': z.writestr('../evil.txt', 'x'); z.writestr('nucleo/a.db', b'x')
            elif conteudo == 'sem': z.writestr('cofre/a', b'x')
            else: z.writestr('nucleo/a.db', b'x')
    try: rs.pedir(dados, p); assert False, nome
    except rs.RestauracaoErro as e: assert str(e)
assert not (dados.parent / 'evil.txt').exists()
real = rs.shutil.disk_usage; rs.shutil.disk_usage = lambda p: type('U', (), {'free': 1024, 'total': 10, 'used': 0})()
try: rs.pedir(dados, zip_ok); assert False
except rs.RestauracaoErro as e: assert 'espaço' in str(e)
finally: rs.shutil.disk_usage = real

# ---- pela tela
from fastapi.testclient import TestClient
from web import cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; config.EXIGIR_2FA = False; chamou = []; app.state.reiniciar = lambda: chamou.append(1)
core.db_auth_register_user('Admin', 'a@exemplo.com.br', 'SenhaForte#2026'); core.db_auth_register_user('Maria', 'm@exemplo.com.br', 'SenhaForte#2026')
cx = core._auth_connect(); cx.execute("UPDATE users SET role='admin' WHERE email='a@exemplo.com.br'"); cx.execute("UPDATE users SET role='user' WHERE email='m@exemplo.com.br'"); cx.commit(); cx.close()
destino2 = Path(tempfile.mkdtemp(prefix='copias2_')); bk.cfg_de(motor.cfg).update(destino=str(destino2), manter=5); assert bk.executar(motor.cfg, motor.salvar_cfg)['ok']; nome = bk.listar(destino2)[0]['nome']
def entrar(email):
    cl = TestClient(app, base_url='http://testserver', follow_redirects=False); cl.get('/login'); tk = cl.cookies.get('exato_csrf'); assert cl.post('/login', data={'email': email, 'senha': 'SenhaForte#2026', 'csrf': tk}).status_code == 303; return cl, tk
adm, tk = entrar('a@exemplo.com.br'); com, tkc = entrar('m@exemplo.com.br')
assert f'/backup/restaurar?arquivo={nome}' in adm.get('/backup').text and 'Restaurar' in adm.get('/backup').text
r = adm.get('/backup/restaurar', params={'arquivo': nome}); assert r.status_code == 200 and 'O que acontece' in r.text and 'Nada é apagado' in r.text
assert adm.get('/backup/restaurar', params={'arquivo': '../x.zip'}).status_code == 303 and adm.get('/backup/restaurar', params={'arquivo': 'nao_existe.zip'}).status_code == 303
assert com.get('/backup/restaurar', params={'arquivo': nome}).status_code == 303 and com.post('/backup/restaurar', data={'arquivo': nome, 'senha': 'SenhaForte#2026', 'entendi': '1', 'csrf': tkc}).status_code == 303
assert adm.post('/backup/restaurar', data={'arquivo': nome, 'senha': 'SenhaForte#2026', 'entendi': '1', 'csrf': 'errado'}).status_code == 303
assert adm.post('/backup/restaurar', data={'arquivo': nome, 'senha': 'errada', 'entendi': '1', 'csrf': tk}).status_code == 401
assert adm.post('/backup/restaurar', data={'arquivo': nome, 'senha': 'SenhaForte#2026', 'csrf': tk}).status_code == 400          # sem marcar "entendi"
assert rs.pedido_pendente(config.DADOS) is None and not chamou
r = adm.post('/backup/restaurar', data={'arquivo': '../fora.zip', 'senha': 'SenhaForte#2026', 'entendi': '1', 'csrf': tk}); assert r.status_code == 303 and rs.pedido_pendente(config.DADOS) is None
r = adm.post('/backup/restaurar', data={'arquivo': nome, 'senha': 'SenhaForte#2026', 'entendi': '1', 'csrf': tk}); assert r.status_code == 200 and 'reiniciando' in r.text and chamou == [1]
ped = rs.pedido_pendente(config.DADOS); assert ped and Path(ped['zip']).name == nome and ped['por'] == 'a@exemplo.com.br'
(config.DADOS / rs.PEDIDO).unlink()          # o teste não reinicia o processo
app.state.reiniciar = None; r = adm.post('/backup/restaurar', data={'arquivo': nome, 'senha': 'SenhaForte#2026', 'entendi': '1', 'csrf': tk}); assert r.status_code == 200 and 'feche o Exato e abra de novo' in r.text; (config.DADOS / rs.PEDIDO).unlink()
print('Exato Web (restaurar cópia): OK')
