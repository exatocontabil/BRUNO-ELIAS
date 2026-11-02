"""V187: relatório de NF-e de ENTRADA (compras) com as colunas "Optante pelo Simples Nacional?" e "Permite aproveitamento?" (crédito de ICMS do Simples: CSOSN 101/201, vCredICMSSN, frase nas informações complementares)."""
import os, sys, tempfile, re
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v187_simples_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as e
import exato_relatorio_docs_pdf as X
import pypdf
CN='11222333000181'; FORN={'A':'45723174000110','B':'11444777000161','C':'12345678000195','D':'55973430000181'}
def nfe(n,forn,crt,icms,cpl='',valor='100.00'):
    k=f'422609{forn}55001{n:09d}1000001234'
    crt_x=f'<CRT>{crt}</CRT>' if crt else ''
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00"><NFe><infNFe Id="NFe{k}" versao="4.00"><ide><mod>55</mod><serie>1</serie><nNF>{n}</nNF><dhEmi>2026-09-1{n}T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{forn}</CNPJ><xNome>FORNECEDOR &amp; CIA {n}</xNome>{crt_x}</emit><dest><CNPJ>{CN}</CNPJ><xNome>EMPRESA TESTE LTDA</xNome></dest>'
            f'<det nItem="1"><imposto><ICMS>{icms}</ICMS></imposto></det><total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total><infAdic><infCpl>{cpl}</infCpl></infAdic></infNFe></NFe>'
            f'<protNFe><infProt><chNFe>{k}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>').encode()
S101='<ICMSSN101><orig>0</orig><CSOSN>101</CSOSN><pCredSN>2.56</pCredSN><vCredICMSSN>12.34</vCredICMSSN></ICMSSN101>'
S102='<ICMSSN102><orig>0</orig><CSOSN>102</CSOSN></ICMSSN102>'
NORMAL='<ICMS00><orig>0</orig><CST>00</CST><vBC>100.00</vBC><pICMS>12.00</pICMS><vICMS>12.00</vICMS></ICMS00>'
FRASE='EMPRESA OPTANTE PELO SIMPLES NACIONAL. PERMITE O APROVEITAMENTO DE CREDITO DE ICMS NO VALOR DE R$ 12,34 CORRESPONDENTE A ALIQUOTA DE 2,56%.'
# ---- leitura do XML
x1=nfe(1,FORN['A'],1,S101,FRASE); r=X.simples_credito(x1)
assert r=={'optante':'Sim','credito':'Sim','cred_valor':Decimal('12.34'),'cred_aliq':Decimal('2.56')},r
assert X.simples_credito(nfe(2,FORN['B'],1,S102))=={'optante':'Sim','credito':'Não','cred_valor':None,'cred_aliq':None}
assert X.simples_credito(nfe(3,FORN['C'],3,NORMAL))=={'optante':'Não','credito':'—','cred_valor':None,'cred_aliq':None}
assert X.simples_credito(nfe(4,FORN['D'],'',NORMAL))=={'optante':'—','credito':'—','cred_valor':None,'cred_aliq':None}          # sem CRT: sem dado, nunca "Não"
assert X.simples_credito(nfe(5,FORN['A'],1,S101.replace('<pCredSN>2.56</pCredSN><vCredICMSSN>12.34</vCredICMSSN>','')))['credito']=='Sim'          # CSOSN 101 sem valor: permite
assert X.simples_credito(nfe(6,FORN['A'],4,S102,FRASE.replace('R$ 12,34',''))) ['credito']=='Não'          # CSOSN 102 (sem crédito) vale mais que a frase solta
assert X.simples_credito(None)['optante']=='—' and X.simples_credito(b'lixo')['credito']=='—'
# ---- no relatório
e._prepare_persistent_storage(); e.init_database(force=True); e.db_register_company(CN,'EMPRESA TESTE LTDA')
docs=[]
for n,(f,crt,ic,cpl) in enumerate([('A',1,S101,FRASE),('B',1,S102,''),('C',3,NORMAL,''),('D','',NORMAL,'')],1):
    docs.append({'xml':nfe(n,FORN[f],crt,ic,cpl),'tipo':'nfeProc','nsu':str(n),'family':'nfe','actor_code':'2','actor_label':'Destinatário / Entrada'})
e.db_upsert_documents(CN,docs)
rows=e.db_list_documents(limit=1000,with_xml=False); linhas=e.relatorio_documentos_linhas(rows)
ent=[l for l in linhas if l['familia']=='nfe' and l['movimentacao']=='Entrada']; assert len(ent)==4,[ (l['movimentacao']) for l in linhas]
por={l['numero']:l for l in ent}
assert por['1']['optante']=='Sim' and por['1']['credito']=='Sim' and por['1']['cred_valor']==Decimal('12.34')
assert por['2']['credito']=='Não' and por['3']['optante']=='Não' and por['4']['optante']=='—'
tmp=Path(tempfile.mkdtemp()); pdf=tmp/'compras.pdf'; X.gerar(linhas,str(pdf),'EMPRESA TESTE LTDA',CN,'01/09/2026 a 30/09/2026',['Tipo: NF-e'],e.LOGO_PATH)
tx=' '.join(' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(pdf)).pages).split())
assert 'Optante pelo Simples Nacional?' in tx and 'Permite aproveitamento?' in tx,tx[-1500:]
assert re.search(r'Sim \S R\$ 12,34 \S 2,56%',tx) and 'crédito informado de R$ 12,34' in tx and '1 nota(s) autorizada(s)' in tx
assert 'FORNECEDOR & CIA 1' in tx
# a seção de SAÍDA não ganha as colunas novas
saida=[dict(l,movimentacao='Saída') for l in ent[:1]]
pdf2=tmp/'saida.pdf'; X.gerar(saida,str(pdf2),'EMPRESA TESTE LTDA',CN,'', [],e.LOGO_PATH)
t2=' '.join(' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(pdf2)).pages).split()); assert 'Permite aproveitamento?' not in t2
print('relatorio simples ok')
