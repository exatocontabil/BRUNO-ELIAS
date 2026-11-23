"""Exato Web, fase 3 (Repositório): XMLs em arquivos organizados por empresa/ano/mês/tipo (nunca sobrescreve), cópia depois de cada rodada, tela e ZIP por mês."""
import os, sys, tempfile, io, zipfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
ARQ = Path(tempfile.mkdtemp(prefix='exato_arq_'))
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3r_'); os.environ['EXATO_WEB_ARQUIVOS'] = str(ARQ); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from ajuda_web import gerar_a1
from web import config, cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; cofre = app.state.cofre
CN = '11222333000181'; core.db_register_company(CN, 'PADARIA TESTE LTDA'); cofre.guardar(CN, gerar_a1(CN, 'sa'), 'sa')
def nfe(n, mes='09', modelo='55', entrada=False):
    k = f'4226{mes}{CN}{modelo}001{n:09d}1000001234'; outro = '99888777000166'; emit, dest = (outro, CN) if entrada else (CN, outro)
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>{modelo}</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-{mes}-10T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{emit}</CNPJ><xNome>EMIT</xNome></emit><dest><CNPJ>{dest}</CNPJ><xNome>DEST</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
docs = [{'xml': nfe(i), 'tipo': 'nfeProc', 'nsu': str(i), 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'} for i in (1, 2, 3)] + \
       [{'xml': nfe(10, entrada=True), 'tipo': 'nfeProc', 'nsu': '10', 'family': 'nfe', 'actor_code': '2', 'actor_label': 'Destinatário / Entrada'}] + \
       [{'xml': nfe(20, mes='10'), 'tipo': 'nfeProc', 'nsu': '20', 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'}]
core.db_upsert_documents(CN, docs)
# ---- cópia para os arquivos
r = motor.copiar_repositorio(); assert r['ok'] and r['novos'] == 5 and r['erros'] == 0 and r['restantes'] == 0, r
xmls = sorted(p for p in ARQ.rglob('*.xml')); assert len(xmls) == 5
rel = {str(p.relative_to(ARQ)).replace('\\', '/') for p in xmls}; assert any('/2026/' in x or '2026' in x for x in rel) and any('PADARIA' in x.upper() or CN in x for x in rel), rel
r2 = motor.copiar_repositorio(); assert r2['novos'] == 0 and r2['restantes'] == 0 and len(list(ARQ.rglob('*.xml'))) == 5          # de novo: nada duplica
primeiro = xmls[0]; antes = primeiro.read_bytes(); core.db_upsert_documents(CN, [docs[0]]); motor.copiar_repositorio(); assert primeiro.read_bytes() == antes          # nunca sobrescreve
# ---- a rodada copia sozinha ao terminar
core.db_upsert_documents(CN, [{'xml': nfe(30), 'tipo': 'nfeProc', 'nsu': '30', 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'}])
import web.busca as B
core.test_sef_nfe_webservice = lambda *a, **k: (True, 'ok', {'cstat': '137', 'motivo': 'Nenhum documento localizado', 'documents': [], 'ultNSURet': str(a[4]), 'maxNSU': str(a[4]), 'qtDfeRet': '0'})
core.test_sef_nfce_webservice = lambda *a, **k: (True, 'ok', {'cstat': '137', 'motivo': 'Nenhum documento localizado', 'documents': [], 'ultNSURet': str(a[4]), 'maxNSU': str(a[4]), 'qtDfeRet': '0'})
core.test_sef_cte_webservice = core.test_sef_nfce_webservice
core.nfse_mod_off = True
motor.nfse_transport = lambda url, thumb: (404, '{"StatusProcessamento":"NENHUM_DOCUMENTO_LOCALIZADO"}')
core_nfse = __import__('exato_nfse'); core_nfse.ADN_PAUSE_SECONDS = 0
assert motor.repo_cfg()['auto'] is False          # a cópia automática vem DESLIGADA
motor.rodada(only=[CN]); motor.aguardar_pos(); assert len(list(ARQ.rglob('*.xml'))) == 5          # a busca não copia nada para a pasta sozinha (a nota nova fica só no banco)
motor.espaco_livre = lambda: 10 * 1024 * 1024; r = motor.copiar_repositorio(); assert r['motivo'] == 'disco_cheio' and len(list(ARQ.rglob('*.xml'))) == 5 and motor.estado_repo['resultado']['motivo'] == 'disco_cheio'          # disco quase cheio: nem tenta
motor.espaco_livre = lambda: 50 * 1024 ** 3
motor.repo_cfg()['auto'] = True; motor.rodada(only=[CN]); motor.aguardar_pos(); assert len(list(ARQ.rglob('*.xml'))) == 6 and motor.estado_repo['resultado']['restantes'] == 0          # ligada: copia depois da busca
# ---- telas
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf')
for rota in ('/repositorio', f'/repositorio/zip?empresa={CN}&mes=2026-09'): assert c.get(rota).status_code == 303          # só logado
c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
pg = c.get('/repositorio').text; assert 'XMLs na pasta de arquivos' in pg and 'PADARIA' in pg and f'/repositorio/zip?empresa={CN}&amp;mes=2026-09' in pg.replace('&mes', '&amp;mes') or f'mes=2026-09' in pg
r = c.get(f'/repositorio/zip?empresa={CN}&mes=2026-09'); assert r.status_code == 303 and r.headers['location'] == f'/exportar?empresa={CN}&de=2026-09-01&ate=2026-09-30', r.headers['location']          # agora abre o formulário de exportação (ZIP com eventos)
from web import exportar as _exp
j = _exp.pedir(CN, '2026-09-01', '2026-09-30', None, '', 'organizado', '', 'teste', em_segundo_plano=False); j = _exp.ler(j['id']); assert j['estado'] == 'pronto', j
z = zipfile.ZipFile(_exp.caminho_zip(j['id'])); nomes = [n for n in z.namelist() if n.endswith('.xml')]; assert len(nomes) == 5 and any(n.startswith('NF-e/Saída/') for n in nomes) and any(n.startswith('NF-e/Entrada/') for n in nomes) and all(z.read(n).startswith(b'<?xml') for n in nomes), z.namelist()
j = _exp.pedir(CN, '2026-10-01', '2026-10-31', ['nfe'], '', 'organizado', '', 'teste', em_segundo_plano=False); j = _exp.ler(j['id']); assert j['estado'] == 'pronto' and j['notas'] == 1          # outubro: só a nota 20
assert c.get('/repositorio/zip?empresa=12&mes=2026-09').status_code == 400 and c.get(f'/repositorio/zip?empresa={CN}&mes=..%2f..').status_code == 400
assert not list(Path(config.DADOS).glob('exato_zip_*'))          # sem sobras
assert c.post('/repositorio/auto', data={'ligar': '0', 'csrf': 'falso'}).status_code == 303 and motor.repo_cfg()['auto'] is True          # sem o token, nada muda
r = c.post('/repositorio/auto', data={'ligar': '0', 'csrf': tk}); assert r.status_code == 303 and motor.repo_cfg()['auto'] is False and 'Desligada' in c.get('/repositorio').text and 'Ligar' in c.get('/repositorio').text
motor.espaco_livre = lambda: 5 * 1024 * 1024; assert 'menos de 1 GB' not in c.get('/repositorio').text; motor.copiar_repositorio(); assert 'menos de 1 GB' in c.get('/repositorio').text; motor.espaco_livre = lambda: 50 * 1024 ** 3
c.post('/repositorio/auto', data={'ligar': '1', 'csrf': tk}); assert motor.repo_cfg()['auto'] is True
assert c.post('/repositorio/copiar', data={'csrf': 'falso'}).status_code == 303
c.post('/repositorio/copiar', data={'csrf': tk}); time.sleep(.5); assert 'Copiando' in c.get('/repositorio').text or 'XMLs na pasta' in c.get('/repositorio').text
# ---- disco cheio / erro inesperado: nunca "Internal Server Error" cru
import sqlite3 as _sq, web.app as _wa
repo_mod = __import__('web.nucleo', fromlist=['x']).modulo('exato_repositorio'); orig = repo_mod.resumo
def cheio(db): raise _sq.OperationalError('database or disk is full')
repo_mod.resumo = cheio; r = c.get('/repositorio'); assert r.status_code == 200 and 'disco do computador estiver cheio' in r.text and 'Internal Server Error' not in r.text; repo_mod.resumo = orig
c2 = TestClient(app, base_url='http://testserver', follow_redirects=False, raise_server_exceptions=False); c2.get('/login'); tk2 = c2.cookies.get('exato_csrf'); c2.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk2})
def quebra(*a, **k): raise RuntimeError('falha de teste')
motor_cfg = motor.repo_cfg; motor.repo_cfg = quebra; r = c2.get('/repositorio'); motor.repo_cfg = motor_cfg
assert r.status_code == 500 and 'Algo deu errado' in r.text and 'Internal Server Error' not in r.text and 'falha de teste' not in r.text          # mensagem em português, sem vazar o erro técnico
def cheio2(*a, **k): raise OSError(28, 'No space left on device')
motor.repo_cfg = cheio2; r = c2.get('/repositorio'); motor.repo_cfg = motor_cfg; assert r.status_code == 500 and 'disco do servidor parece estar cheio' in r.text
print('Exato Web fase 3 (repositório): OK')
