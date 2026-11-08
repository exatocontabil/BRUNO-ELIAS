"""Exato Web, fase 3: fechamento do mês (PDF + ZIPs de importação da Domínio no Repositório) e envio das NFS-e ao Box-e por e-mail (uma vez cada, senha protegida)."""
import os, sys, tempfile, io, zipfile, time, json, sqlite3, datetime
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
ARQ = Path(tempfile.mkdtemp(prefix='exato_arq_'))
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3fb_'); os.environ['EXATO_WEB_ARQUIVOS'] = str(ARQ); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from fastapi.testclient import TestClient
from web import config, cofre as cm
from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; cofre = app.state.cofre
sys.path.insert(0, str(config.pasta_nucleo().parent / 'testes')); from test_v190_nfse_core import nfse_xml, chave
CN = '11222333000181'; core.db_register_company(CN, 'PADARIA TESTE LTDA')
def nfe(n, mes, entrada=False):
    k = f'4226{mes[5:]}{CN}55001{n:09d}1000001234'; o = '99888777000166'; e, d = (o, CN) if entrada else (CN, o)
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>{mes}-10T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{e}</CNPJ><xNome>EMITENTE LTDA</xNome></emit><dest><CNPJ>{d}</CNPJ><xNome>DESTINO LTDA</xNome></dest><total><ICMSTot><vNF>{n}0.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
core.db_upsert_documents(CN, [{'xml': nfe(1, '2026-08'), 'tipo': 'nfeProc', 'nsu': '1', 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'},
                              {'xml': nfe(2, '2026-08'), 'tipo': 'nfeProc', 'nsu': '2', 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'},
                              {'xml': nfe(9, '2026-08', True), 'tipo': 'nfeProc', 'nsu': '9', 'family': 'nfe', 'actor_code': '2', 'actor_label': 'Destinatário / Entrada'}])
# ======================= FECHAMENTO
assert motor.fechar_meses()['fechados'] == 0          # automático: ainda chegou nota há pouco (precisa de dias sem nota nova) e nada foi copiado
assert motor.copiar_repositorio()['restantes'] == 0
r = motor.fechar_meses(manual=True); assert r['fechados'] == 1 and not r['erros'], r
marca = motor.fechamento_info(CN, '2026-08', 'PADARIA TESTE LTDA'); assert marca and marca['revisao'] == 0 and any(a.endswith('.pdf') for a in marca['arquivos']) and sum(a.endswith('.zip') for a in marca['arquivos']) >= 2, marca
pasta = motor.pasta_fechamento(CN, '2026-08', 'PADARIA TESTE LTDA'); assert pasta.name == 'Fechamento' and (pasta / '.fechamento.json').exists()
zips = [a for a in marca['arquivos'] if a.endswith('.zip')]; assert all(CN in z and '2026-08' in z for z in zips), zips
z0 = zipfile.ZipFile(pasta / zips[0]); assert all(n.endswith('.xml') for n in z0.namelist())          # ZIP de importação: XMLs soltos
assert motor.fechar_meses(manual=True)['fechados'] == 0          # de novo: já está igual
core.db_upsert_documents(CN, [{'xml': nfe(3, '2026-08'), 'tipo': 'nfeProc', 'nsu': '3', 'family': 'nfe', 'actor_code': '1', 'actor_label': 'Emitente / Saída'}])
assert motor.copiar_repositorio()['restantes'] == 0; r = motor.fechar_meses(manual=True); assert r['revisados'] == 1, r          # nota atrasada: revisão, os arquivos antigos ficam
marca2 = motor.fechamento_info(CN, '2026-08', 'PADARIA TESTE LTDA'); assert marca2['revisao'] == 1 and any('revisado' in a for a in marca2['arquivos']) and set(marca['arquivos']) <= {a for h in marca2['historico'] for a in h['arquivos']}
for a in marca['arquivos']: assert (pasta / a).exists()
# telas
core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf')
for rota in ('/fechamento', '/boxe', f'/fechamento/arquivo?empresa={CN}&mes=2026-08&nome=x.pdf'): assert c.get(rota).status_code == 303
c.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
pg = c.get('/fechamento').text; assert 'Fechamento do mês' in pg and 'Fechado' in pg and '2026-08' in pg and '.zip' in pg
pdf = [a for a in marca2['arquivos'] if a.endswith('.pdf')][0]
r = c.get(f'/fechamento/arquivo?empresa={CN}&mes=2026-08&nome={pdf}'); assert r.status_code == 200 and r.content[:4] == b'%PDF'
r = c.get(f'/fechamento/arquivo?empresa={CN}&mes=2026-08&nome={zips[0]}'); assert r.status_code == 200 and r.content[:2] == b'PK'
for nome in ('../../../etc/passwd', '..%2f..%2fcofre%2fchave.mestra', '.fechamento.json', 'qualquer.pdf'): assert c.get(f'/fechamento/arquivo?empresa={CN}&mes=2026-08&nome={nome}').status_code in (404, 400), nome
assert c.get('/fechamento/arquivo?empresa=1&mes=x&nome=a').status_code == 400
c.post('/fechamento/auto', data={'ligar': '0', 'csrf': tk}); assert motor.fechamento_cfg()['ativo'] is False and motor.fechar_meses().get('desligado'); c.post('/fechamento/auto', data={'ligar': '1', 'csrf': tk}); assert motor.fechamento_cfg()['ativo']
# ======================= BOX-E
class SMTPFalso:
    enviados = []; falhar = False
    def send_message(self, msg):
        if SMTPFalso.falhar: raise OSError('rede caiu')
        SMTPFalso.enviados.append(msg)
    def quit(self): pass
motor.boxe_conectar = lambda cfg: SMTPFalso()
assert motor.enviar_boxe()['motivo'] == 'desligado'
def nfse_item(i, cn=CN): return {'nsu': i, 'chave': chave(i), 'tipo_documento': 'NFSE', 'xml': nfse_xml(i, prest=cn)}
core.db_upsert_nfse_items(CN, [nfse_item(1)]); con = sqlite3.connect(str(core.DB_PATH)); con.execute("UPDATE documents SET first_seen_at='2020-01-01T00:00:00' WHERE family='nfse'"); con.commit(); con.close()          # NFS-e antiga (histórico)
# ligar sem configurar: recusa em linguagem simples
r = c.post('/boxe/ativar', data={'ligar': '1', 'csrf': tk}); assert 'erro=' in r.headers['location'] and not motor.boxe_cfg()['ativo']
r = c.post('/boxe/salvar', data={'destino': 'box@dominioboxe.com.br', 'servidor': 'a@b.com', 'porta': '587', 'seguranca_': 'STARTTLS', 'usuario_': 'u', 'senha': 's', 'remetente': 'e@x.com', 'csrf': tk}); assert 'erro=' in r.headers['location']          # servidor com @
r = c.post('/boxe/salvar', data={'destino': 'box@dominioboxe.com.br', 'servidor': 'smtp.exemplo.com', 'porta': 'abc', 'seguranca_': 'STARTTLS', 'usuario_': 'u', 'senha': 's', 'remetente': 'e@x.com', 'csrf': tk}); assert 'porta' in r.headers['location'].lower()
r = c.post('/boxe/salvar', data={'destino': 'box@dominioboxe.com.br', 'servidor': 'smtp.exemplo.com', 'porta': '587', 'seguranca_': 'STARTTLS', 'usuario_': 'u', 'senha': 'SENHA-SECRETA-DO-EMAIL', 'remetente': 'e@x.com', 'csrf': tk}); assert 'ok=' in r.headers['location']
bruto = (config.DADOS / 'nucleo').rglob('config.json'); texto = ''.join(p.read_text(encoding='utf-8') for p in bruto); assert 'SENHA-SECRETA-DO-EMAIL' not in texto and 'senha_protegida' in texto          # senha nunca em claro
assert 'SENHA-SECRETA-DO-EMAIL' not in c.get('/boxe').text and 'já guardada' in c.get('/boxe').text
assert motor.boxe_cfg_envio()['senha'] == 'SENHA-SECRETA-DO-EMAIL' and motor.boxe_pronto()
r = c.post('/boxe/ativar', data={'ligar': '1', 'csrf': tk}); assert 'ok=' in r.headers['location'] and motor.boxe_cfg()['ativo'] and motor.boxe_cfg()['desde']
assert motor.enviar_boxe()['enviadas'] == 0 and not SMTPFalso.enviados          # a NFS-e antiga não é enviada (só as novas desde a ativação)
time.sleep(1.1); core.db_upsert_nfse_items(CN, [nfse_item(2), nfse_item(3)])
r = motor.enviar_boxe(); assert r['enviadas'] == 2 and r['erros'] == 0 and len(SMTPFalso.enviados) == 1, r
m = SMTPFalso.enviados[0]; assert m['To'] == 'box@dominioboxe.com.br' and m['From'] == 'e@x.com' and len(list(m.iter_attachments())) == 2 and CN in m['Subject']
assert motor.enviar_boxe()['enviadas'] == 0 and len(SMTPFalso.enviados) == 1          # nunca reenvia
time.sleep(1.1); core.db_upsert_nfse_items(CN, [nfse_item(4)]); SMTPFalso.falhar = True; r = motor.enviar_boxe(); assert r['enviadas'] == 0 and r['erros'] >= 1          # falha de envio: volta para a fila
SMTPFalso.falhar = False; assert motor.boxe_pronto()
pg = c.get('/boxe').text; assert 'NFS-e enviadas' in pg and 'Ligado' in pg
# teste de conexão sem enviar (etapas) e e-mail de teste com falha explicada
import web.app as _a; boxe_mod = __import__('exato_boxe')
orig = boxe_mod.testar_conexao; boxe_mod.testar_conexao = lambda cfg, rede=None: [('Achar o servidor', True, 'smtp.exemplo.com encontrado.'), ('Usuário e senha', False, 'O servidor recusou o usuário ou a senha.')]
r = c.post('/boxe/testar', data={'csrf': tk}); loc = r.headers['location']; assert loc.startswith('/boxe?etapas='); pg = c.get(loc).text; assert 'Achar o servidor' in pg and 'recusou o usuário ou a senha' in pg
boxe_mod.testar_conexao = orig
r = c.post('/boxe/ativar', data={'ligar': '0', 'csrf': tk}); assert not motor.boxe_cfg()['ativo'] and motor.enviar_boxe()['motivo'] == 'desligado'
# a rodada também fecha/envia (ordem: copia, Box-e, fecha)
print('Exato Web fase 3 (fechamento + Box-e): OK')
