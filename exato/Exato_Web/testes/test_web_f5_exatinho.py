"""Exato Web: Exatinho (assistente local): dúvidas de uso (base de conhecimento), quem não buscou e por quê, certificados, contagens, resumo do dia, ações só com confirmação."""
import os, sys, tempfile, json, datetime, sqlite3
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web5_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from fastapi.testclient import TestClient
from ajuda_web import gerar_a1
from web import config, cofre as cm, exatinho as exa, exatinho_log as exalog
from web.exatinho_base import EXEMPLOS, TOPICOS

# ---- base de conhecimento: toda pergunta de exemplo cai no tópico certo; todo tópico tem exemplo; sem tópicos repetidos
ids = [t['id'] for t in TOPICOS]; assert len(ids) == len(set(ids)) and set(EXEMPLOS) == set(ids), set(ids) ^ set(EXEMPLOS)
for tid, qs in EXEMPLOS.items():
    for q in qs:
        r = exa.procurar_topicos(exa.corrigir(q)); assert r and r[0][0] >= 3 and r[0][1]['id'] == tid, (tid, q, [(round(p, 1), t['id']) for p, t in r])
for t in TOPICOS: assert t['resposta'] and all(len(x) < 400 for x in t['resposta']) and (not t['tela'] or t['tela'].startswith('/')), t['id']
assert exa.procurar_topicos(exa.corrigir('qual a capital da franca')) == [] or exa.procurar_topicos(exa.corrigir('qual a capital da franca'))[0][0] < 3          # o que não sabe, não responde
r = exa.procurar_topicos(exa.corrigir('como enviu o certifiado'))[0][1]['id']; assert r == 'enviar_certificado'          # erro de digitação

from web.app import criar_app
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; cofre = app.state.cofre; agendador = app.state.agendador
hoje = datetime.date.today()
def cnpj_valido(base):
    d = [int(x) for x in f'{base:08d}0001']
    for n in (12, 13):
        pesos = [(5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)][n - 12]; s = sum(a * b for a, b in zip(d, pesos)); d.append(0 if s % 11 < 2 else 11 - s % 11)
    return ''.join(map(str, d))
EMP = {'padaria': (cnpj_valido(11111111), 'PADARIA TRIGO DOURADO LTDA'), 'oficina': (cnpj_valido(22222222), 'OFICINA MECANICA SILVA LTDA'), 'clinica': (cnpj_valido(33333333), 'CLINICA SAUDE VIVA S/S'), 'mercado': (cnpj_valido(44444444), 'MERCADO BOM PRECO EIRELI')}
cfg = core.load_config()
for k, (cn, nm) in EMP.items(): core.db_register_company(cn, nm)
def cobertura(cn, fams, dias):
    for f in fams: cfg.setdefault('busca_cobertura', {}).setdefault(cn, {})[f] = {'ate': (hoje - datetime.timedelta(days=dias)).isoformat(), 'inicio': '2026-01-01', 'em': datetime.datetime.now().isoformat(timespec='seconds')}
cobertura(EMP['padaria'][0], ('nfe', 'nfce', 'cte', 'nfse'), 0)            # em dia
cobertura(EMP['oficina'][0], ('nfe', 'nfce', 'cte', 'nfse'), 9)            # atrasada há 9 dias
cobertura(EMP['clinica'][0], ('nfse',), 0)                                 # só NFS-e em dia; o resto nunca buscado
core.save_config(cfg); motor.cfg.update(core.load_config())
cofre.guardar(EMP['padaria'][0], gerar_a1(EMP['padaria'][0], 's', nome='PADARIA'), 's'); cofre.guardar(EMP['oficina'][0], gerar_a1(EMP['oficina'][0], 's', nome='OFICINA'), 's')          # clínica e mercado: sem certificado
def nfe(cn, n, dh):
    ns = 'xmlns="http://www.portalfiscal.inf.br/nfe"'; k = f'35{dh[5:7]}09{cn}55001{n:09d}1000000{n % 10}0'[:44].ljust(44, '0')
    return (f'<nfeProc {ns}><NFe><infNFe Id="NFe{k}"><ide><mod>55</mod><nNF>{n}</nNF><serie>1</serie><dhEmi>{dh}</dhEmi></ide><emit><CNPJ>{cn}</CNPJ><xNome>PADARIA TRIGO DOURADO LTDA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>C</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
mes = hoje.strftime('%Y-%m')
core.db_upsert_documents(EMP['padaria'][0], [{'xml': nfe(EMP['padaria'][0], i, f'{mes}-02T10:00:00-03:00'), 'family': 'nfe', 'tipo': 'nfeProc', 'nsu': i} for i in (1, 2, 3)])

core.db_auth_register_user('Maria Teste', 'maria@exemplo.com.br', 'SenhaForte#2026'); config.EXIGIR_2FA = False
c = core._auth_connect(); c.execute("UPDATE users SET role='admin' WHERE email='maria@exemplo.com.br'"); c.commit(); c.close()
core.db_auth_register_user('Joao Comum', 'joao@exemplo.com.br', 'SenhaForte#2026')
cl = TestClient(app, base_url='http://testserver', follow_redirects=False); cl.get('/login'); tk = cl.cookies.get('exato_csrf')
def perguntar(q, ctx=None, token=None):
    r = cl.post('/exatinho/perguntar', json={'q': q, 'ctx': ctx or {}}, headers={'X-CSRF': token if token is not None else tk}); assert r.status_code == 200, (q, r.status_code, r.text[:200]); return r.json()
# só logado e com o cabeçalho de segurança
assert cl.get('/exatinho/resumo').status_code == 401 and cl.post('/exatinho/perguntar', json={'q': 'oi'}).status_code == 401
cl.post('/login', data={'email': 'maria@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
assert cl.post('/exatinho/perguntar', json={'q': 'oi'}).status_code == 403 and cl.post('/exatinho/perguntar', json={'q': 'oi'}, headers={'X-CSRF': 'falso'}).status_code == 403
pg = cl.get('/situacao').text; assert 'id="exatinho"' in pg and '/static/exatinho.js' in pg and '/static/exatinho.css' in pg and 'Dúvidas do Exatinho' in pg
# ---- quem não buscou, por quê, de quais tipos
d = perguntar('quais empresas não buscaram notas e por quê?'); assert d['topic'] == 'sem_busca' and d['mood'] in ('alerta', 'dica') and len(d['cards']) == 3, d['text']
nomes = [x['nome'] for x in d['cards']]; assert EMP['padaria'][1] not in nomes and EMP['oficina'][1] in nomes and EMP['mercado'][1] in nomes and EMP['clinica'][1] in nomes
mer = next(x for x in d['cards'] if x['nome'] == EMP['mercado'][1]); assert [i['tipo'] for i in mer['itens']] == ['NF-e', 'NFC-e', 'CT-e', 'NFS-e'] and all('certificado' in i['causa'].lower() for i in mer['itens']) and any(b['label'] == 'Enviar certificado' for b in mer['botoes'])
ofi = next(x for x in d['cards'] if x['nome'] == EMP['oficina'][1]); assert all(i['estado'] == 'atrasado' and '9' in i['texto'] for i in ofi['itens']) and any(b['kind'] == 'buscar' for b in ofi['botoes'])
cli = next(x for x in d['cards'] if x['nome'] == EMP['clinica'][1]); assert [i['tipo'] for i in cli['itens']] == ['NF-e', 'NFC-e', 'CT-e']          # NFS-e da clínica está em dia: só os três pendentes
assert 'atrasada' in d['text'] and 'sem certificado' in d['text'] and any('Motivos mais comuns' in l for l in d['lines']) and any(a['kind'] == 'buscar_pendentes' for a in d['actions'])
for q in ('quais empresas estão atrasadas?', 'quem ainda não buscou?', 'quais empresas estão sem busca?'): assert perguntar(q)['topic'] == 'sem_busca', q
d = perguntar('quais empresas estão sem busca de nfs-e?'); assert d['topic'] == 'sem_busca' and d['cards'] and all(i['tipo'] == 'NFS-e' for x in d['cards'] for i in x['itens']) and EMP['clinica'][1] not in [x['nome'] for x in d['cards']]
d = perguntar('quais empresas estão sem certificado?'); assert d['topic'] == 'sem_certificado' and sorted(x['nome'] for x in d['cards']) == sorted([EMP['clinica'][1], EMP['mercado'][1]]) and all('certificado' in i['causa'].lower() for x in d['cards'] for i in x['itens'])
# ---- uma empresa: por que não buscou?
d = perguntar('por que a oficina não buscou?'); assert d['topic'] == 'situacao_empresa' and d['cards'][0]['nome'] == EMP['oficina'][1] and d['ctx']['company'] == EMP['oficina'][0]
d = perguntar('e a clinica?', d['ctx']); assert d['topic'] == 'situacao_empresa' and d['cards'][0]['nome'] == EMP['clinica'][1]          # continua o assunto
d = perguntar('como está a padaria?'); assert 'em dia' in d['text'] and not d['cards']
# ---- certificados, contagens, resumo
d = perguntar('quais certificados vencem?'); assert d['topic'] == 'certificados' and any('sem certificado' in l for l in d['lines'])
d = perguntar('quantas notas tem a padaria este mês?'); assert d['topic'] == 'contagem' and '3 nota(s)' in d['text'] and any('NF-e: 3' in l for l in d['lines']) and any('/exportar?empresa=' in a['url'] for a in d['actions'])
d = perguntar('e em janeiro?', d['ctx']); assert d['topic'] == 'contagem' and 'Não encontrei' in d['text']
d = perguntar('resumo do dia'); assert d['topic'] == 'resumo' and len(d['lines']) >= 2 and any('atrasada' in l for l in d['lines']) and d['mood'] in ('alerta', 'dica')
d = perguntar('bom dia'); assert d['text'].startswith('Bom dia') and d['topic'] == 'resumo'
rr = cl.get('/exatinho/resumo').json(); assert rr['badge'] >= 2 and rr['sugestoes'] and rr['text']
# ---- dúvidas de uso por HTTP, com sugestões e botão para a tela certa
d = perguntar('como envio o certificado?'); assert d['topic'] == 'enviar_certificado' and d['passos'] and any(a['url'] == '/certificados' for a in d['actions']) and d['ajudou'] and d['id']
d = perguntar('o que significa aguardando a próxima janela?'); assert d['topic'] == 'janela_sefaz' and not d['actions']
d = perguntar('como baixo o zip com os eventos?'); assert d['topic'] in ('baixar_zip', 'eventos_zip') and d['passos']
d = perguntar('como busco a partir de uma data'); assert d['topic'] == 'buscar_data'
# ---- ações: só com confirmação; nada acontece sem o "sim"
chamadas = []
agendador.disparar = lambda **kw: (chamadas.append(kw) or True)
d = perguntar('busca as notas da padaria'); assert d['confirm'] and d['confirm']['acao']['kind'] == 'buscar' and d['confirm']['acao']['cnpj'] == EMP['padaria'][0] and not chamadas
d = perguntar('busque o que falta'); assert d['confirm']['acao']['kind'] == 'buscar_pendentes' and not chamadas
d = perguntar('como busco as notas de todas as empresas?'); assert not d['confirm'] and d['topic'] == 'buscar_falta'          # pergunta de "como" não dispara busca
hdr = {'X-CSRF': tk}
assert cl.post('/exatinho/acao', json={'acao': {'kind': 'buscar', 'cnpj': EMP['padaria'][0]}}).status_code == 403 and not chamadas
r = cl.post('/exatinho/acao', json={'acao': {'kind': 'buscar', 'cnpj': EMP['padaria'][0], 'tipos': ['nfe', 'xyz']}}, headers=hdr).json(); assert r['ok'] and chamadas[-1]['only'] == [EMP['padaria'][0]] and chamadas[-1]['tipos'] == ('nfe',) and chamadas[-1]['manual']
r = cl.post('/exatinho/acao', json={'acao': {'kind': 'buscar', 'cnpj': EMP['mercado'][0]}}, headers=hdr).json(); assert not r['ok'] and 'certificado' in r['msg'].lower()          # sem A1: não tenta
r = cl.post('/exatinho/acao', json={'acao': {'kind': 'buscar', 'cnpj': '123'}}, headers=hdr).json(); assert not r['ok']
r = cl.post('/exatinho/acao', json={'acao': {'kind': 'buscar_pendentes'}}, headers=hdr).json(); assert r['ok'] and set(chamadas[-1]['only']) >= {EMP['oficina'][0], EMP['clinica'][0]}
r = cl.post('/exatinho/acao', json={'acao': {'kind': 'apagar_tudo'}}, headers=hdr).json(); assert not r['ok'] and 'desconhecida' in r['msg']
# ---- ir para uma tela e baixar ZIP de uma empresa
d = perguntar('abre a tela de certificados'); assert d.get('abrir') == '/certificados'
d = perguntar('quero o zip da padaria de outubro'); assert any('/exportar?empresa=' + EMP['padaria'][0] in a['url'] for a in d['actions'])
# ---- o que não sabe: diz que não sabe, não inventa, e fica anotado para ensinar
d = perguntar('qual a previsão do tempo para amanhã'); assert d['desconhecida'] and d['topic'] == 'desconhecido' and d['sugestoes'] and not d['passos'] and 'não sei' in d['text'].lower()
assert exalog.resumo()['desconhecidas'] >= 1
cl.post('/exatinho/feedback', json={'id': perguntar('como envio o certificado?')['id'], 'util': False}, headers=hdr); assert exalog.resumo()['inuteis'] == 1
pg = cl.get('/exatinho/duvidas').text; assert 'previsão do tempo' in pg and 'Não ajudou' in pg and 'Não soube responder' in pg
# usuário comum não vê a lista de dúvidas
cl2 = TestClient(app, base_url='http://testserver', follow_redirects=False); cl2.get('/login'); tk2 = cl2.cookies.get('exato_csrf'); cl2.post('/login', data={'email': 'joao@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk2})
assert cl2.get('/exatinho/duvidas').status_code == 303 and 'Dúvidas do Exatinho' not in cl2.get('/situacao').text and 'id="exatinho"' in cl2.get('/situacao').text
# entradas estranhas
assert perguntar('')['topic'] == 'vazio' and perguntar('x' * 900)['desconhecida'] and perguntar('<script>alert(1)</script>')['desconhecida']
print('Exato Web (Exatinho): OK')
