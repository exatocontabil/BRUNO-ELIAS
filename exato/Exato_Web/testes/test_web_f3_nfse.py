"""Exato Web, fase 3: conferência e relatório mensal de NFS-e."""
import os, sys, tempfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3n_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from web import config, cofre as cm, relatorios as rel
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core
CN = '11222333000181'; core.db_register_company(CN, 'PADARIA TESTE LTDA')
sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from test_v190_nfse_core import nfse_xml, evento_xml, chave
pasta = Path(tempfile.mkdtemp())
for i in (1, 2, 4):          # falta a nota 3 (numeração das prestadas)
    (pasta / f'n{i}.xml').write_bytes(nfse_xml(i, prest=CN, valor='100.00', dh=f'2026-09-0{i}T10:00:00-03:00'))
(pasta / 't9.xml').write_bytes(nfse_xml(9, prest='12345678000195', toma=CN, valor='50.00', dh='2026-09-10T10:00:00-03:00'))          # tomada
dados = core.nfse_mod.read_nfse_files([str(x) for x in sorted(pasta.glob('*.xml'))], CN); core.db_upsert_nfse_items(CN, dados['items'])
from web import nfse_conferencia as nfc
c = nfc.conferir(CN); assert c['total'] == 4 and c['prestadas']['aut'] == 3 and c['tomadas']['aut'] == 1 and c['prestadas']['canc'] == 0, c
assert str(c['prestadas']['valor']) == '300.00' and c['lacunas'] == '3' and c['lacunas_total'] == 1 and any('Numeração' in a for a in c['avisos'])
assert nfc.conferir(CN, '2026-09-02', '2026-09-03')['total'] == 1
j = rel.pedir_nfse(CN, '', '', 'maria', em_segundo_plano=False); j = rel.ler(j['id']); assert j['estado'] == 'pronto' and j['total'] == 4, j
pdf = rel.caminho_pdf(j['id']); assert pdf and pdf.read_bytes()[:5] == b'%PDF-'
for ruim in ('123', ''):
    try: rel.pedir_nfse(ruim); raise SystemExit('deveria recusar')
    except rel.RelatorioErro: pass
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
cl = TestClient(app, base_url='http://testserver', follow_redirects=False); cl.get('/login'); tk = cl.cookies.get('exato_csrf')
assert cl.get('/nfse').status_code == 303
cl.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
pg = cl.get('/nfse').text; assert 'Conferência' in pg, pg[:300]
pg = cl.get(f'/nfse?empresa={CN}').text; assert 'R$ 300.00' in pg and 'faltando' in pg and 'Gerar relatório mensal' in pg
assert cl.post('/nfse/relatorio', data={'empresa': CN, 'csrf': 'falso'}).headers['location'] == '/nfse'
r = cl.post('/nfse/relatorio', data={'empresa': CN, 'csrf': tk}); assert r.headers['location'] == '/relatorios'
fim = time.time() + 20
while time.time() < fim and rel.recentes(1)[0]['estado'] == 'gerando': time.sleep(.1)
jr = rel.recentes(1)[0]; assert jr['estado'] == 'pronto' and cl.get(f"/relatorios/{jr['id']}/pdf").content[:5] == b'%PDF-'
print('Exato Web fase 3 (NFS-e): OK')
