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
motor.rodada(only=[CN]); assert len(list(ARQ.rglob('*.xml'))) == 6 and motor.estado_repo['resultado']['restantes'] == 0
# ---- telas
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf')
for rota in ('/repositorio', f'/repositorio/zip?empresa={CN}&mes=2026-09'): assert c.get(rota).status_code == 303          # só logado
c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
pg = c.get('/repositorio').text; assert 'XMLs na pasta de arquivos' in pg and 'PADARIA' in pg and f'/repositorio/zip?empresa={CN}&amp;mes=2026-09' in pg.replace('&mes', '&amp;mes') or f'mes=2026-09' in pg
r = c.get(f'/repositorio/zip?empresa={CN}&mes=2026-09'); assert r.status_code == 200 and r.content[:2] == b'PK'
z = zipfile.ZipFile(io.BytesIO(r.content)); nomes = z.namelist(); assert len(nomes) == 5 and any(n.startswith('NF-e/Saida/') for n in nomes) and any(n.startswith('NF-e/Entrada/') for n in nomes) and all(z.read(n).startswith(b'<?xml') for n in nomes), nomes
r = c.get(f'/repositorio/zip?empresa={CN}&mes=2026-10&tipo=nfe'); assert r.status_code == 200 and len(zipfile.ZipFile(io.BytesIO(r.content)).namelist()) == 1          # outubro: só a nota 20
assert c.get(f'/repositorio/zip?empresa={CN}&mes=2025-01').status_code == 404 and c.get('/repositorio/zip?empresa=12&mes=2026-09').status_code == 400 and c.get(f'/repositorio/zip?empresa={CN}&mes=..%2f..').status_code == 400
assert not list(Path(config.DADOS).glob('exato_zip_*'))          # sem sobras
assert c.post('/repositorio/copiar', data={'csrf': 'falso'}).status_code == 303
c.post('/repositorio/copiar', data={'csrf': tk}); time.sleep(.5); assert 'Copiando' in c.get('/repositorio').text or 'XMLs na pasta' in c.get('/repositorio').text
print('Exato Web fase 3 (repositório): OK')
