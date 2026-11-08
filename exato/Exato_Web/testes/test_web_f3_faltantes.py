"""Exato Web, fase 3: da Auditoria para a busca. Nota do SAT sem XML na Central: o site busca só a faixa em volta dela, confere de novo sozinho e, se a SEFAZ não entrega, explica."""
import os, sys, tempfile, datetime, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3f_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from ajuda_web import gerar_a1
from web import config, auditoria as aud, cofre as cm
from web.app import criar_app
fake = cm.ImportadorFalso(); app = criar_app(importador=fake); core = app.state.core; cofre = app.state.cofre; motor = app.state.motor
sys.path.insert(0, str(config.pasta_nucleo())); import exato_xlsx
CN = '11222333000181'; core.db_register_company(CN, 'PADARIA TESTE LTDA'); cofre.guardar(CN, gerar_a1(CN, 'sa'), 'sa')
def key(n): return '42260911222333000181' + f'55001{n:09d}1000001234'
def nfe(n, valor='100.00'):
    k = key(n); return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
                        f'<emit><CNPJ>{CN}</CNPJ><xNome>PADARIA TESTE LTDA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>CLIENTE</xNome></dest><total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
core.db_upsert_documents(CN, [{'xml': nfe(n), 'tipo': 'nfeProc', 'nsu': str(n), 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'} for n in (1, 2, 3, 4, 5)])
serial = (datetime.date(2026, 9, 10) - datetime.date(1899, 12, 30)).days
def sat(caminho, numeros):
    cols = [{'title': t, 'width': 16, 'type': 'text'} for t in ('NumeroDocumento', 'DataEmissao', 'ValorTotalNota', 'ChaveAcesso', 'SerieDocumento', 'Situacao', 'TipoDocumento', 'TipoDeOperacaoEntradaOuSaida')]
    exato_xlsx.write_xlsx(caminho, [{'name': 'SAT', 'columns': cols, 'rows': [[str(n), str(serial), '100.00', key(n), '1', 'Autorizada', 'NF-e', 'Saída'] for n in numeros]}])
tmp = Path(tempfile.mkdtemp()); f = tmp / 'sat.xlsx'; sat(f, [1, 2, 3, 4, 5, 6, 7])          # 6 e 7 estão no SAT mas não têm XML na Central
res = aud.auditar(CN, [f], ['nfe'], '2026-09-01', '2026-09-30', 'maria@x.com')
assert res['sem_xml'] == 2 and len(res['faltantes']) == 2 and {i['numero'] for i in res['faltantes']} == {'6', '7'} and all(i['ator'] == '1' and i['familia'] == 'nfe' for i in res['faltantes']), res['faltantes']
# SEFAZ simulada: entrega a nota 6, mas não a 7
chamadas = []
def fake_nfe(th, c, homolog, ind, nsu, ator=3):
    chamadas.append((c, th, int(nsu), ator)); n = int(nsu)
    if n == 0: return True, 'ok', {'cstat': '138', 'motivo': 'Documento(s) localizado(s)', 'documents': [{'xml': nfe(6), 'tipo': 'nfeProc', 'nsu': '6', 'family': 'nfe'}], 'ultNSURet': '6', 'maxNSU': '6', 'qtDfeRet': '1'}
    return True, 'nada', {'cstat': '137', 'motivo': 'Nenhum documento localizado', 'documents': [], 'ultNSURet': str(n), 'maxNSU': str(n), 'qtDfeRet': '0'}
core.test_sef_nfe_webservice = fake_nfe
cfg_antes = dict(core.get_saved_nsu(motor.cfg, CN, 'nfe_emitente') and {'x': 1} or {})
ponto_antes = core.get_saved_nsu(motor.cfg, CN, 'nfe_emitente')
# ---- pelo site (em segundo plano)
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf')
assert c.post('/auditoria/' + res['id'] + '/buscar-faltantes', data={'csrf': tk}).status_code == 303 and not chamadas          # sem login: nada acontece
c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
pg = c.get('/auditoria/' + res['id']).text; assert 'Buscar só os 2 XML que faltam' in pg
c.post('/auditoria/' + res['id'] + '/buscar-faltantes', data={'csrf': 'falso'}); assert not chamadas and not motor.estado['rodando']          # CSRF
c.post('/auditoria/' + res['id'] + '/buscar-faltantes', data={'csrf': tk})
fim = time.time() + 30
while time.time() < fim and not (aud.ler(res['id']).get('busca')): time.sleep(.05)
r = aud.ler(res['id']); assert r['busca'] and not motor.estado['rodando'], r['busca']
assert '1 de 2 XML encontrado' in r['busca']['mensagem'] and '1 ainda sem XML' in r['busca']['mensagem'], r['busca']
assert chamadas and all(cn == CN and ator in (1, '1') for (cn, _t, _n, ator) in chamadas)          # só a empresa e o sentido (saída) da auditoria
assert core.get_saved_nsu(motor.cfg, CN, 'nfe_emitente') == ponto_antes          # o ponto de continuação da busca normal NÃO foi movido
assert any(e[0] == 'importar' for e in fake.eventos) and fake.eventos[-1][0] == 'remover'
# a auditoria foi refeita sozinha: 6 conciliados, a nota 7 continua sem XML e agora explica por quê
nova = aud.ler(r['busca']['nova']); assert nova and nova['conciliados'] == 6 and nova['sem_xml'] == 1, nova and (nova['conciliados'], nova['sem_xml'])
obs = [l['observacao'] for l in nova['linhas'] if l['numero'] == '7'][0]; assert 'Procurei na SEFAZ' in obs, obs
pg = c.get('/auditoria/' + res['id']).text; assert 'Busca do que faltava' in pg and 'Abrir a auditoria refeita' in pg and '/auditoria/' + nova['id'] in pg
# ---- sem certificado: mensagem clara, sem travar a trava de busca
cofre.remover(CN); chamadas.clear(); c.post('/auditoria/' + nova['id'] + '/buscar-faltantes', data={'csrf': tk}); fim = time.time() + 10
while time.time() < fim and not aud.ler(nova['id']).get('busca'): time.sleep(.05)
assert 'não tem certificado A1' in aud.ler(nova['id'])['busca']['mensagem'] and not chamadas and not motor.estado['rodando'] and motor.reservar(); motor._trava.release(); motor.estado['rodando'] = False
# ---- SEFAZ pede para esperar (117): explica em vez de insistir
cofre.guardar(CN, gerar_a1(CN, 'sa'), 'sa')
res2 = aud.auditar(CN, [f], ['nfe'], '2026-09-01', '2026-09-30'); core.record_nfe_actor_result(motor.cfg, CN, '1', '117', 'consumo indevido'); chamadas.clear()
c.post('/auditoria/' + res2['id'] + '/buscar-faltantes', data={'csrf': tk}); fim = time.time() + 10
while time.time() < fim and not aud.ler(res2['id']).get('busca'): time.sleep(.05)
m2 = aud.ler(res2['id'])['busca']['mensagem']; assert 'esperar' in m2 or 'XML encontrado' in m2, m2
print('Exato Web fase 3 (buscar o que falta): OK')
