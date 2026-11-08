"""Exato Web, fase 3 (Relatórios): relatório de documentos em PDF gerado em segundo plano, com situação, filtros e download seguro."""
import os, sys, tempfile, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3p_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from web import config, relatorios as rel, cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core
CN = '11222333000181'; core.db_register_company(CN, 'PADARIA TESTE LTDA')
def nfe(n, entrada=False, modelo='55'):
    k = f'422609{CN}{modelo}001{n:09d}1000001234'; outro = '99888777000166'; emit, dest = (outro, CN) if entrada else (CN, outro)
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>{modelo}</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{emit}</CNPJ><xNome>FORNECEDOR LTDA</xNome></emit><dest><CNPJ>{dest}</CNPJ><xNome>CLIENTE LTDA</xNome></dest><total><ICMSTot><vNF>{n}0.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
core.db_upsert_documents(CN, [{'xml': nfe(i), 'tipo': 'nfeProc', 'nsu': str(i), 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'} for i in (1, 2, 3)] +
                         [{'xml': nfe(10, True), 'tipo': 'nfeProc', 'nsu': '10', 'family': 'nfe', 'actor_code': '2', 'actor_label': 'Destinatário / Entrada'}])
# ---- módulo, direto
j = rel.pedir(CN, 'nfe', '', '2026-09-01', '2026-09-30', 'maria@x.com', em_segundo_plano=False); j = rel.ler(j['id'])
assert j['estado'] == 'pronto' and j['total'] == 4 and j['empresa'], j
pdf = rel.caminho_pdf(j['id']); assert pdf and pdf.stat().st_size > 3000
import pypdf; texto = ' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(pdf)).pages); assert 'ENTRADA' in texto.upper() and 'SAÍDA' in texto.upper() or 'SAIDA' in texto.upper(), texto[:300]
vazio = rel.pedir(CN, 'cte', '', '', '', 'x', em_segundo_plano=False); vazio = rel.ler(vazio['id']); assert vazio['estado'] == 'erro' and 'Não há documentos' in vazio['erro'] and rel.caminho_pdf(vazio['id']) is None
for ruim, trecho in ((dict(empresa='123'), 'empresa válida'), (dict(tipo='xyz'), 'Tipo inválido'), (dict(mov='Lado'), 'Movimentação'), (dict(de='2026-13-xx'), 'Data inválida'), (dict(de='2026-09-30', ate='2026-09-01'), 'não pode ser maior')):
    try: rel.pedir(**ruim); assert False, ruim
    except rel.RelatorioErro as e: assert trecho in str(e), (trecho, str(e))
assert rel.ler('../x') is None and rel.caminho_pdf('zzzz') is None
# ---- pelo site
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf')
assert c.get('/relatorios').status_code == 303 and c.get('/relatorios/' + j['id'] + '/pdf').status_code == 303          # só logado
c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
assert 'Novo relatório' in c.get('/relatorios').text
n0 = len(rel.recentes()); c.post('/relatorios', data={'empresa': CN, 'tipo': '', 'mov': '', 'de': '', 'ate': '', 'csrf': 'falso'}); assert len(rel.recentes()) == n0          # CSRF
r = c.post('/relatorios', data={'empresa': CN, 'tipo': 'nfe', 'mov': 'Saída', 'de': '2026-09-01', 'ate': '2026-09-30', 'csrf': tk}); assert r.status_code == 303
novo = [x for x in rel.recentes() if x['por'] == 'maria@exemplo.com.br'][0]; fim = time.time() + 30
while time.time() < fim and rel.ler(novo['id'])['estado'] == 'gerando': time.sleep(.05)
assert rel.ler(novo['id'])['estado'] == 'pronto' and rel.ler(novo['id'])['total'] == 3
assert 'Baixar PDF' in c.get('/relatorios').text
r = c.get('/relatorios/' + novo['id'] + '/pdf'); assert r.status_code == 200 and r.content[:4] == b'%PDF' and 'attachment' in r.headers['content-disposition']
r = c.post('/relatorios', data={'empresa': '', 'tipo': 'xyz', 'mov': '', 'de': '', 'ate': '', 'csrf': tk}); assert 'erro=' in r.headers['location']
print('Exato Web fase 3 (relatórios): OK')
