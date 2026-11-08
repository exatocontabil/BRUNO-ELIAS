"""Exato Web, fase 3 (importação): empresas, notas e pontos de busca do programa instalado entram no site, sem duplicar e sem voltar pontos de busca; aceita pasta e backup .zip."""
import os, sys, tempfile, subprocess, json, zipfile, sqlite3, shutil
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web3_'); os.environ['EXATO_WEB_HTTPS'] = '0'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes'))
from web import config, importar, nucleo
core = nucleo.core(); CORE_DIR = config.pasta_nucleo()
A, B = '11222333000181', '45723174000110'

# ---- "programa instalado": uma pasta Dados de verdade, criada pelo próprio código do Exato
ORIGEM = Path(tempfile.mkdtemp(prefix='exato_orig_'))
codigo = f'''
import sys, datetime
sys.path.insert(0, r"{CORE_DIR}"); sys.path.insert(0, r"{CORE_DIR}/third_party")
import exato_central_fiscal as m
m.init_database()
def nfe(cn, n):
    k = f"4226{{10}}{{cn}}55001{{n:09d}}1000001234"
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{{k}}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{{n}}</nNF><dhEmi>2026-10-10T10:00:00-03:00</dhEmi></ide><emit><CNPJ>{{cn}}</CNPJ><xNome>EMPRESA {{cn[-4:]}} LTDA</xNome></emit><dest><CNPJ>99888777000166</CNPJ><xNome>CLIENTE</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{{k}}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
for cn, nm in (("{A}", "ALFA LTDA"), ("{B}", "BETA LTDA")):
    m.db_register_company(cn, nm)
    m.db_upsert_documents(cn, [{{"xml": nfe(cn, i), "tipo": "nfeProc", "nsu": str(i), "family": "nfe", "actor_code": "1", "actor_label": "Emitente / Saída"}} for i in range(1, 41)])
cfg = m.load_config(); m.save_nsu_state(cfg, "{A}", "nfce", 900); m.save_nsu_state(cfg, "{A}", "nfe_emitente", 40)
import exato_cobertura as C; C.registrar(cfg, "{A}", "nfe", ate=datetime.date(2026, 11, 3)); cfg.setdefault("v028_bootstrap", {{}})["{A}:nfce"] = True; m.save_config(cfg)
'''
subprocess.run([sys.executable, '-c', codigo], env=dict(os.environ, EXATO_DATA_DIR=str(ORIGEM)), check=True)
assert (ORIGEM / 'central_fiscal.db').exists()
antes_bytes = (ORIGEM / 'central_fiscal.db').read_bytes()

def contar(tabela='documents'):
    c = sqlite3.connect(str(core.DB_PATH)); n = c.execute(f'SELECT COUNT(*) FROM {tabela}').fetchone()[0]; c.close(); return n
# ---- site já tem um ponto de busca MAIS adiantado e uma cobertura mais nova: a importação não pode voltar atrás
cfg = core.load_config(); core.save_nsu_state(cfg, A, 'nfe_emitente', 77); core.save_nsu_state(cfg, A, 'nfce', 100)
cfg.setdefault('busca_cobertura', {}).setdefault(A, {})['nfe'] = {'ate': '2026-11-08', 'em': '2026-11-08T10:00:00'}; core.save_config(cfg)
r = importar.importar(ORIGEM, core, progresso=lambda *_: None)
assert r['companies']['novos'] == 2 and r['documents']['novos'] == 80 and r['documents']['total'] == 80, r
assert contar() == 80 and contar('companies') == 2 and contar('document_sources') >= 80
assert (ORIGEM / 'central_fiscal.db').read_bytes() == antes_bytes          # o banco do programa instalado não foi alterado
cfg = core.load_config()
assert core.get_saved_nsu(cfg, A, 'nfce') == 900                          # o do programa instalado estava na frente: vale
assert core.get_saved_nsu(cfg, A, 'nfe_emitente') == 77                   # o do site estava na frente: fica
assert cfg['busca_cobertura'][A]['nfe']['ate'] == '2026-11-08'            # cobertura mais nova do site fica
assert cfg['v028_bootstrap'].get(f'{A}:nfce') is True
# ---- importar de novo (ou de outro computador): nada duplica
r = importar.importar(ORIGEM, core, progresso=lambda *_: None); assert r['documents']['novos'] == 0 and r['companies']['novos'] == 0 and contar() == 80, r
# ---- as notas importadas aparecem na tela de documentos (via código do Exato) e o XML veio inteiro
rows = core.db_list_documents(cnpj=A, family='nfe', limit=100, with_xml=True); assert len(rows) == 40 and all(b'<nfeProc' in (bytes(x['xml']) if not isinstance(x['xml'], bytes) else x['xml']) for x in rows[:5])
# ---- backup .zip
zpath = Path(tempfile.mkdtemp()) / 'central_fiscal_PC01.zip'
with zipfile.ZipFile(zpath, 'w') as z: z.write(ORIGEM / 'central_fiscal.db', 'central_fiscal.db'); z.write(ORIGEM / 'config.json', 'config.json') if (ORIGEM / 'config.json').exists() else None
r = importar.importar(zpath, core, progresso=lambda *_: None); assert r['documents']['novos'] == 0 and r['documents']['total'] == 80
# ---- erros em linguagem simples
for ruim in (Path(tempfile.mkdtemp()), Path(__file__)):
    try: importar.importar(ruim, core); assert False
    except ValueError as e: assert 'Não encontrei o banco' in str(e)
z2 = Path(tempfile.mkdtemp()) / 'vazio.zip'
with zipfile.ZipFile(z2, 'w') as z: z.writestr('leia-me.txt', 'x')
try: importar.importar(z2, core); assert False
except ValueError as e: assert 'não tem o banco' in str(e)
print('Exato Web fase 3 (importação): OK')
