"""Exato Web, fase 3: resumo diário por e-mail (uma vez por dia, depois das 7h, com o e-mail do Box-e), tela, prévia e envio de teste."""
import os, sys, tempfile, time, datetime
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3s_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from web import config, cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; agendador = app.state.agendador; cofre = app.state.cofre
CN = '11222333000181'; core.db_register_company(CN, 'PADARIA TESTE LTDA')
def nfe(n):
    k = f'422611{CN}55001{n:09d}1000001234'
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-11-03T10:00:00-03:00</dhEmi></ide><emit><CNPJ>{CN}</CNPJ><xNome>PADARIA TESTE LTDA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>C</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
core.db_upsert_documents(CN, [{'xml': nfe(n), 'tipo': 'nfeProc', 'nsu': str(n), 'family': 'nfe', 'actor_code': '1', 'actor_label': 'x'} for n in (1, 2, 4)])          # falta a nota 3 (numeração)
class SMTP:
    enviados = []
    def send_message(self, m): SMTP.enviados.append(m)
    def quit(self): pass
motor.boxe_conectar = lambda cfg: SMTP()
manha = datetime.datetime(2026, 11, 9, 8, 30); cedo = datetime.datetime(2026, 11, 9, 6, 0)
assert motor.enviar_resumo(agora=manha)['motivo'] == 'nao_e_hora'          # desligado
motor.resumo_cfg().update(ativo=True, destino='diretoria@escritorio.com.br')
assert motor.enviar_resumo(agora=manha)['motivo'] == 'sem_email'          # ainda sem e-mail de envio configurado
c = motor.boxe_cfg(); c.update(servidor='smtp.exemplo.com', usuario='u', remetente='exato@escritorio.com.br', senha_protegida=cofre.proteger_texto('s'))
assert motor.enviar_resumo(agora=cedo)['motivo'] == 'nao_e_hora'          # antes das 7h não manda
motor.estado['rodando'] = True; assert motor.enviar_resumo(agora=manha)['motivo'] == 'nao_e_hora'; motor.estado['rodando'] = False          # nunca durante uma busca
r = motor.enviar_resumo(agora=manha); assert r['enviado'] and len(SMTP.enviados) == 1, r
m = SMTP.enviados[0]; assert m['To'] == 'diretoria@escritorio.com.br' and m['From'] == 'exato@escritorio.com.br' and 'resumo de 09/11/2026' in m['Subject'].lower().replace('exato: ', '')
corpo = m.get_body(('plain',)).get_content(); assert 'PADARIA' in corpo and ('numeração faltando' in corpo and '3' in corpo)
assert motor.resumo_cfg()['ultimo'] == '2026-11-09' and motor.enviar_resumo(agora=manha)['motivo'] == 'nao_e_hora' and len(SMTP.enviados) == 1          # um por dia
assert motor.enviar_resumo(agora=manha + datetime.timedelta(days=1))['enviado'] and len(SMTP.enviados) == 2          # no dia seguinte, de novo
SMTP.enviados.clear()
class SMTPRuim(SMTP):
    def send_message(self, m): raise OSError('rede caiu')
motor.boxe_conectar = lambda cfg: SMTPRuim(); motor.resumo_cfg()['ultimo'] = ''
r = motor.enviar_resumo(agora=manha); assert not r['enviado'] and r['motivo'] == 'falha' and r['erro'] and motor.resumo_cfg()['ultimo'] == ''          # falhou: tenta de novo depois
motor.boxe_conectar = lambda cfg: SMTP()
# o agendador dispara o resumo sozinho
motor.resumo_cfg()['ultimo'] = ''; motor.cfg['auto_round_last'] = datetime.datetime.now().isoformat(timespec='seconds'); n0 = len(SMTP.enviados)
import web.busca as B
agendador.tick(); fim = time.time() + 5
while time.time() < fim and len(SMTP.enviados) == n0 and datetime.datetime.now().hour >= 7: time.sleep(.05)
if datetime.datetime.now().hour >= 7: assert len(SMTP.enviados) == n0 + 1
# telas
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
cl = TestClient(app, base_url='http://testserver', follow_redirects=False); cl.get('/login'); tk = cl.cookies.get('exato_csrf')
assert cl.get('/resumo/previa').status_code == 303 and cl.post('/resumo/enviar', data={'csrf': tk}).status_code == 303
cl.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
pg = cl.get('/boxe').text; assert 'Resumo diário por e-mail' in pg and 'diretoria@escritorio.com.br' in pg
pg = cl.get('/resumo/previa').text; assert 'PADARIA' in pg and 'para conferir' in pg or 'em dia' in pg
r = cl.post('/resumo/salvar', data={'destino': 'invalido', 'ligar': '1', 'csrf': tk}); assert 'erro=' in r.headers['location']
r = cl.post('/resumo/salvar', data={'destino': 'novo@escritorio.com.br', 'ligar': '1', 'csrf': tk}); assert 'ok=' in r.headers['location'] and motor.resumo_cfg()['destino'] == 'novo@escritorio.com.br' and motor.resumo_cfg()['ativo']
r = cl.post('/resumo/salvar', data={'destino': 'novo@escritorio.com.br', 'csrf': 'falso'}); assert 'erro=' in r.headers['location']
n = len(SMTP.enviados); r = cl.post('/resumo/enviar', data={'csrf': tk}); assert 'ok=' in r.headers['location'] and len(SMTP.enviados) == n + 1 and SMTP.enviados[-1]['To'] == 'novo@escritorio.com.br'
cl.post('/resumo/salvar', data={'destino': 'novo@escritorio.com.br', 'csrf': tk}); assert not motor.resumo_cfg()['ativo']
print('Exato Web fase 3 (resumo diário): OK')
