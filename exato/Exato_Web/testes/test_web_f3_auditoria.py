"""Exato Web, fase 3 (Auditoria): importa o Excel do SAT, confere com os XMLs, gera o PDF do comparativo e guarda o histórico; envio seguro dos arquivos."""
import os, sys, tempfile, datetime, io
from decimal import Decimal
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3a_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from web import config, auditoria as aud, cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core
sys.path.insert(0, str(config.pasta_nucleo())); import exato_xlsx
CN = '11222333000181'; core.db_register_company(CN, 'PADARIA TESTE LTDA')
def key(n): return f'42260911222333000181' + f'55001{n:09d}1000001234'
def nfe(n, valor):
    k = key(n); return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
                        f'<emit><CNPJ>{CN}</CNPJ><xNome>PADARIA TESTE LTDA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>CLIENTE</xNome></dest><total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
VAL = {1: '100.00', 2: '200.00', 3: '300.00', 4: '400.00', 5: '500.00'}
core.db_upsert_documents(CN, [{'xml': nfe(n, v), 'tipo': 'nfeProc', 'nsu': str(n), 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'} for n, v in VAL.items()])
serial = (datetime.date(2026, 9, 10) - datetime.date(1899, 12, 30)).days
def sat_xlsx(caminho, numeros, valores=VAL):
    cols = [{'title': t, 'width': 16, 'type': 'text'} for t in ('NumeroDocumento', 'DataEmissao', 'ValorTotalNota', 'ChaveAcesso', 'SerieDocumento', 'Situacao', 'TipoDocumento', 'TipoDeOperacaoEntradaOuSaida')]
    linhas = [[str(n), str(serial), str(valores.get(n, '50.00')), key(n), '1', 'Autorizada', 'NF-e', 'Saída'] for n in numeros]
    exato_xlsx.write_xlsx(caminho, [{'name': 'SAT', 'columns': cols, 'rows': linhas}])
tmp = Path(tempfile.mkdtemp()); f_ok = tmp / 'sat.xlsx'; sat_xlsx(f_ok, [1, 2, 3, 4, 5, 6])          # a nota 6 está no SAT mas não tem XML na Central
# ---- direto no módulo
res = aud.auditar(CN, [f_ok], ['nfe'], '2026-09-01', '2026-09-30', 'maria@x.com')
assert res['conciliados'] == 5 and res['sem_xml'] == 1 and res['divergencias'] == 0 and res['status'] in ('atencao', 'divergencia') and res['empresa']
assert [l['situacao'] for l in res['linhas']].count('Sem correspondência') == 1 and any(l['numero'] == '6' and 'não foi localizado' in l['observacao'] for l in res['linhas'])
pdf = aud.caminho_pdf(res['id']); assert pdf and pdf.stat().st_size > 5000
import pypdf; texto = ' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(pdf)).pages); assert 'AUDITORIA FISCAL' in texto and 'PADARIA TESTE' in texto
assert (config.DADOS / 'auditorias' / res['id'] / 'SAT_1.xlsx').exists() and aud.historico()[0]['id'] == res['id'] and not any('linhas' in h for h in aud.historico())
# valor diferente = divergência; tudo certo = conforme
f_div = tmp / 'sat_div.xlsx'; sat_xlsx(f_div, [1, 2, 3, 4, 5], {**VAL, 3: '333.00'})
r2 = aud.auditar(CN, [f_div], ['nfe'], '2026-09-01', '2026-09-30'); assert r2['divergencias'] == 1 and r2['status'] == 'divergencia'
f_ok2 = tmp / 'sat_ok.xlsx'; sat_xlsx(f_ok2, [1, 2, 3, 4, 5]); r3 = aud.auditar(CN, [f_ok2], ['nfe'], '2026-09-01', '2026-09-30'); assert r3['status'] == 'conforme' and r3['sem_xml'] == 0
# ---- erros em linguagem simples
for args, trecho in (((CN, [f_ok], [], '2026-09-01', '2026-09-30'), 'NF-e, NFC-e'), (('123', [f_ok], ['nfe'], '2026-09-01', '2026-09-30'), 'Escolha a empresa'), ((CN, [f_ok], ['nfe'], '2026-09-30', '2026-09-01'), 'período'), ((CN, [f_ok], ['nfce'], '2026-09-01', '2026-09-30'), 'não está escolhido')):
    try: aud.auditar(*args); assert False, args
    except aud.AuditoriaErro as e: assert trecho in str(e), (trecho, str(e))
lixo = tmp / 'lixo.xlsx'; lixo.write_bytes(b'isto nao e excel')
try: aud.auditar(CN, [lixo], ['nfe'], '2026-09-01', '2026-09-30'); assert False
except aud.AuditoriaErro as e: assert 'Não consegui ler' in str(e)
assert aud.ler('../../etc/passwd') is None and aud.ler('x') is None and aud.caminho_pdf('../x') is None
# ---- pelo site
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf')
assert c.get('/auditoria').status_code == 303 and c.get('/auditoria/' + res['id']).status_code == 303 and c.get('/auditoria/' + res['id'] + '/pdf').status_code == 303          # só logado
c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
pg = c.get('/auditoria').text; assert 'Nova auditoria' in pg and 'PADARIA TESTE' in pg and 'Auditorias feitas' in pg
dados = f_ok.read_bytes()
r = c.post('/auditoria', data={'empresa': CN, 'de': '2026-09-01', 'ate': '2026-09-30', 'tipo_nfe': '1', 'csrf': 'falso'}, files={'arquivos': ('sat.xlsx', dados)}); assert 'erro=' in r.headers['location']          # CSRF
r = c.post('/auditoria', data={'empresa': CN, 'de': '2026-09-01', 'ate': '2026-09-30', 'tipo_nfe': '1', 'csrf': tk}, files={'arquivos': ('sat.txt', b'x')}); assert 'erro=' in r.headers['location']
r = c.post('/auditoria', data={'empresa': CN, 'de': '2026-09-01', 'ate': '2026-09-30', 'tipo_nfe': '1', 'csrf': tk}, files={'arquivos': ('sat.xlsx', dados)}); assert r.status_code == 303 and r.headers['location'].startswith('/auditoria/2')
aid = r.headers['location'].rsplit('/', 1)[1]
pg = c.get('/auditoria/' + aid).text; assert 'Baixar o PDF do comparativo' in pg and 'Sem correspondência' in pg and 'PADARIA TESTE' in pg
pg = c.get('/auditoria/' + aid + '?situacao=Conforme').text; assert 'Sem correspondência</span>' not in pg
r = c.get('/auditoria/' + aid + '/pdf'); assert r.status_code == 200 and r.content[:4] == b'%PDF' and 'application/pdf' in r.headers['content-type']
assert c.get('/auditoria/2026010199999999').status_code == 404 and c.get('/auditoria/..%2f..%2fetc/pdf').status_code in (404, 405)
assert not list(Path(config.DADOS).glob('exato_aud_*'))          # sem sobras de arquivos temporários
print('Exato Web fase 3 (auditoria): OK')
