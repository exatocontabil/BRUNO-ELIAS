"""V179: NFS-e com "ISS fora?" (município de incidência x município do prestador, pelo CÓDIGO) e totais de autorizadas e canceladas SEPARADOS em todos os relatórios."""
import os, sys, tempfile, shutil
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_fora_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
import exato_nfse as n, exato_nfse_pdf as P
from test_v190_nfse_core import chave, PREST, TOMA
def xml(i, incid=None, nome_incid='', cmun='3531803', cloc_emi=None, valor='1000.00', iss='20.00', dh='2026-09-10T10:00:00-03:00', prest=PREST, toma=TOMA):
    inc=(f'<cLocIncid>{incid}</cLocIncid><xLocIncid>{nome_incid}</xLocIncid>' if incid else '')
    ender=(f'<enderNac><cMun>{cmun}</cMun><UF>SP</UF></enderNac>' if cmun else '')
    emi=(f'<cLocEmi>{cloc_emi}</cLocEmi>' if cloc_emi else '')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<NFSe versao="1.00" xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS{chave(i)}"><xLocEmi>Monte Mor</xLocEmi>{inc}<nNFSe>{i}</nNFSe><dhProc>{dh}</dhProc>
<emit><CNPJ>{prest}</CNPJ><xNome>PRESTADORA SERVICOS LTDA</xNome>{ender}</emit><valores><vBC>{valor}</vBC><pAliqAplic>2.00</pAliqAplic><vISSQN>{iss}</vISSQN><vLiq>{valor}</vLiq></valores>
<DPS versao="1.00"><infDPS Id="DPS1"><dhEmi>{dh}</dhEmi><serie>1</serie><nDPS>{i}</nDPS>{emi}<prest><CNPJ>{prest}</CNPJ></prest>
<toma><CNPJ>{toma}</CNPJ><xNome>TOMADORA COMERCIO LTDA</xNome></toma><valores><vServPrest><vServ>{valor}</vServ></vServPrest></valores></infDPS></DPS></infNFSe></NFSe>'''.encode()
# ---- leitura: pelo código; faltando dado = "—" (None), nunca "NÃO"
assert n.parse_nfse_municipio(xml(1,incid='3531803',nome_incid='Monte Mor'))['fora']=='NÃO'
f=n.parse_nfse_municipio(xml(2,incid='3550308',nome_incid='São Paulo')); assert f['fora']=='SIM' and f['incid_nome']=='São Paulo' and f['prest_cod']=='3531803',f
assert n.parse_nfse_municipio(xml(3))['fora'] is None                                  # nota sem município de incidência
assert n.parse_nfse_municipio(xml(4,incid='3550308',nome_incid='São Paulo',cmun=None))['fora'] is None      # sem município do prestador
assert n.parse_nfse_municipio(xml(5,incid='3550308',nome_incid='São Paulo',cmun=None,cloc_emi='3550308'))['fora']=='NÃO'   # usa cLocEmi quando falta o endereço
assert n.parse_nfse_municipio(xml(6,incid='3531803',nome_incid='MONTE MOR  '))['fora']=='NÃO'     # o nome não conta: só o código
assert n.parse_nfse_municipio(b'lixo')['fora'] is None
real=n.parse_nfse_municipio((Path(__file__).parent/'fixtures'/'nfse_real_prestada_anonimizada.xml').read_bytes()); assert real['fora']=='NÃO' and real['incid_nome']=='Monte Mor',real
# ---- linhas
rows=[P.report_row_from_xml(xml(1,incid='3531803',nome_incid='Monte Mor',dh='2026-09-05T10:00:00-03:00'),PREST,'Autorizada'),
      P.report_row_from_xml(xml(2,incid='3550308',nome_incid='São Paulo',iss='50.00',valor='2500.00',dh='2026-09-06T10:00:00-03:00'),PREST,'Autorizada'),
      P.report_row_from_xml(xml(3,dh='2026-09-07T10:00:00-03:00'),PREST,'Autorizada'),
      P.report_row_from_xml(xml(4,incid='3550308',nome_incid='São Paulo',iss='999.00',valor='700.00',dh='2026-09-08T10:00:00-03:00'),PREST,'Cancelada'),
      P.report_row_from_xml(xml(5,valor='300.00',iss='6.00',toma=PREST,prest='98765432000110',incid='4106902',nome_incid='Curitiba',dh='2026-09-09T10:00:00-03:00'),PREST,'Autorizada'),     # tomada, ISS fora
      P.report_row_from_xml(xml(6,valor='400.00',iss='1.00',toma=PREST,prest='98765432000110',incid='3531803',nome_incid='Monte Mor',dh='2026-09-09T10:00:00-03:00'),PREST,'Cancelada')]
assert [r['iss_fora'] for r in rows]==['NÃO','SIM','—','SIM','SIM','NÃO'] and rows[1]['municipio']=='São Paulo' and rows[2]['municipio']=='—',[(r['iss_fora'],r['municipio']) for r in rows]
S=P.monthly_summary(rows)[0]
assert S['fora_qtd']==2 and S['iss_fora']==Decimal('56.00'),S              # só autorizadas: 50 (prestada) + 6 (tomada); a cancelada de 999 não conta
assert S['canc_qtd']==2 and S['canc_valor']==Decimal('1100.00') and S['prest_canc_qtd']==1 and S['prest_canc_valor']==Decimal('700.00') and S['tom_canc_qtd']==1 and S['tom_canc_valor']==Decimal('400.00'),S
assert S['prest_qtd']==3 and S['prest_valor']==Decimal('4500.00') and S['tom_qtd']==1 and S['tom_valor']==Decimal('300.00')
sec={(a,b):t for a,b,_i,t in P.monthly_report_sections(rows)}
assert sec[('2026-09','Prestado')]['fora_qtd']==1 and sec[('2026-09','Prestado')]['iss_fora']==Decimal('50.00') and sec[('2026-09','Prestado')]['canc_valor']==Decimal('700.00')
# ---- PDFs
tmp=Path(tempfile.mkdtemp(prefix='exato_v183_pdf_'))
def texto(pdf):
    import pypdf
    return ' '.join(' '.join((pg.extract_text() or '') for pg in pypdf.PdfReader(str(pdf)).pages).split())
rel=tmp/'mensal.pdf'; P.generate_monthly_report_pdf(rows,str(rel),'PRESTADORA SERVICOS LTDA',PREST,'09/2026'); tx=texto(rel)
for esperado in ('ISS fora?','Município de incidência','São Paulo','Curitiba','Autorizadas:','Canceladas:','TOTAL AUTORIZADAS','TOTAL CANCELADAS','ISS pago fora','R$ 56,00','R$ 1.100,00','R$ 4.800,00','SIM','NÃO'): assert esperado in tx,(esperado,tx[:900])
# autorizadas: 3 prestadas (1000+2500+1000) + 1 tomada (300) = 4 notas, R$ 4.800,00; canceladas 2 notas, R$ 1.100,00
assert '4 R$ 4.800,00' in tx and '2 R$ 1.100,00' in tx,tx[-900:]
res=tmp/'resumo.pdf'; P.generate_monthly_summary_pdf(P.monthly_summary(rows),str(res),'PRESTADORA SERVICOS LTDA',PREST,'09/2026'); tr=texto(res)
for esperado in ('ISS pago fora','Canceladas (à parte)','2 nota(s) R$ 1.100,00','R$ 56,00'): assert esperado in tr,(esperado,tr[:700])
lista=[dict(r,data='05/09/2026') for r in rows]
rl=tmp/'relacao.pdf'; m.generate_nfse_list_pdf(lista,str(rl),'PRESTADORA SERVICOS LTDA',PREST,'09/2026','Todas'); tl=texto(rl)
for esperado in ('ISS fora?','Município de incidência','TOTAL AUTORIZADAS','TOTAL CANCELADAS','ISS pago fora','Serviços prestados — canceladas','Serviços tomados — canceladas','Curitiba','R$ 56,00'): assert esperado in tl,(esperado,tl[:900])
# ---- planilha
folhas=m.App._nfse_excel_sheets(None,[dict(r,exportada=False) for r in rows],True)
cs=[c['title'] for c in folhas[0]['columns']]; l0=folhas[0]['rows'][0]
assert l0[cs.index('ISS pago fora')]=='56.00' and l0[cs.index('Canceladas (notas)')]==2 and l0[cs.index('Canceladas (valor)')]=='1100.00',l0
cn=[c['title'] for c in folhas[1]['columns']]; assert cn.index('ISS fora?')<cn.index('Situação') and 'Município de incidência' in cn
assert [x[cn.index('ISS fora?')] for x in folhas[1]['rows']]==['NÃO','SIM','—','SIM','SIM','NÃO'] and folhas[1]['rows'][1][cn.index('Município de incidência')]=='São Paulo'
shutil.rmtree(tmp,ignore_errors=True)
print('V179 ISS fora e totais OK')
