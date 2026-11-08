"""Exato Web, fase 2: busca no servidor com os certificados do cofre (SEFAZ e Emissor Nacional simulados): NF-e/NFC-e/CT-e e NFS-e, certificado da empresa x do escritório
(procuração), pontos de continuação, espera da SEFAZ, recusas explicadas, agendador e telas de busca."""
import os, sys, tempfile, json, time, datetime, sqlite3
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web2_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'chave-de-teste'
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
# ---- rodada 1
r = motor.rodada()
assert r['empresas'] == 3 and r['xml_ok'] == 3 and r['sem_certificado'] == 0, r          # C usa o A1 do escritório (procuração): ninguém ficou sem certificado
assert n_docs(A, 'nfe') >= 2 and n_docs(A, 'nfce') == 3 and n_docs(B, 'nfce') == 3 and n_docs(C, 'nfce') == 3
th_usados = {th for lista in visto.values() for (_c, th, *_x) in lista}; assert th_usados <= {THUMB_A, THUMB_ESC} and {THUMB_A, THUMB_ESC} <= th_usados          # A1 próprio em A, do escritório em B e C
assert all(th == THUMB_A for (c, th, *_x) in visto['nfce'] if c == A) and all(th == THUMB_ESC for (c, th, *_x) in visto['nfce'] if c != A)
imp = [e for e in fake.eventos if e[0] == 'importar']; rem = [e for e in fake.eventos if e[0] == 'remover']; assert len(imp) == len(rem) >= 3          # todo certificado colocado no Windows foi retirado
cfg = core.load_config(); assert cfg['busca_cobertura'][A]['nfce']['ate'] == datetime.date.today().isoformat() and cfg['auto_round_last']
assert core.get_saved_nsu(motor.cfg, A, 'nfce') == 3
oc = nucleo.modulo('exato_busca_motivos').ultimas(str(core.DB_PATH)); assert oc[(A, 'nfce')]['resultado'] == 'ok'
# NFS-e: A (A1 próprio) e B/C pelo escritório; C recusada pelo Emissor Nacional (simulado)
assert (A, THUMB_A) in chamadas_nfse and (B, THUMB_ESC) in chamadas_nfse and (C, THUMB_ESC) in chamadas_nfse
ac = motor.cfg['nfse_acesso']; assert ac[B]['ok'] and ac[B]['modo'] == 'procuracao' and not ac[C]['ok'] and A not in ac
assert oc[(C, 'nfse')]['codigo'] == 'procuracao_nao_aceita' and core.db_nfse_stats(A)['total'] == 1 and core.db_nfse_stats(B)['total'] == 1 and core.db_nfse_stats(C)['total'] == 0
assert r['nfse_novos'] == 2 and r['nfse_problemas'] == 0          # a recusa por procuração na rodada automática não vira "problema"
# ---- rodada 2: continua do ponto salvo (não baixa de novo), NFS-e recusada não é repetida logo depois
for k in visto: visto[k].clear(); chamadas_nfse.clear()
r2 = motor.rodada()
assert all(n > 0 for (_c, _t, n) in visto['nfce']) and n_docs(A, 'nfce') == 3, visto['nfce']          # NSU > 0: parte do ponto salvo
assert (C, THUMB_ESC) not in chamadas_nfse and (B, THUMB_ESC) in chamadas_nfse
# ---- espera da SEFAZ (cStat 117): não é erro; nada é "sem notas" falso
modo_sefaz['cstat_nfe'] = '117'; motor.cfg.pop('nfe_sync_control', None)
rr = motor.rodada(only=[A]); oc = nucleo.modulo('exato_busca_motivos').ultimas(str(core.DB_PATH))
assert rr['empresas'] == 1 and oc[(A, 'nfe')]['codigo'] in ('janela', 'sem_novas', 'ok'), oc[(A, 'nfe')]
# ---- recusa da SEFAZ: causa explicada e cobertura não avança
modo_sefaz['cstat_nfe'] = '138'; modo_sefaz['recusa'] = '217'; hoje_antes = core.load_config()['busca_cobertura'][A]['nfe']['em']; time.sleep(1.1)
motor.cfg.pop('nfe_sync_control', None); rr = motor.rodada(only=[A]); oc = nucleo.modulo('exato_busca_motivos').ultimas(str(core.DB_PATH))
assert oc[(A, 'nfe')]['resultado'] != 'ok' and oc[(A, 'nfe')]['titulo'], oc[(A, 'nfe')]; assert core.load_config()['busca_cobertura'][A]['nfe']['em'] == hoje_antes
modo_sefaz['recusa'] = None
# ---- empresa sem nenhum certificado
cofre.remover('escritorio'); rr = motor.rodada(only=[B]); assert rr['sem_certificado'] == 1
assert nucleo.modulo('exato_busca_motivos').ultimas(str(core.DB_PATH))[(B, 'nfe')]['codigo'] == 'sem_a1'
cofre.guardar('escritorio', gerar_a1(ESC, 'se', nome='ESCRITORIO CONTABIL'), 'se'); THUMB_ESC = cofre.info('escritorio')['thumbprint']
# ---- uma rodada de cada vez e cancelamento
import threading
liberar = threading.Event(); original = core.test_sef_nfce_webservice
def lenta(th, c, a, b, nsu): liberar.wait(5); return original(th, c, a, b, nsu)
core.test_sef_nfce_webservice = lenta
assert agendador.disparar(manual=True) and not agendador.disparar(manual=True)          # a segunda é recusada
fim = time.time() + 5
while not motor.estado['rodando'] and time.time() < fim: time.sleep(.02)
assert motor.estado['rodando'] and motor.rodada() == {'ja_rodando': True}
motor.cancelar(); liberar.set(); fim = time.time() + 20
while motor.estado['rodando'] and time.time() < fim: time.sleep(.05)
assert not motor.estado['rodando'] and motor.estado['resumo']['cancelada']
core.test_sef_nfce_webservice = original
# ---- agendador: só roda quando passou das 4 horas e está ligado
motor.cfg['auto_round_last'] = datetime.datetime.now().isoformat(timespec='seconds'); assert not motor.vencida() and not agendador.tick()
motor.cfg['auto_round_last'] = (datetime.datetime.now() - datetime.timedelta(hours=5)).isoformat(timespec='seconds'); assert motor.vencida()
agendador.definir(False); assert not agendador.tick() and agendador.proxima() == ''
agendador.definir(True); assert agendador.tick(); fim = time.time() + 30
time.sleep(.3)
while motor.estado['rodando'] and time.time() < fim: time.sleep(.05)
assert not motor.vencida()
# ---- telas
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026')
os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'
from web import config; config.EXIGIR_2FA = False
c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf')
assert c.get('/busca/estado').status_code == 401
r = c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk}); assert r.headers['location'] == '/situacao'
est = c.get('/busca/estado').json(); assert est['rodando'] is False and est['auto'] is True and est['total'] == 3
pg = c.get('/situacao').text; assert 'Buscar o que falta' in pg and '/busca/agora' in pg and '11.222.333/0001-81' in pg and 'procuração' in pg
assert 'sem_a1' not in pg and ('Esta empresa não tem certificado A1' in pg or 'O Emissor Nacional não aceitou a procuração' in pg)
assert c.post('/busca/auto', data={'ligar': '0', 'csrf': 'falso'}).status_code == 303 and agendador.ligado()          # CSRF
c.post('/busca/auto', data={'ligar': '0', 'csrf': tk}); assert not agendador.ligado() and 'desligada' in c.get('/situacao').text
c.post('/busca/auto', data={'ligar': '1', 'csrf': tk}); assert agendador.ligado()
visto['nfce'].clear(); c.post('/busca/agora', data={'empresa': A, 'csrf': tk}); fim = time.time() + 20; time.sleep(.3)
while motor.estado['rodando'] and time.time() < fim: time.sleep(.05)
assert visto['nfce'] and all(cn == A for (cn, _t, _n) in visto['nfce'])          # só a empresa pedida
print('Exato Web fase 2: OK')
