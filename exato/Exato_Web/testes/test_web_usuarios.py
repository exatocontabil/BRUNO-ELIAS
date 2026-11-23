"""Exato Web: tela Usuários (criar, senha provisória, perfil, bloqueio, código do celular) e "minha senha"."""
import os, re, sys, tempfile, sqlite3
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_usr_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from urllib.parse import unquote
from fastapi.testclient import TestClient
from web import config, cofre as cm, contas
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; sessoes = app.state.sessoes; disp = app.state.dispositivos; totp = app.state.totp; config.EXIGIR_2FA = False
core.db_auth_register_user('Admin Um', 'admin@exemplo.com.br', 'SenhaForte#2026'); c_ = core._auth_connect(); c_.execute("UPDATE users SET role='admin' WHERE email='admin@exemplo.com.br'"); c_.commit(); c_.close()
def cliente(email, senha='SenhaForte#2026'):
    c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf'); r = c.post('/login', data={'email': email, 'senha': senha, 'csrf': tk}); return c, tk, r
def uid(email): return core.db_auth_get_user(email)['id']

# regras da senha
for ruim in ('curta1', '1234567890123', 'apenasletrasaqui'):
    try: contas.validar_senha_nova(ruim); assert False, ruim
    except ValueError: pass
contas.validar_senha_nova('Boa senha 2026!'); s = contas.senha_provisoria(); assert len(s) == 12 and any(x.isdigit() for x in s) and any(x.islower() for x in s) and any(x.isupper() for x in s) and not set(s) & set('lIO01')

adm, tk, r = cliente('admin@exemplo.com.br'); assert r.status_code == 303
r = adm.get('/usuarios'); assert r.status_code == 200 and 'Novo usuário' in r.text and 'Admin Um' in r.text
# a conta-modelo do programa instalado (sem senha) não aparece nem conta como administrador
assert 'brunoalbano' not in adm.get('/usuarios').text and core.db_auth_get_user('admin@exemplo.com.br')['id'] not in contas.sem_senha(core)
# criar
r = adm.post('/usuarios/novo', data={'nome': 'Maria Silva', 'email': 'maria@exemplo.com.br', 'perfil': 'user', 'csrf': tk}); assert r.status_code == 200 and 'Usuário criado' in r.text
prov = re.search(r'<code id="senha-prov" class="senha-prov">([^<]+)</code>', r.text).group(1); assert len(prov) == 12
assert 'Copiar' in r.text and prov not in adm.get('/usuarios').text          # a senha aparece uma vez só
r = adm.post('/usuarios/novo', data={'nome': 'Outra', 'email': 'maria@exemplo.com.br', 'perfil': 'user', 'csrf': tk}); assert r.status_code == 400 and 'já possui cadastro' in r.text.replace('Exato Central Fiscal', '') or r.status_code == 400
r = adm.post('/usuarios/novo', data={'nome': 'X', 'email': 'email-ruim', 'perfil': 'user', 'csrf': tk}); assert r.status_code in (400, 422) or 'inválido' in r.text
assert adm.post('/usuarios/novo', data={'nome': 'Sem csrf', 'email': 'sc@exemplo.com.br', 'perfil': 'user', 'csrf': 'errado'}).status_code == 303 and core.db_auth_get_user('sc@exemplo.com.br') is None

# primeiro acesso: senha provisória -> obrigada a trocar
mar, tkm, r = cliente('maria@exemplo.com.br', prov); assert r.status_code == 303
r = mar.get('/situacao'); assert r.status_code == 303 and r.headers['location'] == '/conta/senha'
r = mar.get('/conta/senha'); assert r.status_code == 200 and 'Escolha a sua senha' in r.text
assert mar.post('/conta/senha', data={'atual': 'errada123456', 'nova': 'Minha nova 2026', 'repita': 'Minha nova 2026', 'csrf': tkm}).status_code == 401
assert 'pelo menos 10' in mar.post('/conta/senha', data={'atual': prov, 'nova': 'curta1', 'repita': 'curta1', 'csrf': tkm}).text
assert 'diferentes' in mar.post('/conta/senha', data={'atual': prov, 'nova': 'Minha nova 2026', 'repita': 'Outra coisa 2026', 'csrf': tkm}).text
r = mar.post('/conta/senha', data={'atual': prov, 'nova': 'Minha nova 2026', 'repita': 'Minha nova 2026', 'csrf': tkm}); assert r.status_code == 303 and r.headers['location'] == '/situacao'
assert mar.get('/situacao').status_code == 200 and not core.db_auth_get_user('maria@exemplo.com.br')['must_set_password']
assert cliente('maria@exemplo.com.br', prov)[2].status_code == 401 and cliente('maria@exemplo.com.br', 'Minha nova 2026')[2].status_code == 303
# usuário comum não entra em Usuários
assert mar.get('/usuarios').status_code == 303 and mar.post(f"/usuarios/{uid('admin@exemplo.com.br')}/acao", data={'acao': 'bloquear', 'csrf': tkm}).status_code == 303 and core.db_auth_get_user('admin@exemplo.com.br')['status'] == 'active'

mid = uid('maria@exemplo.com.br'); aid = uid('admin@exemplo.com.br')
def acao(i, a): return adm.post(f'/usuarios/{i}/acao', data={'acao': a, 'csrf': tk})
# bloquear / liberar
assert acao(mid, 'bloquear').status_code == 303 and core.db_auth_get_user('maria@exemplo.com.br')['status'] == 'blocked'
assert mar.get('/situacao').status_code == 303 and cliente('maria@exemplo.com.br', 'Minha nova 2026')[2].status_code == 401          # sessão e novo acesso bloqueados
assert acao(mid, 'desbloquear').status_code == 303 and cliente('maria@exemplo.com.br', 'Minha nova 2026')[2].status_code == 303
# não bloqueia a si mesmo; único administrador não vira usuário comum
assert 'erro=' in acao(aid, 'bloquear').headers['location'] and core.db_auth_get_user('admin@exemplo.com.br')['status'] == 'active'
assert 'erro=' in unquote(acao(aid, 'tornar_usuario').headers['location']) or 'erro=' in acao(aid, 'tornar_usuario').headers['location']; assert core.db_auth_get_user('admin@exemplo.com.br')['role'] == 'admin'
# perfil
assert acao(mid, 'tornar_admin').status_code == 303 and core.db_auth_get_user('maria@exemplo.com.br')['role'] == 'admin'
assert acao(mid, 'tornar_usuario').status_code == 303 and core.db_auth_get_user('maria@exemplo.com.br')['role'] == 'user'
# código do celular e acessos
c_ = sqlite3.connect(config.DADOS / 'web.db'); c_.close(); totp.preparar(mid); assert totp.confirmar(mid, __import__('web.seguranca', fromlist=['x']).codigo_totp(totp._dec(sqlite3.connect(config.DADOS / 'web.db').execute('select segredo from totp where user_id=?', (mid,)).fetchone()[0], mid))) and totp.ativo(mid)
disp.criar(mid, 30); assert disp.contar(mid) == 1
assert acao(mid, 'zerar_codigo').status_code == 303 and not totp.ativo(mid) and disp.contar(mid) == 0
mar2, tk2, _ = cliente('maria@exemplo.com.br', 'Minha nova 2026'); assert mar2.get('/situacao').status_code == 200
assert acao(mid, 'encerrar_acessos').status_code == 303 and mar2.get('/situacao').status_code == 303
# nova senha provisória: aparece uma vez, derruba acessos e obriga a trocar
r = acao(mid, 'nova_senha'); assert r.status_code == 200 and 'Nova senha provisória' in r.text; prov2 = re.search(r'<code id="senha-prov" class="senha-prov">([^<]+)</code>', r.text).group(1)
assert core.db_auth_get_user('maria@exemplo.com.br')['must_set_password'] and cliente('maria@exemplo.com.br', 'Minha nova 2026')[2].status_code == 401
m3, tk3, r = cliente('maria@exemplo.com.br', prov2); assert r.status_code == 303 and m3.get('/situacao').headers['location'] == '/conta/senha'
# com dois administradores, um pode virar usuário comum
acao(mid, 'tornar_admin'); assert acao(mid, 'tornar_usuario').status_code == 303 and core.db_auth_get_user('maria@exemplo.com.br')['role'] == 'user'
# trocar a própria senha encerra outros acessos
outro, tko, _ = cliente('admin@exemplo.com.br'); assert outro.get('/situacao').status_code == 200
assert adm.post('/conta/senha', data={'atual': 'SenhaForte#2026', 'nova': 'Senha Nova 2027!', 'repita': 'Senha Nova 2027!', 'csrf': tk}).status_code == 303 and outro.get('/situacao').status_code == 303 and adm.get('/situacao').status_code == 200
assert 'Usuários' in adm.get('/situacao').text and 'Minha senha' in adm.get('/situacao').text
print('Exato Web (usuários): OK')
