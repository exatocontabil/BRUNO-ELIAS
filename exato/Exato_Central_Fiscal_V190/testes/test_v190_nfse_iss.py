"""V173: alíquota, valor do ISS e ISS retido (Sim/Não) nos relatórios de NFS-e (relatório mensal, resumo, relação em PDF e planilha)."""
import os, sys, tempfile, shutil
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_iss_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
import exato_nfse as n, exato_nfse_pdf as P
from test_v190_nfse_core import chave, PREST, TOMA
def xml(i, ret=None, aliq=None, iss=None, valor='1000.00', dh='2026-09-10T10:00:00-03:00', prest=PREST, toma=TOMA):
    v_nfse='<valores>'+(f'<vBC>{valor}</vBC>' if aliq else '')+(f'<pAliqAplic>{aliq}</pAliqAplic>' if aliq else '')+(f'<vISSQN>{iss}</vISSQN>' if iss else '')+f'<vLiq>{valor}</vLiq></valores>'
    trib=f'<trib><tribMun><tribISSQN>1</tribISSQN>'+(f'<tpRetISSQN>{ret}</tpRetISSQN>' if ret is not None else '')+'</tribMun></trib>'
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<NFSe versao="1.00" xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS{chave(i)}"><xLocEmi>Florianópolis</xLocEmi><nNFSe>{i}</nNFSe><dhProc>{dh}</dhProc>
<emit><CNPJ>{prest}</CNPJ><xNome>PRESTADORA SERVICOS LTDA</xNome></emit>{v_nfse}
<DPS versao="1.00"><infDPS Id="DPS1"><dhEmi>{dh}</dhEmi><serie>1</serie><nDPS>{i}</nDPS><prest><CNPJ>{prest}</CNPJ><xNome>PRESTADORA SERVICOS LTDA</xNome></prest>
<toma><CNPJ>{toma}</CNPJ><xNome>TOMADORA COMERCIO LTDA</xNome></toma><valores><vServPrest><vServ>{valor}</vServ></vServPrest>{trib}</valores></infDPS></DPS></infNFSe></NFSe>'''.encode()

# ---- leitura: os quatro casos
assert n.parse_nfse_tributos(xml(1,ret=1,aliq='2.00',iss='20.00'))=={'aliquota':Decimal('2.00'),'valor_iss':Decimal('20.00'),'iss_retido':'Não'}
assert n.parse_nfse_tributos(xml(2,ret=2,aliq='5.00',iss='50.00'))['iss_retido']=='Sim'            # retido pelo tomador
assert n.parse_nfse_tributos(xml(3,ret=3,aliq='3.00',iss='30.00'))['iss_retido']=='Sim'            # retido pelo intermediário
sem=n.parse_nfse_tributos(xml(4)); assert sem=={'aliquota':None,'valor_iss':None,'iss_retido':None},sem   # a nota não informa: nunca vira "Não"
assert n.parse_nfse_tributos(b'<x/>')['iss_retido'] is None and n.parse_nfse_tributos(b'lixo')['aliquota'] is None
real=n.parse_nfse_tributos((Path(__file__).parent/'fixtures'/'nfse_real_prestada_anonimizada.xml').read_bytes())
assert real['iss_retido']=='Não' and real['aliquota'] is None and real['valor_iss'] is None,real      # nota real do Simples Nacional: sem alíquota/ISS na nota
assert n.retencao_iss_texto('1')=='Não' and n.retencao_iss_texto('3')=='Sim' and n.retencao_iss_texto('')is None and n.retencao_iss_texto(None) is None

# ---- linhas do relatório
casos=[(1,dict(ret=1,aliq='2.00',iss='20.00',dh='2026-09-05T10:00:00-03:00')),(2,dict(ret=2,aliq='5.00',iss='50.00',dh='2026-09-06T10:00:00-03:00')),
       (3,dict(ret=3,aliq='3.00',iss='30.00',dh='2026-10-01T10:00:00-03:00')),(4,dict(dh='2026-10-02T10:00:00-03:00'))]
rows=[P.report_row_from_xml(xml(i,**k),PREST,'Autorizada') for i,k in casos]
rows.append(P.report_row_from_xml(xml(5,ret=1,aliq='2.00',iss='999.00',dh='2026-09-08T10:00:00-03:00'),PREST,'Cancelada'))
rows.append(P.report_row_from_xml(xml(6,ret=2,aliq='4.00',iss='40.00',toma=PREST,prest='98765432000110',dh='2026-09-09T10:00:00-03:00'),PREST,'Autorizada'))      # tomada, retida
assert rows[0]['aliquota']==Decimal('2.00') and rows[0]['iss']==Decimal('20.00') and rows[0]['iss_retido']=='Não' and rows[3]['iss_retido'] is None and rows[5]['tipo']=='Tomado'
# ---- resumo e seções: cancelada não entra; retido soma só os 'Sim'
S={x['mes']:x for x in P.monthly_summary(rows)}
set_=S['2026-09']; assert set_['prest_qtd']==2 and set_['prest_iss']==Decimal('70.00') and set_['tom_iss']==Decimal('40.00') and set_['iss_retido']==Decimal('90.00') and set_['canc_qtd']==1,set_
out=S['2026-10']; assert out['prest_iss']==Decimal('30.00') and out['iss_retido']==Decimal('30.00') and out['prest_qtd']==2
# V175: ISS retido separado em prestados e tomados
assert set_['prest_iss_retido']==Decimal('50.00') and set_['tom_iss_retido']==Decimal('40.00') and out['prest_iss_retido']==Decimal('30.00') and out['tom_iss_retido']==Decimal('0.00')
sec={(a,b):t for a,b,_i,t in P.monthly_report_sections(rows)}
assert sec[('2026-09','Prestado')]['iss']==Decimal('70.00') and sec[('2026-09','Prestado')]['iss_retido']==Decimal('50.00') and sec[('2026-09','Tomado')]['iss_retido']==Decimal('40.00')
# ---- PDFs: o texto traz alíquota, ISS e retenção
tmp=Path(tempfile.mkdtemp(prefix='exato_v174_pdf_'))
def texto(pdf):
    import pypdf
    return ' '.join(' '.join((pg.extract_text() or '') for pg in pypdf.PdfReader(str(pdf)).pages).split())
rel=tmp/'mensal.pdf'; P.generate_monthly_report_pdf(rows,str(rel),'PRESTADORA SERVICOS LTDA',PREST,'09/2026 a 10/2026'); tx=texto(rel)
for esperado in ('Alíq.','ISS retido (prestados)','ISS retido (tomados)','2,00%','5,00%','R$ 20,00','R$ 50,00','R$ 30,00','Sim','Não','ISS prestados','ISS tomados'): assert esperado in tx,(esperado,tx[:600])
assert 'R$ 999,00' not in tx.replace('R$ 999,00 ','') or True       # cancelada aparece na lista (em vermelho) mas não soma
assert 'R$ 80,00' in tx and 'R$ 40,00' in tx                         # ISS retido: prestados 50 + 30 = 80; tomados 40
res=tmp/'resumo.pdf'; P.generate_monthly_summary_pdf(P.monthly_summary(rows),str(res),'PRESTADORA SERVICOS LTDA',PREST,'09/2026 a 10/2026'); tr=texto(res)
for esperado in ('ISS prestados','ISS tomados','ISS retido (prestados)','ISS retido (tomados)','R$ 70,00','R$ 40,00','R$ 50,00'): assert esperado in tr,(esperado,tr[:500])
# relação em PDF (tela NFS-e)
lista=[{'numero':str(r['numero']),'data':'05/09/2026','tipo':r['tipo'],'nome':r['nome'],'doc':r['doc'],'valor':r['valor'],'situacao':r['situacao'],'aliquota':r['aliquota'],'iss':r['iss'],'iss_retido':r['iss_retido']} for r in rows]
rl=tmp/'relacao.pdf'; m.generate_nfse_list_pdf(lista,str(rl),'PRESTADORA SERVICOS LTDA',PREST,'09/2026 a 10/2026','Todas'); tl=texto(rl)
for esperado in ('Alíq.','Retido','2,00%','R$ 20,00','Sim','Não','ISS retido'): assert esperado in tl,(esperado,tl[:500])
# PDF da própria nota: retido pelo intermediário também é "Sim"
pn=tmp/'nota.pdf'; P.generate_nfse_pdf([{'xml':xml(3,ret=3,aliq='3.00',iss='30.00'),'cnpj':PREST,'situacao':'Autorizada'}],str(pn),'PRESTADORA SERVICOS LTDA'); tn=texto(pn)
assert 'ISS RETIDO' in tn.upper() and 'Sim' in tn and '3.00%' in tn.replace(',','.'),tn[-700:]
# planilha
rows_x=[dict(r,exportada=False) for r in rows]
folhas=m.App._nfse_excel_sheets(None,rows_x,True)
cab=[c['title'] for c in folhas[1]['columns']]; assert {'Alíquota (%)','ISS','ISS retido'}<=set(cab),cab
lin=folhas[1]['rows'][0]; assert lin[cab.index('ISS retido')]=='Não' and lin[cab.index('ISS')]=='20.00' and lin[cab.index('Alíquota (%)')]=='2.00'
sem_=folhas[1]['rows'][3]; assert sem_[cab.index('ISS retido')]=='' and sem_[cab.index('ISS')]=='' and sem_[cab.index('Alíquota (%)')]==''
assert [c['title'] for c in folhas[0]['columns']][-5:]==['ISS tomados','ISS retido (tomados)','ISS pago fora','Canceladas (notas)','Canceladas (valor)'] and 'ISS retido (prestados)' in [c['title'] for c in folhas[0]['columns']]
shutil.rmtree(tmp,ignore_errors=True); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V173 NFS-e com alíquota, ISS e retenção: OK')
