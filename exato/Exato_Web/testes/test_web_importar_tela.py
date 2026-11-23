"""Exato Web: importar do Exato Central Fiscal pela tela (pasta ou cópia .zip), sem duplicar, sem alterar a origem."""
import os, re, sys, tempfile, subprocess, zipfile, time, sqlite3, hashlib
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_imp_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from fastapi.testclient import TestClient
from web import config, importar, backup as bk, nucleo, cofre as cm
from web.app import criar_app
CORE_DIR = config.pasta_nucleo(); A, B = '11222333000181', '45723174000110'
ORIGEM = Path(tempfile.mkdtemp(prefix='exato_orig_'))
codigo = f'''
import sys
sys.path.insert(0, r"{CORE_DIR}"); sys.path.insert(0, r"{CORE_DIR}/third_party")
import exato_central_fiscal as m
m.init_database()
def nfe(cn, n):
    k = f"4226{{10}}{{cn}}55001{{n:09d}}1000001234"
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{{k}}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{{n}}</nNF><dhEmi>2026-11-0{{1 + n % 8}}T10:00:00-03:00</dhEmi></ide><emit><CNPJ>{{cn}}</CNPJ><xNome>EMPRESA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>CLIENTE</xNome></dest><total><ICMSTot><vNF>{{100 + n}}.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{{k}}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
for cn, nm in (("{A}", "ALFA LTDA"), ("{B}", "BETA LTDA")):
    m.db_register_company(cn, nm)
    m.db_upsert_documents(cn, [{{"xml": nfe(cn, i), "tipo": "nfeProc", "nsu": str(i), "family": "nfe", "actor_code": "1", "actor_label": "Emitente / Saída"}} for i in range(1, 31)])
'''
subprocess.run([sys.executable, '-c', codigo], env=dict(os.environ, EXATO_DATA_DIR=str(ORIGEM)), check=True)
assert (ORIGEM / 'central_fiscal.db').exists(); hash_antes = hashlib.sha256((ORIGEM / 'central_fiscal.db').read_bytes()).hexdigest()

# conferência da origem e detecção
for ruim in ('', 'relativo', str(Path(tempfile.mkdtemp())), str(Path(__file__))):
    try: importar.analisar(ruim); assert False, ruim
    except ValueError as e: assert str(e)
assert importar.analisar(str(ORIGEM))['tipo'] == 'pasta'
cand = importar.candidatos([ORIGEM, Path('/nao/existe')]); assert len(cand) == 1 and cand[0]['caminho'] == str(ORIGEM) and cand[0]['mb'] >= 0
zdir = Path(tempfile.mkdtemp()); zpath = zdir / 'copia_PC01.zip'
with zipfile.ZipFile(zpath, 'w') as z: z.write(ORIGEM / 'central_fiscal.db', 'Dados/central_fiscal.db')
assert importar.analisar(str(zpath))['tipo'] == 'zip'; vazio = zdir / 'vazio.zip'
with zipfile.ZipFile(vazio, 'w') as z: z.writestr('a.txt', 'x')
try: importar.analisar(str(vazio)); assert False
except ValueError as e: assert 'não tem os dados' in str(e)
l = bk.listar_pastas(str(zdir), zips=True); assert [x['nome'] for x in l['arquivos']] == ['copia_PC01.zip', 'vazio.zip'] and 'arquivos' not in bk.listar_pastas(str(zdir))

app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; config.EXIGIR_2FA = False
core.db_auth_register_user('Admin', 'a@exemplo.com.br', 'SenhaForte#2026'); core.db_auth_register_user('Maria', 'm@exemplo.com.br', 'SenhaForte#2026')
cx = core._auth_connect(); cx.execute("UPDATE users SET role='admin' WHERE email='a@exemplo.com.br'"); cx.execute("UPDATE users SET role='user' WHERE email='m@exemplo.com.br'"); cx.commit(); cx.close()
def entrar(email):
    c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf'); assert c.post('/login', data={'email': email, 'senha': 'SenhaForte#2026', 'csrf': tk}).status_code == 303; return c, tk
adm, tk = entrar('a@exemplo.com.br'); com, tkc = entrar('m@exemplo.com.br')
def esperar():
    for _ in range(300):
        if not motor.estado_importar['rodando']: return
        time.sleep(0.1)
    assert False, 'importação demorou'
def n(t): c = sqlite3.connect(str(core.DB_PATH)); v = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]; c.close(); return v
r = adm.get('/importar'); assert r.status_code == 200 and 'Importar do Exato Central Fiscal' in r.text and 'Procurar...' in r.text
assert com.get('/importar').status_code == 303 and com.post('/importar/iniciar', data={'origem': str(ORIGEM), 'csrf': tkc}).status_code == 303 and n('documents') == 0
assert adm.post('/importar/iniciar', data={'origem': str(ORIGEM), 'csrf': 'errado'}).status_code == 303 and n('documents') == 0
assert 'erro=' in adm.post('/importar/iniciar', data={'origem': 'relativo', 'csrf': tk}).headers['location'] and 'erro=' in adm.post('/importar/iniciar', data={'origem': str(vazio), 'csrf': tk}).headers['location']
# não começa durante uma busca
assert motor.reservar(); assert 'erro=' in adm.post('/importar/iniciar', data={'origem': str(ORIGEM), 'csrf': tk}).headers['location'] and n('documents') == 0; motor._trava.release(); motor.estado['rodando'] = False
# com cópia de segurança antes
destino = Path(tempfile.mkdtemp(prefix='copias_')); bk.cfg_de(motor.cfg).update(destino=str(destino), manter=3)
r = adm.post('/importar/iniciar', data={'origem': str(ORIGEM), 'antes': '1', 'csrf': tk}); assert 'ok=' in r.headers['location']; esperar()
st = motor.estado_importar; assert not st['erro'] and any('Empresas: 2 nova(s) de 2' in x for x in st['linhas']) and any('Notas: 60 nova(s) de 60' in x for x in st['linhas']), st
assert n('documents') == 60 and n('companies') == 2 and len(bk.listar(destino)) == 1          # a cópia de segurança foi feita antes
assert hashlib.sha256((ORIGEM / 'central_fiscal.db').read_bytes()).hexdigest() == hash_antes          # a origem não foi alterada
t = adm.get('/importar').text; assert 'Importação concluída' in t and 'Empresas: 2 nova(s) de 2' in t
# de novo e por cópia .zip: nada duplica
assert 'ok=' in adm.post('/importar/iniciar', data={'origem': str(zpath), 'csrf': tk}).headers['location']; esperar()
assert not motor.estado_importar['erro'] and any('Notas: 0 nova(s) de 60' in x for x in motor.estado_importar['linhas']) and n('documents') == 60
assert not motor.estado['rodando'] and motor.reservar(); motor._trava.release(); motor.estado['rodando'] = False          # a trava da rodada foi devolvida
print('Exato Web (importar pela tela): OK')
