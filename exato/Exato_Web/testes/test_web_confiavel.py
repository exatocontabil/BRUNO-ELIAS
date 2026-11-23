"""Exato Web: "confiar neste computador" (não pedir o código do celular de novo) e como ele é revogado."""
import os, re, sys, tempfile, sqlite3, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_conf_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'; os.environ.pop('EXATO_WEB_EXIGIR_2FA', None)
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from fastapi.testclient import TestClient
from web import config, cofre as cm, seguranca
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; disp = app.state.dispositivos
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); core.db_auth_register_user('Joao Teste', 'joao@exemplo.com.br', 'SenhaForte#2026')
webdb = config.DADOS / 'web.db'
def liberar_codigo():          # o mesmo código só vale uma vez: zera o "último passo" para o teste poder repetir
    c = sqlite3.connect(webdb); c.execute('UPDATE totp SET ultimo_passo=0'); c.commit(); c.close()
def novo_cliente(): c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); return c, c.cookies.get('exato_csrf')
def senha(c, tk, email='maria@exemplo.com.br'): return c.post('/login', data={'email': email, 'senha': 'SenhaForte#2026', 'csrf': tk})

# Maria ativa o código do celular
c, tk = novo_cliente(); assert senha(c, tk).headers['location'] == '/conta/2fa'
seg = re.search(r'<code class="seg">([A-Z2-7]+)</code>', c.get('/conta/2fa').text).group(1)
assert c.post('/conta/2fa', data={'codigo': seguranca.codigo_totp(seg), 'csrf': tk}).status_code == 303
c.post('/sair', data={'csrf': tk})

# sem marcar: pede o código a cada entrada
liberar_codigo(); c, tk = novo_cliente(); assert senha(c, tk).headers['location'] == '/login/codigo'
r = c.get('/login/codigo'); assert 'name="confiar"' in r.text and '30 dias' in r.text          # a opção aparece, desmarcada
r = c.post('/login/codigo', data={'codigo': seguranca.codigo_totp(seg), 'csrf': tk}); assert r.status_code == 303 and 'exato_confiavel' not in c.cookies
c.post('/sair', data={'csrf': tk}); assert senha(c, tk).headers['location'] == '/login/codigo'          # continua pedindo

# marcando "confiar": a sessão dura mais e a próxima entrada só pede a senha
liberar_codigo(); c, tk = novo_cliente(); senha(c, tk)
r = c.post('/login/codigo', data={'codigo': seguranca.codigo_totp(seg), 'confiar': '1', 'csrf': tk}); assert r.status_code == 303 and 'exato_confiavel' in c.cookies
assert 'httponly' in r.headers['set-cookie'].lower()
con = sqlite3.connect(webdb); (expira,) = con.execute('SELECT MAX(expira) FROM sessoes').fetchone(); assert expira - time.time() > 6 * 86400; assert con.execute('SELECT COUNT(*) FROM dispositivos').fetchone()[0] == 1          # sessão longa; 1 dispositivo
assert 'exato_confiavel' not in str(con.execute('SELECT id FROM dispositivos').fetchone())          # o servidor só guarda o hash
con.close()
c.post('/sair', data={'csrf': tk}); r = senha(c, tk); assert r.headers['location'] == '/situacao' and 'exato_sessao' in c.cookies          # só a senha
assert c.get('/situacao').status_code == 200

# outro computador, outro usuário ou cookie adulterado: pede o código
c2, tk2 = novo_cliente(); assert senha(c2, tk2).headers['location'] == '/login/codigo'
tok_m = disp.criar(core.db_auth_get_user('maria@exemplo.com.br')['id'], 1); assert disp.valido(tok_m, core.db_auth_get_user('maria@exemplo.com.br')['id']) and not disp.valido(tok_m, core.db_auth_get_user('joao@exemplo.com.br')['id'])          # o identificador de uma pessoa não vale para outra
c4, tk4 = novo_cliente(); c4.cookies.set('exato_confiavel', c.cookies.get('exato_confiavel')[:-3] + 'abc'); assert senha(c4, tk4).headers['location'] == '/login/codigo'          # assinatura errada
# senha errada nunca entra, mesmo em computador confiável
assert c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'errada12345', 'csrf': tk}).status_code == 401

# "sair e esquecer este computador": volta a pedir o código aqui
mid = core.db_auth_get_user('maria@exemplo.com.br')['id']; t_c = seguranca.verificar(c.cookies.get('exato_confiavel'))['t']; assert disp.valido(t_c, mid)
c.post('/sair', data={'csrf': tk, 'esquecer': '1'}); assert not disp.valido(t_c, mid)          # o identificador deste computador foi apagado no servidor
assert senha(c, tk).headers['location'] == '/login/codigo'

# trocar a senha / zerar a verificação revoga os computadores confiáveis
liberar_codigo(); c, tk = novo_cliente(); senha(c, tk); c.post('/login/codigo', data={'codigo': seguranca.codigo_totp(seg), 'confiar': '1', 'csrf': tk}); c.post('/sair', data={'csrf': tk})
assert senha(c, tk).headers['location'] == '/situacao'; c.post('/sair', data={'csrf': tk})
disp.revogar_usuario(core.db_auth_get_user('maria@exemplo.com.br')['id']); assert senha(c, tk).headers['location'] == '/login/codigo'
# vencido não vale
tok = disp.criar(core.db_auth_get_user('maria@exemplo.com.br')['id'], -1); assert disp.valido(tok, core.db_auth_get_user('maria@exemplo.com.br')['id']) is False
assert 'revogar_usuario' in (RAIZ / 'web' / 'usuarios.py').read_text(encoding='utf-8')          # CLI de trocar senha / zerar verificação também revoga
print('Exato Web (computador confiável): OK')
