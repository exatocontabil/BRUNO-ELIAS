"""Exato Web: atualizar pela tela (só administrador, com senha, arquivo conferido, versão, pedido ao auxiliar). O instalador de verdade NÃO é rodado."""
import io, os, re, sys, tempfile, types
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_atu_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from fastapi.testclient import TestClient
from web import atualizacao as at, config, cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; config.EXIGIR_2FA = False
core.db_auth_register_user('Admin Um', 'admin@exemplo.com.br', 'SenhaForte#2026'); core.db_auth_register_user('Maria', 'maria@exemplo.com.br', 'SenhaForte#2026')
c_ = core._auth_connect(); c_.execute("UPDATE users SET role='admin' WHERE email='admin@exemplo.com.br'"); c_.commit(); c_.close()
def cliente(email):
    c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf'); c.post('/login', data={'email': email, 'senha': 'SenhaForte#2026', 'csrf': tk}); return c, tk

# funções puras
assert at.versao_do_nome('Exato_Web_Instalador_20261124.11.exe') == '20261124.11' and at.versao_do_nome('qualquer.exe') == '' and at.versao_do_nome('../Exato_Web_Instalador_1.exe') == '1'
assert at.comparar('20261124.12', '20261124.11') == 1 and at.comparar('20261124.11', '20261124.11') == 0 and at.comparar('20261123.99', '20261124.1') == -1 and at.comparar('20261124.100', '20261124.99') == 1
def falso(nome, tam=21 * 1024 * 1024, marca=b'Inno Setup Setup Data (6.7.1)', cabeca=b'MZ'): return (nome, io.BytesIO(cabeca + b'\0' * (tam - 2) + marca), 'application/octet-stream')
d = Path(tempfile.mkdtemp())
for nome, kw, trecho in (('Exato_Web_Instalador_1.exe', dict(tam=1000), 'pequeno'), ('Exato_Web_Instalador_2.exe', dict(cabeca=b'PK'), 'instalador do Windows'), ('Exato_Web_Instalador_3.exe', dict(marca=b'nada'), 'não é um instalador do Exato'), ('programa.exe', {}, 'não parece')):
    try: at.guardar(falso(nome, **kw)[1], nome, dados=d); assert False, nome
    except at.AtualizacaoErro as e: assert trecho in str(e), (nome, str(e))
assert not list((d / 'atualizacao').glob('*.parcial'))                       # nada fica pela metade
ok = at.guardar(falso('x')[1], 'Exato_Web_Instalador_20261124.12.exe', dados=d); assert ok.exists() and ok.name == 'Exato_Web_Instalador_20261124.12.exe'
at.guardar(falso('x')[1], 'Exato_Web_Instalador_20261124.13.exe', dados=d); assert [p.name for p in (d / 'atualizacao').glob('*.exe')] == ['Exato_Web_Instalador_20261124.13.exe']          # só o último fica
# comando do auxiliar
raiz = Path(tempfile.mkdtemp()) / 'app'; raiz.mkdir(); (raiz.parent / 'python').mkdir(); (raiz.parent / 'python' / 'pythonw.exe').write_bytes(b'x'); (raiz / 'atualizar.pyw').write_text('x'); (raiz / 'endereco.txt').write_text('https://fiscal.exemplo.com\n')
assert at.raiz_instalada(raiz) == raiz.parent and at.endereco_guardado(raiz) == 'fiscal.exemplo.com'
cmd = at.comando_auxiliar('C:/x/inst.exe', raiz, d, raiz.parent); assert cmd[1].endswith('atualizar.pyw') and cmd[2] == 'C:/x/inst.exe' and cmd[5] == 'fiscal.exemplo.com' and cmd[3] == str(raiz.parent) and cmd[0].endswith('pythonw.exe')
assert at.raiz_instalada(Path(tempfile.mkdtemp()) / 'app') is None

# telas
rodou = []; at.subprocess = types.SimpleNamespace(Popen=lambda cmd, **kw: rodou.append(cmd))
at.raiz_instalada = lambda raiz=None: raiz_fake; raiz_fake = raiz.parent
at.versao_atual = lambda raiz=None: '20261124.11'
adm, tk = cliente('admin@exemplo.com.br'); mar, tkm = cliente('maria@exemplo.com.br')
assert mar.get('/atualizacao').status_code == 303 and 'Atualizar o Exato' not in mar.get('/situacao').text and 'Atualizar o Exato' in adm.get('/situacao').text          # só administrador
r = adm.get('/atualizacao'); assert r.status_code == 200 and '20261124.11' in r.text and 'name="arquivo"' in r.text
import html as _h
visivel = _h.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?s)<(script|style|svg)[^>]*>.*?</\1>', '', r.text)))
assert not re.search(r'\.bat\b|PowerShell|Python|\bSMTP\b|\bCSRF\b|\bAPI\b|banco', visivel, re.I), visivel[:400]
def enviar(c, tk, nome='Exato_Web_Instalador_20261124.12.exe', senha='SenhaForte#2026', entendi='1', repetida='', **kw):
    return c.post('/atualizacao/aplicar', data={'senha': senha, 'entendi': entendi, 'repetida': repetida, 'csrf': tk}, files={'arquivo': falso(nome, **kw)})
assert enviar(mar, tkm).status_code == 303 and not rodou                                           # não administrador
assert enviar(adm, 'errado').status_code == 303 and not rodou                                       # sem CSRF
r = enviar(adm, tk, senha='errada'); assert r.status_code == 401 and 'senha não confere' in r.text and not rodou
r = enviar(adm, tk, entendi=''); assert r.status_code == 400 and 'entendi' in r.text and not rodou
r = enviar(adm, tk, nome='Exato_Web_Instalador_20261124.11.exe'); assert r.status_code == 400 and 'mesmo assim' in r.text and not rodou          # mesma versão: pede confirmação
r = enviar(adm, tk, nome='qualquer.exe'); assert r.status_code == 400 and 'não parece' in r.text and not rodou
r = enviar(adm, tk, marca=b'nada'); assert r.status_code == 400 and not rodou
r = enviar(adm, tk); assert r.status_code == 200 and 'Atualizando o Exato' in r.text and '20261124.12' in r.text and 'restaurando.js' in r.text and len(rodou) == 1, r.text[:300]
assert rodou[0][1].endswith('atualizar.pyw') and rodou[0][2].endswith('Exato_Web_Instalador_20261124.12.exe') and rodou[0][3] == str(raiz.parent) and rodou[0][5] == ''
p = at.ultimo_pedido(); assert p['de'] == '20261124.11' and p['para'] == '20261124.12' and p['por'] == 'admin@exemplo.com.br'
rodou.clear(); r = enviar(adm, tk, nome='Exato_Web_Instalador_20261124.11.exe', repetida='1'); assert r.status_code == 200 and len(rodou) == 1          # mesma versão, com confirmação
# resultado depois da atualização
import json; (config.DADOS / at.PEDIDO).write_text(json.dumps({'arquivo': 'x', 'de': '20261124.10', 'para': '20261124.11', 'pedido_em': '2026-11-24T12:00:00', 'por': 'a'})); est, msg = at.resultado(); assert est == 'ok' and '20261124.11' in msg and '24/11' in msg
assert 'foi atualizado' in adm.get('/atualizacao').text
at.versao_atual = lambda raiz=None: '20261124.10'; assert at.resultado()[0] == 'falhou'
# instalação antiga (sem Python próprio): não atualiza por aqui
at.raiz_instalada = lambda raiz=None: None
assert 'não se atualiza por aqui' in adm.get('/atualizacao').text and enviar(adm, tk).status_code == 400
print('Exato Web (atualizar pela tela): OK')
