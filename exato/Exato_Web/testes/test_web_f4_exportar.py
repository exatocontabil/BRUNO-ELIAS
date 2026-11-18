"""Exato Web: ZIP com os eventos das notas (cancelamento em outro mês, sem resumo, aviso quando falta), período livre, formato Domínio, notas novas da busca,
PDF da nota, editar empresa e o ZIP do Fechamento com eventos."""
import os, sys, tempfile, time, io, zipfile, sqlite3, datetime
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web4_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from web import config, cofre as cm, exportar as exp
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor
CN, OUTRO = '11222333000181', '45723174000110'; core.db_register_company(CN, 'EMIT LTDA')
NS = 'xmlns="http://www.portalfiscal.inf.br/nfe"'
def chave(n, mod='55'): return f'35{mod}09{CN}{mod}001{n:09d}1000000{n % 10}0'[:44].ljust(44, '0')
def nfe(n, dh, entrada=False, mod='55'):
    k = chave(n, mod); emit, dest = (OUTRO, CN) if entrada else (CN, OUTRO)
    return (f'<nfeProc {NS}><NFe><infNFe Id="NFe{k}"><ide><mod>{mod}</mod><nNF>{n}</nNF><serie>1</serie><dhEmi>{dh}</dhEmi></ide><emit><CNPJ>{emit}</CNPJ><xNome>{"FORN LTDA" if entrada else "EMIT LTDA"}</xNome></emit>'
            f'<dest><CNPJ>{dest}</CNPJ><xNome>{"EMIT LTDA" if entrada else "CLIENTE LTDA"}</xNome></dest><total><ICMSTot><vNF>100.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
def resumo_cancel(n): return f'<resEvento {NS}><chNFe>{chave(n)}</chNFe><tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento><xEvento>Cancelamento homologado</xEvento><dhEvento>2026-09-11T09:00:00-03:00</dhEvento><nProt>135260000000001</nProt></resEvento>'.encode()
def evento_completo(n, dh): return (f'<procEventoNFe {NS}><evento><infEvento><chNFe>{chave(n)}</chNFe><tpEvento>110111</tpEvento><nSeqEvento>1</nSeqEvento><dhEvento>{dh}</dhEvento></infEvento></evento><retEvento><infEvento><cStat>135</cStat><chNFe>{chave(n)}</chNFe></infEvento></retEvento></procEventoNFe>').encode()
def up(xml, nsu, tipo='nfeProc'): core.db_upsert_documents(CN, [{'xml': xml, 'family': 'nfe', 'tipo': tipo, 'nsu': nsu}])
antes = datetime.datetime.now().replace(microsecond=0)
up(nfe(1, '2026-09-10T10:00:00-03:00'), 1); up(nfe(2, '2026-09-12T10:00:00-03:00'), 2); up(nfe(3, '2026-09-15T10:00:00-03:00'), 3); up(nfe(4, '2026-10-02T10:00:00-03:00'), 4); up(nfe(5, '2026-09-20T10:00:00-03:00', entrada=True), 5)
up(resumo_cancel(1), 10, 'resEvento'); up(evento_completo(1, '2026-10-05T09:00:00-03:00'), 11, 'procEventoNFe')          # nota 1: cancelada em OUTUBRO (evento completo)
up(resumo_cancel(3), 12, 'resEvento')                                                                                    # nota 3: cancelada, mas só chegou o RESUMO
con = sqlite3.connect(str(core.DB_PATH)); st = dict(con.execute("SELECT access_key, status FROM documents WHERE status<>'Evento'").fetchall()); con.close()
assert st[chave(1)] == 'Cancelado' and st[chave(3)] == 'Cancelado' and st[chave(2)] == 'Autorizado', st
def gerar(**kw):
    a = dict(empresa=CN, de='', ate='', tipos=None, mov='', formato='organizado', desde='', por='teste'); a.update(kw); j = exp.pedir(a['empresa'], a['de'], a['ate'], a['tipos'], a['mov'], a['formato'], a['desde'], a['por'], em_segundo_plano=False); return exp.ler(j['id'])
# ---- ZIP de setembro: a nota cancelada em outubro leva o evento; o resumo nunca entra; falta de evento é avisada
j = gerar(de='2026-09-01', ate='2026-09-30'); assert j['estado'] == 'pronto', j
z = zipfile.ZipFile(exp.caminho_zip(j['id'])); nomes = z.namelist()
notas = [n for n in nomes if n.endswith('.xml') and '/Eventos/' not in n]; evs = [n for n in nomes if '/Eventos/' in n]
assert sorted(notas) == sorted([f'NF-e/Saída/{chave(k)}.xml' for k in (1, 2, 3)] + [f'NF-e/Entrada/{chave(5)}.xml']), nomes
assert len(evs) == 1 and evs[0].startswith('NF-e/Saída/Eventos/') and chave(1) in evs[0], evs          # evento da nota 1 (feito em outubro) está no ZIP de setembro
dados = z.read(evs[0]); assert b'procEventoNFe' in dados and b'<resEvento' not in dados
assert not any(b'<resEvento' in z.read(n) for n in nomes if n.endswith('.xml'))          # nenhum resumo em lugar nenhum do ZIP
av = z.read('AVISOS.txt').decode('utf-8'); assert chave(3) in av and 'SEM o XML do cancelamento' in av and 'nunca inventa' in av and chave(1) not in av.split('Notas:')[1]
assert j['notas'] == 4 and j['eventos'] == 1 and j['canceladas'] == 2 and j['sem_evento'] == 1, j
# ---- outubro: a nota 4 sozinha, sem evento algum (o da nota 1 pertence a ela, que é de setembro)
j = gerar(de='2026-10-01', ate='2026-10-31'); z = zipfile.ZipFile(exp.caminho_zip(j['id'])); assert [n for n in z.namelist() if n.endswith('.xml')] == [f'NF-e/Saída/{chave(4)}.xml'] and j['eventos'] == 0
# ---- filtros: movimentação, tipo, sem notas, entradas inválidas
j = gerar(de='2026-09-01', ate='2026-09-30', mov='Entrada'); assert j['notas'] == 1
j = gerar(mov='Saída', tipos=['nfe']); assert j['notas'] == 4          # sem datas: todas as de saída (1, 2, 3 e 4)
for ruim, msg in (({'tipos': ['nfce']}, 'Não há notas'), ({'mov': 'Saída', 'de': '2027-01-01'}, 'Não há notas')):
    assert gerar(**ruim)['estado'] == 'erro' and msg in gerar(**ruim)['erro'], ruim
for ruim in ({'empresa': '123'}, {'tipos': ['xyz']}, {'mov': 'Lado'}, {'formato': 'rar'}, {'de': '2026-09-30', 'ate': '2026-09-01'}, {'de': 'abc'}, {'desde': 'ontem'}):
    try: gerar(**ruim); raise SystemExit(f'devia recusar {ruim}')
    except exp.ExportarErro: pass
# ---- formato Domínio: um ZIP por mês/tipo/movimentação, XMLs soltos e eventos soltos
j = gerar(de='2026-09-01', ate='2026-09-30', formato='dominio'); z = zipfile.ZipFile(exp.caminho_zip(j['id'])); assert 'AVISOS.txt' in z.namelist()
internos = [n for n in z.namelist() if n.endswith('.zip')]; assert sorted(internos) == [f'{CN}_2026-09_NF-e_Entrada.zip', f'{CN}_2026-09_NF-e_Saída.zip'], internos
sai = zipfile.ZipFile(io.BytesIO(z.read(f'{CN}_2026-09_NF-e_Saída.zip'))).namelist(); assert len(sai) == 4 and sum(1 for n in sai if n.startswith('evento_')) == 1 and all('/' not in n for n in sai), sai
# ---- notas novas de uma busca (desde): só as guardadas depois do instante
agora = (antes - datetime.timedelta(seconds=5)).isoformat(); j = gerar(desde=agora); assert j['notas'] == 5, j
futuro = (datetime.datetime.now() + datetime.timedelta(hours=1)).replace(microsecond=0).isoformat(); assert gerar(desde=futuro)['estado'] == 'erro'
# ---- telas e rotas
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
cl = TestClient(app, base_url='http://testserver', follow_redirects=False); cl.get('/login'); tk = cl.cookies.get('exato_csrf')
for rota in ('/exportar', f'/exportar/{j["id"]}/zip', '/documentos/x/pdf', '/exportar/estado'): assert cl.get(rota).status_code in (303, 401), rota          # só logado
cl.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
pg = cl.get(f'/exportar?empresa={CN}&de=2026-09-01&ate=2026-09-30').text; assert 'eventos das notas' in pg and 'Para importar na Domínio' in pg and 'value="2026-09-01"' in pg
assert cl.post('/exportar', data={'empresa': CN, 'csrf': 'falso'}).headers['location'] == '/exportar'
r = cl.post('/exportar', data={'empresa': CN, 'de': '2026-09-01', 'ate': '2026-09-30', 'tipo': ['nfe'], 'formato': 'organizado', 'csrf': tk}); assert 'ok=' in r.headers['location']
fim = time.time() + 20
while time.time() < fim and exp.recentes(1)[0]['estado'] == 'gerando': time.sleep(.1)
jr = exp.recentes(1)[0]; assert jr['estado'] == 'pronto'; rz = cl.get(f"/exportar/{jr['id']}/zip"); assert rz.status_code == 200 and rz.content[:2] == b'PK' and 'filename' in rz.headers['content-disposition']
assert 'erro=' in cl.post('/exportar', data={'empresa': '12', 'csrf': tk}).headers['location'] and cl.get('/exportar/zzzz/zip').status_code == 404 and cl.get('/exportar/..%2f..%2fx/zip').status_code in (404, 422)
pg = cl.get('/exportar').text; assert 'Baixar' in pg and 'cancelada(s) sem o XML do evento' in pg
import json as _j; es = _j.loads(cl.get(f"/exportar/estado?jid={jr['id']}").content); assert es['estado'] == 'pronto' and es['eventos'] == 1
# documentos: coluna PDF, ZIP do filtro e "notas novas"
pg = cl.get(f'/documentos?empresa={CN}').text; assert '<th>PDF</th>' in pg and '/pdf' in pg and 'Baixar ZIP deste filtro' in pg
pg = cl.get(f'/documentos?empresa={CN}&desde={agora}').text; assert 'notas novas guardadas pela busca' in pg
assert cl.get(f'/documentos?empresa={CN}&desde=lixo').status_code == 200
con = sqlite3.connect(str(core.DB_PATH)); did = con.execute("SELECT doc_id FROM documents WHERE access_key=? AND status<>'Evento'", (chave(2),)).fetchone()[0]; evid = con.execute("SELECT doc_id FROM documents WHERE status='Evento' LIMIT 1").fetchone()[0]; con.close()
rp = cl.get(f'/documentos/{did}/pdf'); assert rp.status_code == 200 and rp.content[:5] == b'%PDF-' and rp.headers['content-type'] == 'application/pdf', (rp.status_code, rp.content[:80])
assert cl.get(f'/documentos/{evid}/pdf').status_code == 400 and cl.get('/documentos/nao-existe/pdf').status_code == 404
assert not list(Path(config.DADOS).glob('exato_pdf_*'))          # PDF temporário sumiu depois de enviado
# ---- editar empresa
pg = cl.get('/empresas').text; assert 'Editar' in pg and f'/empresas/editar?cnpj={CN}' in pg
pg = cl.get(f'/empresas/editar?cnpj={CN}').text; assert 'Editar empresa' in pg and 'name="confirmo"' in pg and 'trazem o nome' in pg and cl.get('/empresas/editar?cnpj=12').status_code == 303
assert core.db_get_company_name(CN) == 'EMIT LTDA'
r = cl.post('/empresas/editar', data={'cnpj': CN, 'nome': 'EMPRESA NOVA LTDA', 'csrf': tk}); assert 'erro=' in r.headers['location'] and core.db_get_company_name(CN) == 'EMIT LTDA'          # as notas trazem outro nome: pede confirmação
assert 'erro=' in cl.post('/empresas/editar', data={'cnpj': CN, 'nome': 'ab', 'confirmo': '1', 'csrf': tk}).headers['location'] and 'erro=' in cl.post('/empresas/editar', data={'cnpj': '12', 'nome': 'Nome Valido', 'csrf': tk}).headers['location']
assert 'erro=' in cl.post('/empresas/editar', data={'cnpj': OUTRO, 'nome': 'Nome Valido', 'confirmo': '1', 'csrf': tk}).headers['location']          # CNPJ que não está cadastrado
assert cl.post('/empresas/editar', data={'cnpj': CN, 'nome': 'EMPRESA NOVA LTDA', 'confirmo': '1', 'csrf': 'falso'}).headers['location'].startswith('/empresas?erro=')
r = cl.post('/empresas/editar', data={'cnpj': CN, 'nome': '  EMPRESA   NOVA LTDA ', 'confirmo': '1', 'csrf': tk}); assert 'ok=' in r.headers['location'] and core.db_get_company_name(CN) == 'EMPRESA NOVA LTDA'
core.db_company_verified_name(CN); assert core.db_get_company_name(CN) == 'EMIT LTDA'          # o código do Exato devolve o nome das notas...
motor.reaplicar_nomes(); assert core.db_get_company_name(CN) == 'EMPRESA NOVA LTDA' and motor.nome_manual(CN) == 'EMPRESA NOVA LTDA'          # ...e o nome editado volta a valer
assert 'EMPRESA NOVA LTDA' in cl.get('/empresas').text and 'nome editado à mão' in cl.get('/empresas').text and motor._nome_empresa(CN, 'x') == ('EMPRESA NOVA LTDA', True)
cl.post('/empresas/restaurar-nome', data={'cnpj': CN, 'csrf': tk}); assert motor.nome_manual(CN) == '' and core.db_get_company_name(CN) == 'EMIT LTDA'
time.sleep(.3)
# ---- Fechamento: ZIP de eventos do mês traz o evento da nota (feito em outro mês) e não traz o resumo
fech = __import__('web.nucleo', fromlist=['x']).modulo('exato_fechamento'); con = sqlite3.connect(str(core.DB_PATH)); con.row_factory = sqlite3.Row
docs = [dict(r) for r in con.execute("SELECT * FROM documents WHERE cnpj=? AND family='nfe' AND substr(COALESCE(NULLIF(issued_at,''),first_seen_at),1,7)='2026-09' ORDER BY issued_at", (CN,))]; con.close()
assert not any(d['status'] == 'Evento' for d in docs)          # os eventos chegaram em novembro (data de recebimento): o fechamento de setembro do programa antigo ficaria SEM o evento da nota 1
tmp = tempfile.mkdtemp(); zips = fech._montar_zips(docs, CN, '2026-09', tmp)
nome_ev = [n for n in zips if 'Eventos' in n]; assert len(nome_ev) == 1, list(zips)
ze = zipfile.ZipFile(zips[nome_ev[0]]); xs = ze.namelist(); assert len(xs) == 1 and chave(1) in xs[0] and b'procEventoNFe' in ze.read(xs[0]) and all(b'<resEvento' not in ze.read(n) for n in xs), xs
assert not any(b'<resEvento' in zipfile.ZipFile(p).read(n) for p in zips.values() for n in zipfile.ZipFile(p).namelist())
# NFS-e: PDF e ZIP (Prestados/Tomados)
sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes')); from test_v190_nfse_core import nfse_xml
pasta = Path(tempfile.mkdtemp()); (pasta / 'p.xml').write_bytes(nfse_xml(31, prest=CN, valor='100.00', dh='2026-09-05T10:00:00-03:00')); (pasta / 't.xml').write_bytes(nfse_xml(32, prest='12345678000195', toma=CN, valor='50.00', dh='2026-09-06T10:00:00-03:00'))
core.db_upsert_nfse_items(CN, core.nfse_mod.read_nfse_files([str(x) for x in sorted(pasta.glob('*.xml'))], CN)['items'])
con = sqlite3.connect(str(core.DB_PATH)); nid = con.execute("SELECT doc_id FROM documents WHERE family='nfse' LIMIT 1").fetchone()[0]; con.close()
rp = cl.get(f'/documentos/{nid}/pdf'); assert rp.status_code == 200 and rp.content[:5] == b'%PDF-'
j = gerar(tipos=['nfse'], de='2026-09-01', ate='2026-09-30'); z = zipfile.ZipFile(exp.caminho_zip(j['id'])); assert sorted(n for n in z.namelist() if n.endswith('.xml')) and any(n.startswith('NFS-e/Prestados/') for n in z.namelist()) and any(n.startswith('NFS-e/Tomados/') for n in z.namelist()), z.namelist()
con = sqlite3.connect(str(core.DB_PATH)); con.row_factory = sqlite3.Row; mes_hoje = datetime.date.today().strftime('%Y-%m')
docs_hoje = [dict(r) for r in con.execute("SELECT * FROM documents WHERE cnpj=? AND family='nfe' AND substr(COALESCE(NULLIF(issued_at,''),first_seen_at),1,7)=?", (CN, mes_hoje))]; con.close()
assert any(d['status'] == 'Evento' for d in docs_hoje)          # no mês do recebimento estão as linhas de evento (com o resumo da nota 3)
zh = fech._montar_zips(docs_hoje, CN, mes_hoje, tempfile.mkdtemp()); assert not any(b'<resEvento' in zipfile.ZipFile(p).read(n) for p in zh.values() for n in zipfile.ZipFile(p).namelist())          # resumo nunca vira arquivo do ZIP
print('Exato Web (exportar, eventos, PDF, editar empresa, fechamento): OK')
