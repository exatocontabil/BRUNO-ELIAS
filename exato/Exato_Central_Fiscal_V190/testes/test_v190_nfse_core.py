"""Núcleo da NFS-e nacional: leitura de XML, lotes do ADN (JSON, gzip+base64), NSU, erros e cancelamento."""
import base64, gzip, json, sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'programa'))
import exato_nfse as n

PREST, TOMA = '12345678000195', '98765432000110'
def chave(i): return f'35503082{PREST}{i:012d}'.ljust(50, '0')[:50]
def nfse_xml(i, prest=PREST, toma=TOMA, valor='1500.00', dh='2026-09-10T14:30:00-03:00'):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<NFSe versao="1.00" xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS{chave(i)}">
<xLocEmi>Florianópolis</xLocEmi><nNFSe>{i}</nNFSe><dhProc>{dh}</dhProc>
<emit><CNPJ>{prest}</CNPJ><xNome>PRESTADORA SERVICOS LTDA</xNome></emit><valores><vLiq>{valor}</vLiq></valores>
<DPS versao="1.00"><infDPS Id="DPS1"><dhEmi>{dh}</dhEmi><serie>1</serie><nDPS>{i}</nDPS>
<prest><CNPJ>{prest}</CNPJ><xNome>PRESTADORA SERVICOS LTDA</xNome></prest>
<toma><CNPJ>{toma}</CNPJ><xNome>TOMADORA COMERCIO LTDA</xNome></toma>
<valores><vServPrest><vServ>{valor}</vServ></vServPrest></valores></infDPS></DPS></infNFSe></NFSe>'''.encode()
def evento_xml(i, tp='101101'):
    return f'''<evento xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.00"><infEvento Id="EVT{chave(i)}{tp}">
<pedRegEvento><infPedReg><chNFSe>{chave(i)}</chNFSe><nPedRegEvento>1</nPedRegEvento><e{tp}><xDesc>Cancelamento de NFS-e</xDesc></e{tp}></infPedReg></pedRegEvento></infEvento></evento>'''.encode()
def pack(xml): return base64.b64encode(gzip.compress(xml)).decode()
def item(nsu, xml, tipo='NFSE', ev=''): return {'NSU': nsu, 'ChaveAcesso': chave(nsu), 'TipoDocumento': tipo, 'TipoEvento': ev, 'ArquivoXml': pack(xml), 'DataHoraGeracao': '2026-09-11T10:00:00'}

# --- leitura da NFS-e
m = n.parse_nfse(nfse_xml(7), PREST)
assert m['chave'] == chave(7) and len(m['chave']) == 50 and m['numero'] == '7' and m['direcao'] == 'Saída'
assert m['valor'] == Decimal('1500.00') and m['data'].startswith('2026-09-10') and m['empresa'] == 'PRESTADORA SERVICOS LTDA' and m['family'] == 'nfse' and m['tipo'] == 'NFS-e'
r = n.parse_nfse(nfse_xml(7), TOMA); assert r['direcao'] == 'Entrada' and r['empresa'] == 'TOMADORA COMERCIO LTDA'
assert n.parse_nfse(nfse_xml(7), '11111111000191')['direcao'] == 'Saída'
try: n.parse_nfse(b'<NFe><x/></NFe>'); raise SystemExit('deveria falhar')
except n.NfseError: pass
assert n.is_nfse_xml(nfse_xml(1)) and not n.is_nfse_xml(b'<nfeProc><NFe/></nfeProc>') and n.is_nfse_event_xml(evento_xml(1))
ev = n.parse_nfse_event(evento_xml(7)); assert ev['key'] == chave(7) and ev['type'] == '101101' and ev['cancels']
assert not n.parse_nfse_event(evento_xml(7, '101103'))['cancels']

# --- resposta do ADN
body = json.dumps({'StatusProcessamento': 'DOCUMENTOS_LOCALIZADOS', 'LoteDFe': [item(11, nfse_xml(11)), item(12, evento_xml(11), 'EVENTO', '101101'), item(13, b'<DPS/>', 'DPS')]})
res = n.parse_adn_response(200, body)
assert [i['nsu'] for i in res['items']] == [11, 12, 13] and res['max_nsu'] == 13
assert [n.classify_item(i) for i in res['items']] == ['nfse', 'evento', 'outro']
assert n.parse_adn_response(404, json.dumps({'StatusProcessamento': 'NENHUM_DOCUMENTO_LOCALIZADO'}))['empty']
for code, frag in ((403, 'recusou o certificado'), (429, 'aguardar'), (503, 'indisponível')):
    try: n.parse_adn_response(code, '{}'); raise SystemExit(f'{code} deveria falhar')
    except n.NfseError as e: assert frag in str(e), (code, str(e))
try: n.parse_adn_response(400, json.dumps({'Erros': [{'Descricao': 'CNPJ inválido'}]})); raise SystemExit('400')
except n.NfseError as e: assert 'CNPJ inválido' in str(e)

# --- busca em lotes por NSU (transporte falso)
pages = {0: [item(i, nfse_xml(i)) for i in range(1, 51)], 50: [item(i, nfse_xml(i)) for i in range(51, 71)]}
calls = []
def fake(url, thumb):
    calls.append(url); nsu = int(url.split('/DFe/')[1].split('?')[0])
    return (200, json.dumps({'StatusProcessamento': 'DOCUMENTOS_LOCALIZADOS', 'LoteDFe': pages[nsu]})) if nsu in pages else (404, json.dumps({'StatusProcessamento': 'NENHUM_DOCUMENTO_LOCALIZADO'}))
seen = []
items, last, info = n.fetch_all_new('AB CD', 0, transport=fake, progress=lambda a, b: seen.append((a, b)), sleep=lambda s: None)
assert len(items) == 70 and last == 70 and info['batches'] == 3 and seen == [(50, 1), (70, 2)]
assert calls[0].endswith('/contribuintes/DFe/0') and calls[-1].endswith('/DFe/70') and 'adn.nfse.gov.br' in calls[0]
items, last, _ = n.fetch_all_new('AB', 70, transport=fake, sleep=lambda s: None); assert items == [] and last == 70
calls.clear(); n.fetch_all_new('AB', 0, homologacao=True, cnpj_consulta='12.345.678/0001-95', transport=fake, sleep=lambda s: None)
assert 'producaorestrita' in calls[0] and 'cnpjConsulta=12345678000195' in calls[0]
_, _, info = n.fetch_all_new('AB', 0, transport=fake, cancelled=lambda: True, sleep=lambda s: None); assert info['cancelled']
# --- XML real: a DPS traz só o CNPJ do prestador; o nome está no bloco do emitente
so_cnpj = nfse_xml(40).replace(b'<prest><CNPJ>' + PREST.encode() + b'</CNPJ><xNome>PRESTADORA SERVICOS LTDA</xNome></prest>', b'<prest><CNPJ>' + PREST.encode() + b'</CNPJ></prest>')
assert b'<prest><CNPJ>' + PREST.encode() + b'</CNPJ></prest>' in so_cnpj
mm = n.parse_nfse(so_cnpj, TOMA); assert mm['prestador']['nome'] == 'PRESTADORA SERVICOS LTDA' and mm['direcao'] == 'Entrada' and mm['tomador']['nome'] == 'TOMADORA COMERCIO LTDA'
# --- importação de XML/ZIP baixados do portal
import tempfile, zipfile
d = Path(tempfile.mkdtemp())
(d / 'a.xml').write_bytes(nfse_xml(21)); (d / 'lixo.xml').write_bytes(b'<x/>'); (d / 'ev.xml').write_bytes(evento_xml(21))
with zipfile.ZipFile(d / 'lote.zip', 'w') as zf:
    zf.writestr('dentro1.xml', nfse_xml(22)); zf.writestr('dentro2.xml', nfse_xml(23, prest='11111111000191', toma='22222222000191')); zf.writestr('a_repetida.xml', nfse_xml(21)); zf.writestr('leia.txt', 'x')
rd = n.read_nfse_files([d / 'a.xml', d / 'lixo.xml', d / 'ev.xml', d / 'lote.zip', d / 'nao_existe.zip'], PREST)
assert sorted(i['tipo_documento'] for i in rd['items']) == ['EVENTO', 'NFSE', 'NFSE'], rd['items']   # 21 (repetida só 1x), 22 e o evento
assert rd['outros_cnpj'] == 1 and len(rd['invalidos']) == 2 and rd['lidos'] == 6, rd
print('V169 NFS-e core: OK')
