"""Exato Web: espaço em disco (medição, limpeza SEGURA só do que se refaz, aviso de disco cheio) e atualização que confere o espaço antes."""
import os, re, sys, tempfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_esp_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from web import atualizacao as at, config, cofre as cm, espaco as es
from web.app import criar_app

assert es.legivel(500) == '500 bytes' and es.legivel(2048) == '2 KB' and es.legivel(5 * 1048576) == '5,0 MB' and es.legivel(3 * 1024 ** 3) == '3,0 GB' and es.legivel(0) == '0 bytes'
assert es.situacao_disco(0) == '' and es.situacao_disco(100 * 1048576) == 'critico' and es.situacao_disco(500 * 1048576) == 'baixo' and es.situacao_disco(5 * 1024 ** 3) == ''

def montar():
    d = Path(tempfile.mkdtemp(prefix='dados_')); a = Path(tempfile.mkdtemp(prefix='copias_'))
    def f(p, tam, dias=0):
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'x' * tam)
        if dias: t = time.time() - dias * 86400; os.utime(p, (t, t))
    f(d / 'nucleo' / 'central_fiscal.db', 5000); f(d / 'web.db', 100); f(d / 'cofre' / 'a.cof', 300); f(d / 'auditorias' / 'x.json', 50); f(d / 'logs' / 'l.log', 70)
    f(d / 'atualizacao' / 'Exato_Web_Instalador_1.exe', 4000); f(d / 'atualizacao' / 'Exato_Web_Instalador_2.exe.parcial', 10); f(d / 'atualizacao' / 'outra_coisa.txt', 7)
    f(d / 'relatorios' / 'velho.pdf', 800, dias=60); f(d / 'relatorios' / 'novo.pdf', 900, dias=1); f(d / 'relatorios' / 'nota.txt', 5, dias=90)
    f(d / 'exportacoes' / 'velho.zip', 700, dias=45); f(d / 'exportacoes' / 'novo.zip', 600)
    f(d / '_antes_da_restauracao_20261101_100000' / 'nucleo' / 'db', 3000); f(d / '_antes_da_restauracao_20261101_100000' / 'cofre' / 'c', 20)
    f(a / 'Repositório' / 'Emp' / 'nf.xml', 1234)
    f(a.parent / ('fora_' + a.name + '.txt'), 9)          # arquivo FORA da pasta de dados
    return d, a
d, a = montar(); fora = a.parent / ('fora_' + a.name + '.txt')
r = es.medir(d, a); itens = {i['chave']: i for i in r['itens']}
assert itens['nucleo']['bytes'] == 5100 and itens['copias']['bytes'] == 1234 and itens['atualizacao']['bytes'] == 4017 and itens['relatorios']['bytes'] == 1705 and itens['restauracao']['bytes'] == 3020 and itens['cofre']['bytes'] == 300 and r['disco']['livre'] > 0
# limpeza: só lista branca; respeita a idade; nunca outras partes
antes = {i['chave']: i['bytes'] for i in r['itens']}
res = es.limpar(['atualizacao', 'relatorios', 'exportacoes', 'nucleo', 'cofre', 'copias', 'inexistente', '../x'], d)
assert not (d / 'atualizacao' / 'Exato_Web_Instalador_1.exe').exists() and not (d / 'atualizacao' / 'Exato_Web_Instalador_2.exe.parcial').exists() and (d / 'atualizacao' / 'outra_coisa.txt').exists()          # só instaladores
assert not (d / 'relatorios' / 'velho.pdf').exists() and (d / 'relatorios' / 'novo.pdf').exists() and (d / 'relatorios' / 'nota.txt').exists()          # só PDFs com mais de 30 dias
assert not (d / 'exportacoes' / 'velho.zip').exists() and (d / 'exportacoes' / 'novo.zip').exists()
assert (d / 'nucleo' / 'central_fiscal.db').exists() and (d / 'cofre' / 'a.cof').exists() and (a / 'Repositório' / 'Emp' / 'nf.xml').exists() and (d / 'web.db').exists() and (d / 'auditorias' / 'x.json').exists() and fora.exists()          # nada de importante
assert res['bytes'] == 4000 + 10 + 800 + 700 and res['arquivos'] == 4 and set(res['por_parte']) == {'atualizacao', 'relatorios', 'exportacoes'}, res
res = es.limpar(['restauracao'], d); assert not list(d.glob('_antes_da_restauracao_*')) and res['bytes'] == 3020 and (d / 'nucleo' / 'central_fiscal.db').exists() and d.exists()
# atalho (link) nunca é seguido
d2, a2 = montar(); alvo = Path(tempfile.mkdtemp(prefix='alvo_')); (alvo / 'precioso.txt').write_text('importante')
import shutil; shutil.rmtree(d2 / '_antes_da_restauracao_20261101_100000'); os.symlink(alvo, d2 / '_antes_da_restauracao_20261102_100000', target_is_directory=True)
es.limpar(['restauracao'], d2); assert (alvo / 'precioso.txt').read_text() == 'importante'
# medição em segundo plano
es.medicao.update(fim='', rodando=False); assert es.medir_em_segundo_plano(d, a, forcar=True)
for _ in range(100):
    if not es.medicao['rodando']: break
    time.sleep(0.05)
assert es.medicao['itens'] and es.medicao['fim'] and not es.medir_em_segundo_plano(d, a)                   # reaproveita a medida recente

# atualização: confere o espaço antes de baixar
try: at.garantir_espaco(d, 10 ** 18); assert False
except at.AtualizacaoErro as e: assert 'Falta espaço' in str(e) and 'Espaço em disco' in str(e)
at.garantir_espaco(d, 1)

# telas
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; config.EXIGIR_2FA = False
app.state.motor.cfg['primeiros_passos'] = {'concluido': True}
core.db_auth_register_user('Admin', 'admin@exemplo.com.br', 'SenhaForte#2026'); core.db_auth_register_user('Maria', 'maria@exemplo.com.br', 'SenhaForte#2026')
c_ = core._auth_connect(); c_.execute("UPDATE users SET role='admin' WHERE email='admin@exemplo.com.br'"); c_.commit(); c_.close()
def cliente(email):
    c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf'); c.post('/login', data={'email': email, 'senha': 'SenhaForte#2026', 'csrf': tk}); return c, tk
adm, tk = cliente('admin@exemplo.com.br'); mar, tkm = cliente('maria@exemplo.com.br')
assert mar.get('/espaco').status_code == 303 and 'Espaço em disco' not in mar.get('/situacao').text and 'Espaço em disco' in adm.get('/situacao').text
es.medicao.update(fim='', rodando=False)
r = adm.get('/espaco'); assert r.status_code == 200 and 'Espaço em disco' in r.text and 'livres' in r.text
for _ in range(100):
    if not es.medicao['rodando']: break
    time.sleep(0.05)
r = adm.get('/espaco'); assert 'Empresas e notas' in r.text and 'Cópias dos XMLs' in r.text and 'Limpar o que se refaz sozinho' in r.text
import html as _h
visivel = _h.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'(?s)<(script|style|svg)[^>]*>.*?</\1>', '', r.text)))
assert not re.search(r'\.bat\b|PowerShell|Python|\bSMTP\b|\bCSRF\b|\bAPI\b|banco de dados|SQLite', visivel, re.I), visivel[:400]
# limpar pela tela: só administrador, com CSRF, com confirmação, só partes válidas
dados_reais = config.DADOS; (dados_reais / 'atualizacao').mkdir(exist_ok=True); inst = dados_reais / 'atualizacao' / 'Exato_Web_Instalador_9.exe'; inst.write_bytes(b'x' * 100)
assert mar.post('/espaco/limpar', data={'partes': ['atualizacao'], 'entendi': '1', 'csrf': tkm}).headers['location'] == '/situacao' and inst.exists()
assert adm.post('/espaco/limpar', data={'partes': ['atualizacao'], 'entendi': '1', 'csrf': 'errado'}).headers['location'] == '/espaco' and inst.exists()
from urllib.parse import unquote_plus
assert 'Marque o que' in unquote_plus(adm.post('/espaco/limpar', data={'partes': ['nucleo', 'cofre'], 'entendi': '1', 'csrf': tk}).headers['location']) and (config.DADOS / 'nucleo').exists()          # parte proibida: nada
assert 'confirmando' in unquote_plus(adm.post('/espaco/limpar', data={'partes': ['atualizacao'], 'csrf': tk}).headers['location']) and inst.exists()
r = adm.post('/espaco/limpar', data={'partes': ['atualizacao'], 'entendi': '1', 'csrf': tk}); assert r.status_code == 303 and 'liberados' in unquote_plus(r.headers['location']) and not inst.exists()
# aviso de disco cheio no menu (só administrador)
import types; real = es.disco_de
es.disco_de = lambda p: {'total': 100 * 1024 ** 3, 'usado': 100 * 1024 ** 3 - 200 * 1048576, 'livre': 200 * 1048576}
t = adm.get('/situacao').text; assert 'quase cheio' in t and 'Cheio' in t and 'quase cheio' not in mar.get('/situacao').text
es.disco_de = real
print('Exato Web (espaço em disco): OK')
