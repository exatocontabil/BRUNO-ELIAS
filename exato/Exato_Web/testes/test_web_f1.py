"""Exato Web, fase 1: login com verificação em duas etapas, limite de tentativas, CSRF, cofre A1 criptografado, empresas, situação da busca e documentos."""
import os, re, sys, tempfile, datetime, sqlite3
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'chave-de-teste'
sys.path.insert(0, str(RAIZ))
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from web import config, seguranca, cofre as cofre_mod
from web.app import criar_app


def gerar_a1(cnpj, senha, dias=365, nome='EMPRESA TESTE LTDA'):
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nm = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f'{nome}:{cnpj}')]); agora = datetime.datetime.now(datetime.timezone.utc)
    cert = x509.CertificateBuilder().subject_name(nm).issuer_name(nm).public_key(chave.public_key()).serial_number(x509.random_serial_number()).not_valid_before(agora - datetime.timedelta(days=max(10, 2 - dias))).not_valid_after(agora + datetime.timedelta(days=dias)).sign(chave, hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(b'x', chave, cert, None, serialization.BestAvailableEncryption(senha.encode()))


# ---- cofre (sem site)
fake = cofre_mod.ImportadorFalso(); app = criar_app(importador=fake); cofre = app.state.cofre; core = app.state.core
CN = '11222333000181'; PFX = gerar_a1(CN, 'senha-do-a1')
info = cofre.guardar(CN, PFX, 'senha-do-a1', enviado_por='teste')
assert info['titular_cnpj'] == CN and not info['vencido'] and len(info['thumbprint']) == 40
for p in Path(config.DADOS).rglob('*'):          # nada em claro no disco
    if p.is_file() and p.suffix != '.db': b = p.read_bytes(); assert b'senha-do-a1' not in b and PFX[:40] not in b, p
for senha_ruim in ('errada', ''):
    try: cofre.guardar(CN, PFX, senha_ruim); assert False
    except cofre_mod.CofreErro as e: assert 'senha está errada' in str(e)
try: cofre.guardar(CN, b'nao e certificado', 'x'); assert False
except cofre_mod.CofreErro: pass
try: cofre.guardar(CN, gerar_a1(CN, 's', dias=-5), 's'); assert False
except cofre_mod.CofreErro as e: assert 'venceu' in str(e)
try: cofre.guardar('123', PFX, 'senha-do-a1'); assert False
except cofre_mod.CofreErro: pass
with cofre.usar(CN) as th1:
    with cofre.usar(CN) as th2: assert th1 == th2 == info['thumbprint']
    assert fake.eventos.count(('remover', th1)) == 0          # ainda em uso pelo bloco de fora
assert fake.eventos[-1] == ('remover', info['thumbprint'])
try:
    with cofre.usar(CN) as _t: raise RuntimeError('falha na consulta')
except RuntimeError: pass
assert fake.eventos[-1][0] == 'remover'          # sempre retira, mesmo com erro
try:
    with cofre.usar('99888777000166'): pass
    assert False
except cofre_mod.CofreErro as e: assert 'não tem certificado' in str(e)
assert [c['id'] for c in cofre.listar()] == [CN]
# ---- usuários
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026')
c = TestClient(app, base_url='http://testserver', follow_redirects=False)
def csrf(): c.get('/login'); return c.cookies.get('exato_csrf')
# sem login: tudo vai para o login
for rota in ('/situacao', '/empresas', '/certificados', '/documentos'): assert c.get(rota).status_code == 303 and c.get(rota).headers['location'] == '/login'
assert c.get('/saude').text == 'ok' and c.get('/openapi.json').status_code == 404 and c.get('/docs').status_code == 404
r = c.get('/login'); assert "frame-ancestors 'none'" in r.headers['content-security-policy'] and r.headers['x-frame-options'] == 'DENY'
# CSRF
assert c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': 'falso'}).status_code == 400
# senha errada (e limite de tentativas)
tk = csrf()
for i in range(5): assert c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'errada', 'csrf': tk}).status_code == 401
r = c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk}); assert r.status_code == 429 and 'Muitas tentativas' in r.text          # nem a senha certa entra bloqueado
app.state.limite.acertou('testclient', 'maria@exemplo.com.br'); app.state.limite._f.clear()
# login certo -> primeiro acesso exige ativar a verificação
r = c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk}); assert r.status_code == 303 and r.headers['location'] == '/conta/2fa' and 'exato_sessao' not in c.cookies
assert c.get('/situacao').status_code == 303          # ainda sem sessão
r = c.get('/conta/2fa'); seg = re.search(r'<code class="seg">([A-Z2-7]+)</code>', r.text).group(1)
r = c.post('/conta/2fa', data={'codigo': '000000', 'csrf': tk}); assert r.status_code == 400
r = c.post('/conta/2fa', data={'codigo': seguranca.codigo_totp(seg), 'csrf': tk}); assert r.status_code == 303 and r.headers['location'] == '/situacao' and 'exato_sessao' in c.cookies
assert c.get('/situacao').status_code == 200
# sair e entrar de novo: agora pede o código, e o mesmo código não vale duas vezes
c.post('/sair', data={'csrf': tk}); c.cookies.delete('exato_sessao')
r = c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk}); assert r.headers['location'] == '/login/codigo'
r = c.post('/login/codigo', data={'codigo': seguranca.codigo_totp(seg), 'csrf': tk}); assert r.status_code == 401          # mesmo passo já usado na ativação
import time; novo = seguranca.codigo_totp(seg, time.time() + 30)
r = c.post('/login/codigo', data={'codigo': novo, 'csrf': tk}); assert r.status_code == 303 and 'exato_sessao' in c.cookies
# ---- telas
r = c.post('/empresas', data={'cnpj': '11.222.333/0001-80', 'nome': 'ruim', 'csrf': tk}); assert 'inv' in r.headers['location']
r = c.post('/empresas', data={'cnpj': CN, 'nome': 'EMPRESA TESTE LTDA', 'csrf': tk}); assert r.status_code == 303
assert c.post('/empresas', data={'cnpj': CN, 'nome': 'x', 'csrf': 'falso'}).headers['location'].startswith('/empresas?erro')          # CSRF
assert 'EMPRESA TESTE LTDA' in c.get('/empresas').text
r = c.post('/certificados', data={'empresa': CN, 'senha': 'senha-do-a1', 'csrf': tk}, files={'arquivo': ('a1.pfx', PFX, 'application/x-pkcs12')}); assert 'ok=' in r.headers['location']
r = c.post('/certificados', data={'empresa': CN, 'senha': 'errada', 'csrf': tk}, files={'arquivo': ('a1.pfx', PFX, 'application/x-pkcs12')}); assert 'erro=' in r.headers['location']
pg = c.get('/certificados').text; assert 'Guardado' in pg or 'EMPRESA TESTE' in pg and 'senha-do-a1' not in pg
assert 'Guardado' in c.get('/empresas').text
# situação da busca e documentos
con = sqlite3.connect(str(core.DB_PATH)); agora = datetime.datetime.now().isoformat(timespec='seconds')
con.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,series,issued_at,value,status,access_key,xml,first_seen_at,last_seen_at) VALUES('d1',?,'nfe','NF-e','Saída','10','1','2026-10-10T10:00:00','150.00','Autorizado',?,?,?,?)", (CN, '4' * 44, b'<nfe>x</nfe>', agora, agora)); con.commit(); con.close()
r = c.get('/situacao'); assert r.status_code == 200 and 'EMPRESA TESTE LTDA' in r.text and 'Ainda não buscado' in r.text and 'até ' in r.text
r = c.get('/documentos'); assert 'NF-e' in r.text and '150.00' in r.text and '/documentos/d1/xml' in r.text
r = c.get('/documentos?empresa=' + CN + '&tipo=nfce'); assert '/documentos/d1/xml' not in r.text
r = c.get('/documentos/d1/xml'); assert r.status_code == 200 and r.content == b'<nfe>x</nfe>' and 'attachment' in r.headers['content-disposition']
assert c.get('/documentos/nao-existe/xml').status_code == 404
# texto inserido pelo usuário é escapado
c.post('/empresas', data={'cnpj': '45723174000110', 'nome': '<script>alert(1)</script>', 'csrf': tk}); assert '<script>alert(1)</script>' not in c.get('/empresas').text
# remover certificado
r = c.post('/certificados/remover', data={'empresa': CN, 'csrf': tk}); assert cofre.info(CN) is None and not list(Path(config.DADOS).rglob(CN + '.cof'))
print('Exato Web fase 1: OK')
