"""Exato Web: "Enviar diagnóstico" (ZIP para o suporte, sem dados sensíveis, e envio por e-mail)."""
import os, re, sys, tempfile, zipfile, io
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_diag_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from fastapi.testclient import TestClient
from web import config, cofre as cm, diagnostico as dg
from web.app import criar_app

# máscara
t = dg.mascarar('Empresa 12.345.678/0001-95 e 12345678000195, CPF 123.456.789-09, pessoa.silva@exemplo.com.br em C:\\Users\\Maria Souza\\ExatoWebDados e C:/Users/joao/x')
assert '12.345.678/0001-95' not in t and '12345678000195' not in t and '123.456.789-09' not in t and 'pessoa.silva' not in t and 'Maria' not in t and 'joao' not in t, t
assert '12.***.***/****-95' in t and 'p***@exemplo.com.br' in t and '<usuario>' in t

app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; config.EXIGIR_2FA = False
core.db_auth_register_user('Admin', 'a@exemplo.com.br', 'SenhaForte#2026'); core.db_auth_register_user('Maria', 'm@exemplo.com.br', 'SenhaForte#2026')
c_ = core._auth_connect(); c_.execute("UPDATE users SET role='admin' WHERE email='a@exemplo.com.br'"); c_.execute("UPDATE users SET role='user' WHERE email='m@exemplo.com.br'"); c_.commit(); c_.close()
# dados de mentira: um registro com CNPJ/e-mail, segredos na configuração e arquivos que NUNCA podem sair
logs = config.DADOS / 'logs'; logs.mkdir(exist_ok=True); (logs / 'servidor_saida.log').write_text('INFO empresa 12345678000195 fulano@exemplo.com.br em C:\\Users\\Maria\\x erro de teste', encoding='utf-8')
(config.DADOS / 'cofre').mkdir(exist_ok=True); (config.DADOS / 'cofre' / 'abc.pfx.enc').write_bytes(b'SEGREDO-DO-CERTIFICADO')
motor.cfg.setdefault('boxe', {}).update(senha_protegida='SEGREDO-SENHA-EMAIL', servidor='smtp.exemplo.com', usuario='u'); motor.cfg['nfse_acesso'] = {'123': {'senha': 'SEGREDO-PORTAL'}}; motor.salvar_cfg()

def membros(dados): z = zipfile.ZipFile(io.BytesIO(dados)); return {n: z.read(n).decode('utf-8', 'replace') for n in z.namelist()}
m = membros(dg.montar_zip(core, motor, ocultar=True))
assert set(m) >= {'LEIA-ME.txt', 'resumo.txt', 'registro_do_site.txt'} and set(m) <= {'LEIA-ME.txt', 'resumo.txt', 'registro_do_site.txt', 'registro_do_site_anterior.txt', 'registro_do_exato.txt'}, sorted(m)
tudo = '\n'.join(m.values())
for segredo in ('SEGREDO-DO-CERTIFICADO', 'SEGREDO-SENHA-EMAIL', 'SEGREDO-PORTAL', 'SenhaForte#2026', 'fulano@exemplo.com.br', '12345678000195', 'Maria\\x'): assert segredo not in tudo, segredo          # nada sensível, e o resto mascarado
assert 'erro de teste' in m['registro_do_site.txt'] and 'Versão:' in m['resumo.txt'] and 'Disco' in m['resumo.txt'] and 'Cópia de segurança' in m['resumo.txt'] and 'Empresas:' in m['resumo.txt']
m2 = membros(dg.montar_zip(core, motor, ocultar=False)); assert '12345678000195' in m2['registro_do_site.txt'] and 'NÃO foram escondidos' in m2['LEIA-ME.txt'] and 'SEGREDO' not in '\n'.join(m2.values())          # sem máscara só o que a pessoa pediu; segredos nunca

def entrar(email):
    c = TestClient(app, base_url='http://testserver', follow_redirects=False); c.get('/login'); tk = c.cookies.get('exato_csrf'); assert c.post('/login', data={'email': email, 'senha': 'SenhaForte#2026', 'csrf': tk}).status_code == 303; return c, tk
adm, tk = entrar('a@exemplo.com.br'); com, tkc = entrar('m@exemplo.com.br')
r = adm.get('/diagnostico'); assert r.status_code == 200 and 'Diagnóstico para o suporte' in r.text and 'Nunca vão' in r.text
assert com.get('/diagnostico').status_code == 303 and com.post('/diagnostico/baixar', data={'ocultar': '1', 'csrf': tkc}).status_code == 303
assert adm.post('/diagnostico/baixar', data={'ocultar': '1', 'csrf': 'errado'}).status_code == 303
r = adm.post('/diagnostico/baixar', data={'ocultar': '1', 'csrf': tk}); assert r.status_code == 200 and r.headers['content-type'] == 'application/zip' and 'Diagnostico_Exato_' in r.headers['content-disposition'] and zipfile.is_zipfile(io.BytesIO(r.content))
# e-mail do suporte e envio
assert 'erro=' in adm.post('/diagnostico/suporte', data={'email': 'isso nao e email', 'csrf': tk}).headers['location']
assert 'ok=' in adm.post('/diagnostico/suporte', data={'email': 'suporte@exemplo.com.br', 'csrf': tk}).headers['location'] and motor.cfg['suporte']['email'] == 'suporte@exemplo.com.br'
r = adm.post('/diagnostico/enviar', data={'ocultar': '1', 'csrf': tk}); assert 'erro=' in r.headers['location']          # e-mail de envio ainda não configurado: explica em português
class SMTPFalso:
    enviados = []; falhar = False
    def send_message(self, msg):
        if SMTPFalso.falhar: raise OSError('rede caiu')
        SMTPFalso.enviados.append(msg)
    def quit(self): pass
motor.boxe_conectar = lambda cfg: SMTPFalso()
assert 'ok=' in adm.post('/boxe/salvar', data={'destino': 'box@dominioboxe.com.br', 'servidor': 'smtp.exemplo.com', 'porta': '587', 'seguranca_': 'STARTTLS', 'usuario_': 'u', 'senha': 's', 'remetente': 'e@x.com', 'csrf': tk}).headers['location']
r = adm.post('/diagnostico/enviar', data={'ocultar': '1', 'csrf': tk}); assert 'ok=' in r.headers['location'], r.headers['location']
msg = SMTPFalso.enviados[-1]; assert msg['To'] == 'suporte@exemplo.com.br' and msg['From'] == 'e@x.com' and len(list(msg.iter_attachments())) == 1 and zipfile.is_zipfile(io.BytesIO(list(msg.iter_attachments())[0].get_payload(decode=True)))
SMTPFalso.falhar = True; r = adm.post('/diagnostico/enviar', data={'ocultar': '1', 'csrf': tk}); assert 'erro=' in r.headers['location'] and 'Traceback' not in r.headers['location']
print('Exato Web (diagnóstico): OK')
