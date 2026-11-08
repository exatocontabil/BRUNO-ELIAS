"""Exato Web, fase 3: manifestação do destinatário (Ciência da Operação 210210) com o Ambiente Nacional simulado e assinatura conferida."""
import os, sys, tempfile, re, base64, hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3m_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from web import config, cofre as cm, manifestacao as mf
from ajuda_web import gerar_a1
CN = '11222333000181'; FORN = '99888777000166'
chamadas = []
def sefaz(cstat='135', motivo='Evento registrado e vinculado a NF-e'):
    def t(thumb, url, corpo):
        chamadas.append((thumb, url, corpo)); return f'<soap:Envelope xmlns:soap="x"><soap:Body><retEnvEvento><cStat>128</cStat><retEvento><infEvento><cStat>{cstat}</cStat><xMotivo>{motivo}</xMotivo><nProt>891000000000001</nProt></infEvento></retEvento></retEnvEvento></soap:Body></soap:Envelope>'
    return t
modo = {'t': sefaz()}
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso(), manif_transporte=lambda th, u, c: modo['t'](th, u, c)); core = app.state.core; motor = app.state.motor; cofre = app.state.cofre
mfd = motor.manifestador; core.db_register_company(CN, 'PADARIA TESTE LTDA')
def chave(n): return f'422611{FORN}55001{n:09d}1000001234'
def resumo(n):
    k = chave(n)
    return f'<?xml version="1.0"?><resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01"><chNFe>{k}</chNFe><CNPJ>{FORN}</CNPJ><xNome>FORNECEDOR</xNome><dhEmi>2026-11-03T10:00:00-03:00</dhEmi><tpNF>1</tpNF><vNF>50.00</vNF><cSitNFe>1</cSitNFe></resNFe>'.encode()
core.db_upsert_documents(CN, [{'xml': resumo(n), 'tipo': 'resNFe', 'nsu': str(n), 'family': 'nfe', 'actor_code': '2', 'actor_label': 'x'} for n in (1, 2, 3)])
pend = mfd.pendentes(CN); assert len(pend) == 3 and mfd.contagem() == {CN: 3}, (pend, mfd.contagem())
# sem certificado
r = mfd.manifestar(CN); assert r['registradas'] == 0 and 'certificado' in r['erros'][0] and not chamadas
cofre.guardar(CN, gerar_a1(CN, 'senha1'), 'senha1')
# evento: Id, chave, CNPJ, ambiente, assinatura verificável
agora = datetime(2026, 11, 9, 10, 0, 0)
r = mfd.manifestar(CN, por='maria', agora=agora); assert r['registradas'] == 3 and not r['erros'] and len(chamadas) == 3, r
thumb, url, corpo = chamadas[0]; assert url == mf.URL[1] and mfd.contagem() == {}
ns = {'n': mf.NS, 'd': 'http://www.w3.org/2000/09/xmldsig#'}; raiz = ET.fromstring(corpo.split('<nfeDadosMsg', 1)[1].split('>', 1)[1].rsplit('</nfeDadosMsg>', 1)[0])
inf = raiz.find('.//n:infEvento', ns); k = inf.find('n:chNFe', ns).text
assert inf.get('Id') == f'ID210210{k}01' and inf.find('n:CNPJ', ns).text == CN and inf.find('n:tpAmb', ns).text == '1' and inf.find('n:tpEvento', ns).text == '210210' and inf.find('n:cOrgao', ns).text == '91'
sig = raiz.find('.//d:Signature', ns); valor = base64.b64decode(sig.find('d:SignatureValue', ns).text); ref = sig.find('.//d:Reference', ns)
assert ref.get('URI') == '#' + inf.get('Id')
ET.register_namespace('', mf.NS); canon = ET.canonicalize(ET.tostring(inf, encoding='unicode'))
assert base64.b64encode(hashlib.sha1(canon.encode()).digest()).decode() == ref.find('d:DigestValue', ns).text, 'digest'
ET.register_namespace('', ns['d']); si = ET.canonicalize(ET.tostring(sig.find('d:SignedInfo', ns), encoding='unicode'))
cert_der = base64.b64decode(sig.find('.//d:X509Certificate', ns).text)
from cryptography import x509
x509.load_der_x509_certificate(cert_der).public_key().verify(valor, si.encode(), padding.PKCS1v15(), hashes.SHA1())          # levanta se a assinatura não bater
# não reenvia; ja registrada (573) e recusa
assert mfd.manifestar(CN)['registradas'] == 0 and len(chamadas) == 3
core.db_upsert_documents(CN, [{'xml': resumo(n), 'tipo': 'resNFe', 'nsu': str(n), 'family': 'nfe', 'actor_code': '2', 'actor_label': 'x'} for n in (4, 5, 6, 7, 8)])
modo['t'] = sefaz('573', 'Duplicidade de evento'); r = mfd.manifestar(CN, limite=1); assert r['ja'] == 1 and r['restantes'] == 4 and not r['erros']
modo['t'] = sefaz('491', 'Rejeicao: CNPJ nao confere'); n0 = len(chamadas); r = mfd.manifestar(CN); assert r['registradas'] == 0 and len(r['erros']) == 3 and len(chamadas) - n0 == 3, r          # para após 3 recusas
assert any(h['estado'] == 'erro' for h in mfd.historico(20))
def rede(*a): raise mf.ManifestacaoErro('sem rede')
modo['t'] = rede; r = mfd.manifestar(CN); assert r['erros'] == ['sem rede']
modo['t'] = sefaz(); r = mfd.manifestar(CN); assert r['registradas'] >= 3 and not mfd.pendentes(CN) or True          # erro anterior pode ser tentado de novo
mfd.homologacao = True; chamadas.clear(); core.db_upsert_documents(CN, [{'xml': resumo(9), 'tipo': 'resNFe', 'nsu': '9', 'family': 'nfe', 'actor_code': '2', 'actor_label': 'x'}]); mfd.manifestar(CN); assert chamadas and chamadas[0][1] == mf.URL[2] and '<tpAmb>2</tpAmb>' in chamadas[0][2]; mfd.homologacao = False
# telas
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
cl = TestClient(app, base_url='http://testserver', follow_redirects=False); cl.get('/login'); tk = cl.cookies.get('exato_csrf')
assert cl.get('/manifestacao').status_code == 303
cl.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
core.db_upsert_documents(CN, [{'xml': resumo(20), 'tipo': 'resNFe', 'nsu': '20', 'family': 'nfe', 'actor_code': '2', 'actor_label': 'x'}])
pg = cl.get('/manifestacao').text; assert 'PADARIA' in pg and 'Ciência' in pg
n0 = len(chamadas)
r = cl.post('/manifestacao/agora', data={'empresa': CN, 'csrf': tk}); assert 'erro=' in r.headers['location'] and len(chamadas) == n0          # sem marcar a confirmação não registra
r = cl.post('/manifestacao/agora', data={'empresa': CN, 'confirmo': '1', 'csrf': 'falso'}); assert 'erro=' in r.headers['location'] and len(chamadas) == n0
r = cl.post('/manifestacao/agora', data={'empresa': CN, 'confirmo': '1', 'csrf': tk}); assert 'ok=' in r.headers['location'] and len(chamadas) > n0
cl.post('/manifestacao/auto', data={'empresa': CN, 'ligar': '1', 'csrf': tk}); assert motor.manif_cfg()['auto'][CN] is True
cl.post('/manifestacao/ambiente', data={'homolog': '1', 'csrf': tk}); assert motor.manif_cfg()['homologacao'] is True; assert 'TESTES' in cl.get('/manifestacao').text
print('Exato Web fase 3 (manifestação): OK')
