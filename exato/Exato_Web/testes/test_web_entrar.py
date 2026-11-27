"""Exato Web: tela de entrada com "Salvar a senha neste computador" (a senha só vai para o cofre do navegador; o Exato nunca a guarda)."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_ent_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from fastapi.testclient import TestClient
from web import config, cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; config.EXIGIR_2FA = False
core.db_auth_register_user('Admin', 'admin@exemplo.com.br', 'SenhaForte#2026')
c = TestClient(app, base_url='http://testserver', follow_redirects=False)
t = c.get('/login').text
assert 'id="salvar-senha"' in t and 'Salvar a senha neste computador' in t and '/static/entrar.js' in t
assert re.search(r'id="salvar-linha"[^>]*\bhidden\b', t) and re.search(r'id="salvar-ajuda"[^>]*\bhidden\b', t)          # escondida até o navegador provar que sabe guardar
assert 'autocomplete="username"' in t and 'autocomplete="current-password"' in t                                         # o navegador reconhece os campos
assert 'o Exato nunca guarda a sua senha' in t
js = (RAIZ / 'web' / 'static' / 'entrar.js').read_text(encoding='utf-8')
assert 'PasswordCredential' in js and 'credentials.store' in js
# a senha NUNCA vai para o armazenamento da página nem para outro lugar além do cofre do navegador
assert not re.search(r'(localStorage|sessionStorage)\.setItem\([^)]*senha', js) and js.count('password:senha.value') == 1 and js.count('senha.value') == js.count('password:senha.value') + js.count("senha.value=''"), 'a senha só pode ser lida na chamada do cofre do navegador (e apagada)'
assert 'console.' not in js
if shutil.which('node'): assert subprocess.run(['node', '--check', str(RAIZ / 'web' / 'static' / 'entrar.js')], capture_output=True).returncode == 0
# o envio normal continua valendo (sem a opção marcada, ou sem JavaScript)
tk = c.cookies.get('exato_csrf'); r = c.post('/login', data={'email': 'admin@exemplo.com.br', 'senha': 'errada', 'csrf': tk}); assert r.status_code == 401 and 'E-mail ou senha inválidos' in r.text and 'aviso erro' in r.text      # o erro vem na forma que o script lê
r = c.post('/login', data={'email': 'admin@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk}); assert r.status_code == 303 and r.headers['location'] == '/situacao'
print('Exato Web (entrar / salvar a senha): OK')
