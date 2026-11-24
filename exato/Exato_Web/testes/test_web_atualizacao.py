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


# ------------------------------------------------------------------ atualização automática (consulta e baixa sozinho)
import hashlib, json, time
conteudo = b'MZ' + b'\0' * (21 * 1024 * 1024) + b'Inno Setup Setup Data (6.7.1)'; sha = hashlib.sha256(conteudo).hexdigest()
URL = 'https://exemplo.github.io/atualizacoes/releases/latest/download/versao.json'
class Resp:
    def __init__(self, st=200, js=None, dados=b''): self.status_code = st; self._js = js; self._d = dados
    def json(self):
        if self._js is None: raise ValueError('sem json')
        return self._js
    def iter_bytes(self, n): 
        for i in range(0, len(self._d), n): yield self._d[i:i + n]
    def __enter__(self): return self
    def __exit__(self, *a): return False
class Cli:
    def __init__(self, versao='20261125.20', arquivo=None, sha256=None, dados=conteudo, st=200, erro=None, tam=None):
        arquivo = arquivo or f'Exato_Web_Instalador_{versao}.exe'; self.js = {'versao': versao, 'arquivo': arquivo, 'sha256': sha256 or sha, 'tamanho': tam or len(conteudo), 'notas': 'Melhorias.'}; self.dados = dados; self.st = st; self.erro = erro; self.pedidos = []
    def get(self, url):
        self.pedidos.append(url)
        if self.erro: raise OSError('sem internet')
        return Resp(self.st, self.js if self.st == 200 else None)
    def stream(self, m, url):
        self.pedidos.append(url)
        if self.erro: raise OSError('sem internet')
        return Resp(self.st, None, self.dados)
i = at.consultar(URL, '20261124.11', Cli()); assert i['ok'] and i['nova'] and i['versao'] == '20261125.20' and i['url_arquivo'] == 'https://exemplo.github.io/atualizacoes/releases/latest/download/Exato_Web_Instalador_20261125.20.exe' and i['notas'] == 'Melhorias.'
i = at.consultar(URL, '20261125.20', Cli()); assert i['ok'] and not i['nova']                                   # já está na mais nova
i = at.consultar(URL, '20261126.1', Cli()); assert i['ok'] and not i['nova']                                    # a daqui é mais antiga
for kw, trecho in ((dict(st=404), 'Ainda não há'), (dict(st=500), 'Não consegui consultar'), (dict(erro=1), 'internet'), (dict(sha256='xyz'), 'não parece confiável'), (dict(arquivo='malicioso.exe'), 'não parece confiável'), (dict(tam=5), 'não parece confiável')):
    i = at.consultar(URL, '20261124.11', Cli(**kw)); assert not i['ok'] and trecho in i['erro'], (kw, i)
assert not at.consultar('http://exemplo.com/versao.json', '1', Cli())['ok']                                    # sem https não vale
# o endereço do instalador nunca vem de dentro do arquivo da consulta
c = Cli(); c.js['url'] = 'https://malicioso.example/x.exe'; assert at.consultar(URL, '1', c)['url_arquivo'].startswith('https://exemplo.github.io/')
# download: confere tamanho e impressão digital; descarta o que veio errado
d2 = Path(tempfile.mkdtemp()); info = at.consultar(URL, '20261124.11', Cli()); prog = []
arq = at.baixar(info, d2, lambda b, t: prog.append((b, t)), Cli()); assert arq.exists() and arq.name == 'Exato_Web_Instalador_20261125.20.exe' and prog and prog[-1][0] == len(conteudo)
for ruim in (conteudo[:-10], conteudo[:-1] + b'x'):
    try: at.baixar(info, d2, None, Cli(dados=ruim)); assert False
    except at.AtualizacaoErro as e: assert 'incompleto ou diferente' in str(e)
assert not list((d2 / 'atualizacao').glob('*.parcial')) and arq.exists()
try: at.baixar(info, d2, None, Cli(st=500)); assert False
except at.AtualizacaoErro as e: assert 'Não consegui baixar' in str(e)
try: at.baixar(info, d2, None, Cli(erro=1)); assert False
except at.AtualizacaoErro as e: assert 'internet' in str(e)
# memória da consulta (uma vez por dia) e aviso no menu
cfg = {}; assert at.consulta_devida(cfg); at.guardar_consulta(cfg, info); assert cfg['atualizacao']['nova'] == '20261125.20' and not at.consulta_devida(cfg)
from datetime import datetime, timedelta
assert at.consulta_devida(cfg, agora=datetime.now() + timedelta(hours=25))
at.guardar_consulta(cfg, {'ok': False, 'erro': 'x'}); assert cfg['atualizacao']['nova'] == '' and cfg['atualizacao']['erro'] == 'x'
# telas: usa a consulta do servidor falso
at.raiz_instalada = lambda raiz=None: raiz_fake; at.versao_atual = lambda raiz=None: '20261124.11'
cli = Cli(); at._http = lambda url, **kw: cli
r = adm.post('/atualizacao/verificar', data={'csrf': tk}); assert r.status_code == 303 and 'versão+nova' in r.headers['location'].replace('%20', '+') or 'nova' in r.headers['location']
t = adm.get('/atualizacao').text; assert 'Há uma versão nova: 20261125.20' in t and 'Melhorias.' in t and 'action="/atualizacao/baixar"' in t
assert 'selo-novo' in adm.get('/situacao').text and 'selo-novo' not in mar.get('/situacao').text           # o aviso "Nova" só para administrador
rodou.clear()
def baixar_(senha='SenhaForte#2026', entendi='1', cs=None): return adm.post('/atualizacao/baixar', data={'senha': senha, 'entendi': entendi, 'csrf': cs or tk})
assert baixar_(cs='errado').status_code == 303 and not rodou
assert baixar_(senha='errada').status_code == 401 and not rodou and baixar_(entendi='').status_code == 400 and not rodou
assert mar.post('/atualizacao/baixar', data={'senha': 'SenhaForte#2026', 'entendi': '1', 'csrf': tkm}).status_code == 303 and not rodou
r = baixar_(); assert r.status_code == 200 and 'Atualizando o Exato' in r.text and 'baixando.js' in r.text and '20261125.20' in r.text, r.text[:300]
for _ in range(100):
    if at.estado['fase'] in ('reiniciando', 'erro'): break
    time.sleep(0.1)
assert at.estado['fase'] == 'reiniciando' and at.estado['bytes'] == len(conteudo), at.estado
assert len(rodou) == 1 and rodou[0][2].endswith('Exato_Web_Instalador_20261125.20.exe') and Path(rodou[0][2]).exists()
a = adm.get('/atualizacao/andamento').json(); assert a['fase'] == 'reiniciando' and a['total'] == len(conteudo) and mar.get('/atualizacao/andamento').status_code == 401
# sem versão nova: recusa; internet fora: mensagem clara
cli.js['versao'] = '20261124.11'; cli.js['arquivo'] = 'Exato_Web_Instalador_20261124.11.exe'; r = baixar_(); assert r.status_code == 400 and 'já está na versão mais nova' in r.text
cli.erro = 1; r = baixar_(); assert r.status_code == 400 and 'internet' in r.text
import web.agendador as ag
print('Exato Web (atualizar pela tela e automática): OK')
