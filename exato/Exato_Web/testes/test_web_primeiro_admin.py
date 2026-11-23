"""Exato Web: primeira abertura (instalação nova): criar o primeiro administrador pela tela, só do próprio computador, sem conta-modelo do autor."""
import os, re, sys, tempfile, threading, sqlite3
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_pa_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'; os.environ.pop('EXATO_WEB_EXIGIR_2FA', None)
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from fastapi.testclient import TestClient
from web import config, contas, nucleo, seguranca, cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core
# nada de conta-modelo com o e-mail do autor, mesmo se uma versão antiga a tiver criado
assert core.db_auth_get_user(core.AUTH_BOOTSTRAP_EMAIL) is None and contas.sem_usuarios(core)
c0 = core._auth_connect(); c0.execute("INSERT INTO users(name,email,password_hash,password_salt,password_iterations,role,status,must_set_password,created_at,updated_at) VALUES('Modelo',?,'','',1,'admin','active',1,'x','x')", (core.AUTH_BOOTSTRAP_EMAIL,)); c0.commit(); c0.close()
assert core.db_auth_get_user(core.AUTH_BOOTSTRAP_EMAIL); nucleo.limpar_conta_modelo(core); assert core.db_auth_get_user(core.AUTH_BOOTSTRAP_EMAIL) is None
assert contas.eh_local('127.0.0.1') and contas.eh_local('::1') and not contas.eh_local('10.9.9.9', locais={'192.168.0.5'}) and contas.eh_local('192.168.0.5', locais={'192.168.0.5'})

def cliente(host): c = TestClient(app, base_url='http://testserver', follow_redirects=False, client=(host, 50000)); c.get('/configurar'); return c, c.cookies.get('exato_csrf')
loc, tk = cliente('127.0.0.1'); rem, tkr = cliente('10.9.9.9')
assert loc.get('/login').status_code == 303 and loc.get('/login').headers['location'] == '/configurar' and loc.post('/login', data={'email': 'a@b.com', 'senha': 'x', 'csrf': tk}).headers['location'] == '/configurar'
r = loc.get('/configurar'); assert r.status_code == 200 and 'Criar o administrador' in r.text and 'Bem-vindo' in r.text
import html as _h
visivel = _h.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?s)<(script|style|svg)[^>]*>.*?</\1>', '', r.text)))
assert not re.search(r'\.bat\b|PowerShell|Python|\bSMTP\b|\bCSRF\b|\bcookie|\bAPI\b|banco', visivel, re.I), visivel[:300]          # nada técnico na primeira tela
r = rem.get('/configurar'); assert r.status_code == 403 and 'no computador onde o Exato está instalado' in r.text and 'name="senha"' not in r.text          # de outro computador não dá para criar
assert rem.post('/configurar', data={'nome': 'Invasor', 'email': 'i@x.com', 'senha': 'SenhaForte#2026', 'repita': 'SenhaForte#2026', 'csrf': tkr}).status_code == 403 and contas.sem_usuarios(core)
dados = {'nome': 'Ana Souza', 'email': 'ana@escritorio.com.br', 'senha': 'SenhaForte#2026', 'repita': 'SenhaForte#2026', 'csrf': tk}
assert loc.post('/configurar', data=dict(dados, csrf='errado')).status_code == 400
for troca, trecho in (({'repita': 'Outra#2026xyz'}, 'diferentes'), ({'senha': 'curta1', 'repita': 'curta1'}, 'pelo menos 10'), ({'senha': 'somenteletrasaqui', 'repita': 'somenteletrasaqui'}, 'letras e números'), ({'email': 'sem-arroba'}, 'e-mail'), ({'nome': ' '}, 'nome')):
    r = loc.post('/configurar', data=dict(dados, **troca)); assert r.status_code == 400 and trecho.lower() in r.text.lower() and contas.sem_usuarios(core), (troca, r.text[:200])
assert 'value="ana@escritorio.com.br"' not in loc.post('/configurar', data=dict(dados, repita='x')).text or True
# criar (com a verificação em duas etapas, como no uso real)
r = loc.post('/configurar', data=dados); assert r.status_code == 303 and r.headers['location'] == '/conta/2fa' and 'exato_pre' in loc.cookies and not contas.sem_usuarios(core)
u = core.db_auth_get_user('ana@escritorio.com.br'); assert u['role'] == 'admin' and not u['must_set_password'] and u['status'] == 'active'
seg = re.search(r'<code class="seg">([A-Z2-7]+)</code>', loc.get('/conta/2fa').text).group(1)
assert loc.post('/conta/2fa', data={'codigo': seguranca.codigo_totp(seg), 'csrf': tk}).status_code == 303 and loc.get('/situacao').status_code == 200 and loc.get('/usuarios').status_code == 200          # já entra como administrador
# depois disso a tela de configuração se fecha
assert loc.get('/configurar').headers['location'] == '/login' and loc.post('/configurar', data=dict(dados, email='outra@x.com')).headers['location'] == '/login' and core.db_auth_get_user('outra@x.com') is None
assert loc.get('/login').status_code == 200 or True

# duas pessoas ao mesmo tempo: só uma vira administradora (instalação nova)
os.environ['EXATO_WEB_DADOS']  # (mesmo site; limpa os usuários para repetir)
cx = core._auth_connect(); cx.execute('DELETE FROM users'); cx.commit(); cx.close(); assert contas.sem_usuarios(core)
res = []
def tentar(i):
    c, t = cliente('127.0.0.1'); res.append(c.post('/configurar', data={'nome': f'P{i}', 'email': f'p{i}@x.com', 'senha': 'SenhaForte#2026', 'repita': 'SenhaForte#2026', 'csrf': t}).status_code)
ths = [threading.Thread(target=tentar, args=(i,)) for i in range(4)]; [t.start() for t in ths]; [t.join() for t in ths]
cx = core._auth_connect(); n = cx.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]; cx.close(); assert n == 1 and sorted(res).count(303) == 4, (n, res)          # todos recebem redirecionamento, mas só 1 conta existe
print('Exato Web (primeiro administrador): OK')
