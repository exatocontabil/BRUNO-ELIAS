"""Exato Web: assistente de primeira instalação (Primeiros passos): só administrador, lê o CNPJ do certificado, empresas, cópia de segurança, primeira busca."""
import os, re, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_pp_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi.testclient import TestClient
from web import config, cofre as cm, primeiros_passos as pp
from web.app import criar_app

# funções puras
ok_ = lambda d: d in ('11222333000181', '45723174000110')
assert pp.ler_cnpjs('11.222.333/0001-81; 45723174000110\n11222333000181\nlixo 123', ok_) == (['11222333000181', '45723174000110'], ['lixo', '123'])
assert pp.nome_do_certificado('PADARIA BOA LTDA:11222333000181') == 'PADARIA BOA LTDA' and pp.nome_do_certificado('11222333000181') == '' and pp.nome_do_certificado('') == ''
cfg = {}; e = pp.estado(cfg, [], [], ''); assert e['proximo'] == 'certificado' and not e['concluido']
e = pp.estado(cfg, [1], [1], ''); assert e['proximo'] == 'copia'
cfg['primeiros_passos'] = {'pulados': ['copia']}; assert pp.estado(cfg, [1], [1], '')['proximo'] == 'busca'
cfg['primeiros_passos']['busca_feita'] = True; assert pp.estado(cfg, [1], [1], '')['concluido']

def pfx(cnpj, nome='PADARIA BOA LTDA', dias=300):
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cn = f'{nome}:{cnpj}' if cnpj else nome
    nm = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, cn)])
    cert = x509.CertificateBuilder().subject_name(nm).issuer_name(nm).public_key(chave.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc) - timedelta(days=400)).not_valid_after(datetime.now(timezone.utc) + timedelta(days=dias)).sign(chave, hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(b'x', chave, cert, None, serialization.BestAvailableEncryption(b'senha123'))

app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; config.EXIGIR_2FA = False
core.db_register_user('Admin', 'admin@exemplo.com.br', 'SenhaForte#2026') if hasattr(core, 'db_register_user') else core.db_auth_register_user('Admin', 'admin@exemplo.com.br', 'SenhaForte#2026')
core.db_auth_register_user('Maria', 'maria@exemplo.com.br', 'SenhaForte#2026')
c_ = core._auth_connect(); c_.execute("UPDATE users SET role='admin' WHERE email='admin@exemplo.com.br'"); c_.commit(); c_.close()
def cliente(email):
    c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf'); c.post('/login', data={'email': email, 'senha': 'SenhaForte#2026', 'csrf': tk}); return c, tk
adm, tk = cliente('admin@exemplo.com.br'); mar, tkm = cliente('maria@exemplo.com.br')

# instalação nova: o administrador cai no assistente (uma vez); quem não é administrador não vê nada
r = adm.get('/situacao'); assert r.status_code == 303 and r.headers['location'] == '/comecar'
assert adm.get('/situacao').status_code == 200                                  # só abre sozinho uma vez
assert mar.get('/comecar').status_code == 303 and mar.get('/comecar').headers['location'] == '/situacao' and 'Primeiros passos' not in mar.get('/situacao').text
r = adm.get('/comecar'); assert r.status_code == 200 and '1. Certificado digital' in r.text and 'Primeiros passos' in adm.get('/situacao').text
import html as _h
visivel = _h.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?s)<(script|style|svg)[^>]*>.*?</\1>', '', r.text)))
assert not re.search(r'\.bat\b|PowerShell|Python|\bSMTP\b|\bCSRF\b|\bAPI\b|banco de dados|thumbprint', visivel, re.I), visivel[:300]

def cert(c, tk, dados, senha='senha123', tipo='empresa', cnpj=''):
    return c.post('/comecar/certificado', data={'senha': senha, 'tipo': tipo, 'cnpj': cnpj, 'csrf': tk}, files={'arquivo': ('c.pfx', dados, 'application/x-pkcs12')})
assert cert(mar, tkm, pfx('11222333000181')).status_code == 303 and not cm.Cofre.listar(app.state.cofre)                       # não administrador
assert cert(adm, 'errado', pfx('11222333000181')).status_code == 303 and not app.state.cofre.listar()                           # sem CSRF
r = cert(adm, tk, pfx('11222333000181'), senha='errada'); assert r.status_code == 400 and 'senha' in r.text.lower() and not app.state.cofre.listar()
r = cert(adm, tk, pfx('11222333000181', dias=-3)); assert r.status_code == 400 and 'venceu' in r.text
r = cert(adm, tk, pfx('')); assert r.status_code == 400 and 'CNPJ' in r.text and not app.state.cofre.listar()                  # sem CNPJ no certificado: pede
r = cert(adm, tk, pfx(''), cnpj='11.222.333/0001-81'); assert r.status_code == 303 and 'guardado' in _h.unescape(r.headers['location']).replace('+', ' ')
assert [c['id'] for c in app.state.cofre.listar()] == ['11222333000181']
emp = [c for c in core.db_list_companies(50)]; assert len(emp) == 1 and re.sub(r'\D', '', emp[0]['cnpj']) == '11222333000181'     # a empresa nasceu do certificado
r = adm.get('/comecar'); assert r.status_code == 200 and '3. Cópia de segurança' in r.text                                     # certificado guardado e empresa criada por ele: pula para a cópia
assert 'Cole os' in adm.get('/comecar?passo=empresas').text
assert adm.get('/comecar?passo=certificado').text.count('vence em') >= 1
# certificado do escritório
r = cert(adm, tk, pfx('99999999000191', 'ESCRITORIO CONTABIL'), tipo='escritorio'); assert r.status_code == 303 and 'escritorio' in [c['id'] for c in app.state.cofre.listar()]
# empresas coladas
r = adm.post('/comecar/empresas', data={'texto': 'abc', 'csrf': tk}); assert r.status_code == 400 and 'nenhum CNPJ' in r.text
r = adm.post('/comecar/empresas', data={'texto': '45.723.174/0001-10\n11222333000181\nxx', 'csrf': tk}); assert r.status_code == 303
assert len(core.db_list_companies(50)) == 2                                                                                      # não duplica a que já existia
# cópia de segurança
destino = Path(tempfile.mkdtemp(prefix='copia_'))
r = adm.post('/comecar/copia', data={'destino': 'relativo', 'csrf': tk}); assert r.status_code == 400 and 'caminho completo' in r.text
r = adm.post('/comecar/copia', data={'destino': str(Path(os.environ['EXATO_WEB_DADOS']) / 'dentro'), 'csrf': tk}); assert r.status_code == 400 and 'dentro da pasta' in r.text
r = adm.post('/comecar/copia', data={'destino': str(destino), 'csrf': tk}); assert r.status_code == 303
assert str(destino) in adm.get('/comecar?passo=copia').text                                                                    # a cópia ficou ligada nessa pasta
# primeira busca
r = adm.get('/comecar'); assert r.status_code == 200 and '4. Primeira busca' in r.text and 'Buscar as notas agora' in r.text
r = adm.post('/comecar/buscar', data={'csrf': tk}); assert r.status_code == 303 and r.headers['location'] == '/situacao'
assert 'Primeiros passos' not in adm.get('/situacao').text                                                                      # concluído: some do menu
# "fazer depois" não volta a abrir sozinho; instalação que já tem empresa não ganha o assistente
adm2, tk2 = cliente('admin@exemplo.com.br'); app.state.motor.cfg['primeiros_passos'] = {}; app.state.motor.cfg.pop('backup', None)
assert adm2.get('/situacao').status_code == 200 and 'Primeiros passos' not in adm2.get('/situacao').text and app.state.motor.cfg['primeiros_passos']['concluido'] is True      # já tinha empresa e certificado
app.state.motor.cfg['primeiros_passos'] = {'concluido': False}; assert adm2.post('/comecar/pular', data={'csrf': tk2}).headers['location'] == '/situacao' and app.state.motor.cfg['primeiros_passos']['pulou'] is True
print('Exato Web (primeiros passos): OK')
