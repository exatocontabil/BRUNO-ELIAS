"""V177: por que a busca não aconteceu — causas em português, registro por empresa/tipo, diagnóstico prévio, relatório em PDF, e a Situação da busca com a causa."""
import os, sys, sqlite3, tempfile
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v177_mot_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_busca_motivos as M, exato_situacao_busca as S
# ---- classificação do que o Exato recebe (texto de erro / cStat) -> causa em português
casos=[('Selecione primeiro um certificado digital.','','sem_certificado'),('Certificado expirado em 10/09','','certificado_vencido'),('Rejeição cStat 657','657','sefaz_consumo'),
       ('consumo indevido: aguarde 1 hora','','sefaz_consumo'),('O portal recusou os 12 pedido(s).','','portal_bloqueio'),('Informe a senha do Emissor Nacional.','','sem_usuario_senha'),
       ('usuário ou senha incorretos','','senha_recusada'),('O portal pediu captcha','','captcha'),('Não consegui abrir o navegador Microsoft Edge.','','navegador'),
       ('A chave privada do certificado não está disponível','','certificado_senha'),('Timeout ao falar com o serviço','','sefaz_fora'),('sem conexão com a rede','','sem_internet'),
       ('Busca cancelada.','','cancelada_pelo_usuario'),('o certificado não possui procuração para este CNPJ','','certificado_outra_empresa'),('xyzzy','','erro_desconhecido'),('','','erro_desconhecido'),
       ('erro do serviço (225)','225','sefaz_rejeicao')]
for texto,cst,esperado in casos:
    got=M.classificar(texto,cst); assert got==esperado,(texto,got,esperado)
assert M.classificar('Timeout','', 'nfse')=='portal_fora'                                 # na NFS-e, serviço fora do ar é o portal, não a SEFAZ
for cod,(tit,exp,acao,grav) in M.CAUSAS.items():
    assert tit and exp and grav in ('erro','aviso','info') and (acao or grav=='info'),cod       # toda causa tem título, explicação e (se não for sucesso) o que fazer
    assert not any(t in (tit+exp+acao).lower() for t in ('traceback','exception','errno','nonetype')),cod          # nada de linguagem de programação
# ---- registro por empresa e tipo
db=tempfile.mktemp(suffix='.db'); CN='11222333000181'
assert M.registrar(db,CN,('nfe','cte'),'sem_certificado','x') and M.registrar(db,CN,'nfse','so_portal') and not M.registrar(db,'123','nfe','ok')
M.registrar(db,CN,'nfe','ok')
u=M.ultimas(db); assert u[(CN,'nfe')]['codigo']=='ok' and u[(CN,'cte')]['codigo']=='sem_certificado' and u[(CN,'cte')]['resultado']=='falha' and u[(CN,'nfse')]['resultado']=='aviso'
h=M.historico(db,CN,10); assert len(h)==4 and h[0]['codigo']=='ok' and [x for x in h if x['codigo']=='so_portal'][0]['titulo'].startswith('Esta empresa só pode')
for i in range(60): M.registrar(db,CN,'nfce','sem_novas')
assert len([x for x in M.historico(db,CN,500) if x['tipo']=='nfce'])==40                    # guarda só as 40 últimas por tipo
assert not M.registrar('/nao/existe/x.db',CN,'nfe','ok') or True                            # nunca levanta erro
# ---- diagnóstico prévio pela configuração
assert M.diagnosticar({'cert_escolhido':False})['xml']=='sem_certificado' and M.diagnosticar({'cert_escolhido':True,'cert_vencido':True})['xml']=='certificado_vencido'
assert M.diagnosticar({'cert_escolhido':True,'empresa_tem_cert':False,'portal_login':False})=={'xml':None,'nfse':'sem_certificado_empresa'}
assert M.diagnosticar({'cert_escolhido':True,'empresa_tem_cert':False,'portal_login':True})['nfse']=='so_portal' and M.diagnosticar({'cert_escolhido':True,'empresa_tem_cert':True})['nfse'] is None
# ---- na Situação da busca: a causa aparece no selo e no relatório
d2=tempfile.mktemp(suffix='.db'); c=sqlite3.connect(d2)
c.execute("CREATE TABLE companies(cnpj TEXT PRIMARY KEY,name TEXT)"); c.execute("""CREATE TABLE documents(doc_id TEXT PRIMARY KEY,cnpj TEXT,family TEXT,doc_type TEXT,direction TEXT,number TEXT,series TEXT,issued_at TEXT,value TEXT,status TEXT,access_key TEXT,source_nsu TEXT,xml BLOB,first_seen_at TEXT,last_seen_at TEXT)""")
c.execute("INSERT INTO companies VALUES(?,?)",(CN,'ALFA LTDA')); c.commit(); c.close()
L=S.linhas(d2,{},None,date(2026,10,7),ocorrencias={(CN,'nfe'):dict(M.explicar('sefaz_consumo'),cnpj=CN,tipo='nfe',quando='2026-10-07T10:00:00',resultado='aviso',detalhe='cStat 657')},
           diagnostico={CN:{'xml':'sem_certificado','nfse':'sem_certificado_empresa'}})
cel=L[0]['celulas']; assert cel['nfe']['causa']['codigo']=='sefaz_consumo' and cel['nfe']['detalhe']=='A SEFAZ bloqueou novas consultas por um tempo'     # o que de fato aconteceu vence a previsão
assert cel['cte']['causa']['codigo']=='sem_certificado' and cel['cte']['causa'].get('previsto') and cel['nfse']['causa']['codigo']=='sem_certificado_empresa'
itens=S.itens_relatorio(L[0]); assert [i['tipo'] for i in itens]==['nfe','nfce','cte','nfse'] and itens[0]['gravidade']=='aviso' and 'Aguarde' in itens[0]['acao'] and itens[2]['gravidade']=='erro'
# ---- PDF legível
pdf=tempfile.mktemp(suffix='.pdf'); M.gerar_pdf(pdf,[{'nome':'ALFA LTDA','cnpj':'11.222.333/0001-81','itens':itens}],'Relatório da busca — ALFA LTDA')
import pypdf; tx=' '.join(' '.join((p.extract_text() or '') for p in pypdf.PdfReader(pdf).pages).split())
for esperado in ('Relatório da busca','ALFA LTDA','NF-e','A SEFAZ bloqueou novas consultas por um tempo','O que fazer:','Aguarde cerca de 1 hora','Falta escolher o certificado digital','Esta empresa não tem certificado neste computador'): assert esperado in tx,(esperado,tx[:400])
assert M.gerar_pdf(tempfile.mktemp(suffix='.pdf'),[])
print('V177 busca motivos OK')
