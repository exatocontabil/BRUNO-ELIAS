"""Exato Web, fase 3 (busca manual): tipos escolhidos e recomeçar do zero. Base da fase 2: busca no servidor com os certificados do cofre (SEFAZ e Emissor Nacional simulados): NF-e/NFC-e/CT-e e NFS-e, certificado da empresa x do escritório
(procuração), pontos de continuação, espera da SEFAZ, recusas explicadas, agendador e telas de busca."""
import os, sys, tempfile, json, time, datetime, sqlite3
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3b_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'chave-de-teste'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from ajuda_web import gerar_a1
from web import config as _cfg; sys.path.insert(0, str(_cfg.pasta_nucleo().parent / 'testes'))          # XMLs de NFS-e de exemplo do programa instalado
from fastapi.testclient import TestClient
from web import cofre as cofre_mod, seguranca
from web.app import criar_app

A, B, C = '11222333000181', '45723174000110', '11444777000161'          # A: A1 próprio • B: usa o A1 do escritório • C: sem certificado
ESC = '12345678000195'
fake = cofre_mod.ImportadorFalso()
import web.nucleo as nucleo
chamadas_nfse = []
def transporte_nfse(url, thumb):
    cn = url.split('cnpjConsulta=')[1] if 'cnpjConsulta=' in url else ''; chamadas_nfse.append((cn, thumb)); nsu = int(url.split('/DFe/')[1].split('?')[0])
    from test_v190_nfse_core import nfse_xml, chave, pack
    if cn == C or (cn == B and thumb != THUMB_ESC): return 400, json.dumps({'Erros': [{'Descricao': 'CNPJ base diferente'}]})
    if nsu == 0: return 200, json.dumps({'StatusProcessamento': 'DOCUMENTOS_LOCALIZADOS', 'LoteDFe': [{'NSU': 1, 'ChaveAcesso': chave(7 if cn == A else 8), 'TipoDocumento': 'NFSE', 'ArquivoXml': pack(nfse_xml(7 if cn == A else 8, prest=cn))}]})
    return 404, json.dumps({'StatusProcessamento': 'NENHUM_DOCUMENTO_LOCALIZADO'})
app = criar_app(importador=fake, nfse_transport=transporte_nfse); core = app.state.core; cofre = app.state.cofre; motor = app.state.motor; agendador = app.state.agendador
core.nfse_mod.ADN_PAUSE_SECONDS = 0
for cn, nm in ((A, 'ALFA LTDA'), (B, 'BETA LTDA'), (C, 'GAMA LTDA')): core.db_register_company(cn, nm)
cofre.guardar(A, gerar_a1(A, 'sa'), 'sa'); cofre.guardar('escritorio', gerar_a1(ESC, 'se', nome='ESCRITORIO CONTABIL'), 'se')
THUMB_ESC = cofre.info('escritorio')['thumbprint']; THUMB_A = cofre.info(A)['thumbprint']
assert motor.certificado_para(A) == A and motor.certificado_para(B) == 'escritorio' and motor.certificado_para(C) == 'escritorio'
cofre.remover('escritorio'); assert motor.certificado_para(B) is None and motor.certificado_para(A) == A          # sem escritório, B e C ficam sem certificado
cofre.guardar('escritorio', gerar_a1(ESC, 'se', nome='ESCRITORIO CONTABIL'), 'se'); THUMB_ESC = cofre.info('escritorio')['thumbprint']

# ---- SEFAZ simulada (a mesma forma de resposta que as rotinas fiscais devolvem)
def nfe_xml(cn, n, modelo='55', entrada=False):
    k = f'4226{datetime.date.today().strftime("%m")}{cn}{modelo}001{n:09d}1000001234'; outro = '99888777000166'; emit, dest = (outro, cn) if entrada else (cn, outro)
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>{modelo}</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-10-10T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{emit}</CNPJ><xNome>EMITENTE</xNome></emit><dest><CNPJ>{dest}</CNPJ><xNome>DESTINO</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
visto = {'nfe': [], 'nfce': [], 'cte': []}; modo_sefaz = {'cstat_nfe': '138', 'recusa': None}
def lote(cn, fam, nsu, n_docs, **extra):
    if nsu > 0 or n_docs == 0: return True, 'Nenhum documento', {'cstat': '137', 'motivo': 'Nenhum documento localizado', 'documents': [], 'ultNSURet': str(nsu), 'maxNSU': str(nsu), 'qtDfeRet': '0'}
    docs = [{'xml': nfe_xml(cn, i + 1, '65' if fam == 'nfce' else '55'), 'tipo': 'nfeProc', 'nsu': str(i + 1), 'family': fam} for i in range(n_docs)]
    return True, 'ok', {'cstat': '138', 'motivo': 'Documento(s) localizado(s)', 'documents': docs, 'ultNSURet': str(n_docs), 'maxNSU': str(n_docs), 'qtDfeRet': str(n_docs)}
def fake_nfe(th, c, homolog, ind, nsu, ator=3):
    visto['nfe'].append((c, th, int(nsu), ator))
    if modo_sefaz['recusa']: return False, 'A SEFAZ recusou', {'cstat': modo_sefaz['recusa'], 'motivo': 'Rejeição: certificado sem permissão', 'documents': []}
    if modo_sefaz['cstat_nfe'] == '117': return True, 'aguarde', {'cstat': '117', 'motivo': 'Consumo indevido: aguarde', 'documents': [], 'ultNSURet': str(nsu), 'maxNSU': str(nsu), 'qtDfeRet': '0'}
    return lote(c, 'nfe', int(nsu), 2 if ator in (1, '1') else 1)
def fake_nfce(th, c, a, b, nsu): visto['nfce'].append((c, th, int(nsu))); return lote(c, 'nfce', int(nsu), 3)
def fake_cte(th, c, a, ator, nsu): visto['cte'].append((c, th, int(nsu), ator)); return True, 'sem CT-e', {'cstat': '137', 'motivo': 'Nenhum documento localizado', 'documents': [], 'ultNSURet': str(nsu), 'maxNSU': str(nsu), 'qtDfeRet': '0'}
core.test_sef_nfe_webservice, core.test_sef_nfce_webservice, core.test_sef_cte_webservice = fake_nfe, fake_nfce, fake_cte

def n_docs(cn, fam): return len([r for r in core.db_list_documents(cnpj=cn, family=fam, limit=1000, with_xml=False) if r.get('status') != 'Evento'])
import re
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026')
from web import config; config.EXIGIR_2FA = False
cl = TestClient(app, base_url='http://testserver', follow_redirects=False); cl.get('/login'); tk = cl.cookies.get('exato_csrf')
assert cl.get('/buscar').status_code == 303
cl.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
def esperar():
    fim = time.time() + 30
    while time.time() < fim and motor.estado.get('rodando'): time.sleep(.05)
    assert not motor.estado.get('rodando')
pg = cl.get('/buscar').text; assert 'Buscar notas' in pg and 'ALFA LTDA' in pg
pg = cl.get(f'/buscar?empresa={A}').text; assert 'A1 próprio' in pg and 'Situação de ALFA' in pg
# validações
assert 'erro=' in cl.post('/buscar/manual', data={'empresa': '123', 'tipo': ['nfe'], 'csrf': tk}).headers['location']
assert 'erro=' in cl.post('/buscar/manual', data={'empresa': A, 'csrf': tk}).headers['location']                              # nenhum tipo
assert 'erro=' in cl.post('/buscar/manual', data={'empresa': A, 'tipo': ['nfe'], 'modo': 'recomecar', 'csrf': tk}).headers['location']          # sem confirmar
assert cl.post('/buscar/manual', data={'empresa': A, 'tipo': ['nfe'], 'csrf': 'falso'}).headers['location'] == '/buscar'
assert not visto['nfe'] and not visto['nfce']
# só NFC-e: nenhuma consulta de NF-e, CT-e nem NFS-e
n0 = len(chamadas_nfse); r = cl.post('/buscar/manual', data={'empresa': A, 'tipo': ['nfce'], 'modo': 'continuar', 'csrf': tk}); assert 'ok=' in r.headers['location']; esperar()
assert visto['nfce'] and not visto['nfe'] and not visto['cte'] and len(chamadas_nfse) == n0 and n_docs(A, 'nfce') == 3
# só NFS-e
r = cl.post('/buscar/manual', data={'empresa': A, 'tipo': ['nfse'], 'csrf': tk}); esperar(); assert len(chamadas_nfse) > n0 and not visto['nfe'] and n_docs(A, 'nfse') == 1
# NFC-e: a segunda busca continua do ponto salvo; "refazer desde o começo" volta a 0 (NF-e e NFS-e também recomeçam)
visto['nfce'].clear(); cl.post('/buscar/manual', data={'empresa': A, 'tipo': ['nfce'], 'csrf': tk}); esperar(); assert visto['nfce'] and all(v[2] > 0 for v in visto['nfce']), visto['nfce']          # continuou do ponto salvo
visto['nfe'].clear(); visto['nfce'].clear(); n0 = len(chamadas_nfse); cl.post('/buscar/manual', data={'empresa': A, 'tipo': ['nfe', 'nfce', 'nfse'], 'modo': 'recomecar', 'confirmo': '1', 'csrf': tk}); esperar()
assert visto['nfe'] and visto['nfe'][0][2] == 0 and visto['nfce'] and visto['nfce'][0][2] == 0 and len(chamadas_nfse) > n0          # recomeçou do zero
# duas buscas ao mesmo tempo: a segunda é recusada
assert motor.reservar(); r = cl.post('/buscar/manual', data={'empresa': A, 'tipo': ['nfe'], 'csrf': tk}); assert 'erro=' in r.headers['location'] and 'andamento' in r.headers['location'].replace('%20', ' ')
motor._trava.release(); motor.estado['rodando'] = False
# empresa sem certificado nenhum
cofre.remover('escritorio'); r = cl.post('/buscar/manual', data={'empresa': C, 'tipo': ['nfe'], 'csrf': tk}); assert 'erro=' in r.headers['location']
print('Exato Web fase 3 (busca manual): OK')
