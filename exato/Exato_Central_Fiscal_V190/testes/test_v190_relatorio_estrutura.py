"""V181: relatório de Documentos por FATURAMENTO x DESPESA: seções por tipo e movimentação (sempre os dois lados), sem total geral, texto nunca passa da coluna, &amp; desfeito."""
import os, sys, tempfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_est_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_relatorio_docs_pdf as X
import pypdf
from reportlab.pdfbase.pdfmetrics import stringWidth
# ---- &amp; e corte pela largura real
assert X.outra_parte(b'<NFe><dest><CNPJ>11222333000181</CNPJ><xNome>BUSCHLE &amp; LEPPER S.A.</xNome></dest></NFe>','Saída')['parte']=='BUSCHLE & LEPPER S.A.'
assert X.outra_parte(b'<NFe><emit><xNome>A &quot;B&quot; LTDA</xNome></emit><dest><xNome>X</xNome></dest></NFe>','Entrada')['parte']=='A "B" LTDA'
longo='CONDOMINIO EDIFICIO RESIDENCIAL JARDINS DE MONTE CARLO E COMERCIAL ANEXOS LTDA'
for larg in (30,50,80):
    t=X.ajustar(longo,larg); assert stringWidth(t,'Helvetica',7.6)<=larg*72/25.4-14+0.01 and t.endswith('…'),(larg,t)
assert X.ajustar('CURTO',80)=='CURTO' and X.ajustar('WWWWWWWWWWWWWWWWWWWWWWWWWW',20).endswith('…')
# ---- classificação
assert X.rotulo_secao('nfe',True)=='NF-e (SAÍDA)' and X.rotulo_secao('nfe',False)=='NF-e (ENTRADA)' and X.rotulo_secao('nfse',True)=='NFS-e (PRESTADOS)' and X.rotulo_secao('cte',False)=='CT-e (TOMADOS)' and X.rotulo_secao('nfce',True)=='NFC-e (SAÍDA)'
def L(fam,mov,v,sit='Autorizada',data='2026-09-10',parte='CLIENTE',n='1'):
    return {'familia':fam,'movimentacao':mov,'numero':n,'serie':'1','data':data,'valor':Decimal(v),'situacao':sit,'exportada':False,'chave':'4'*44,'parte':parte,'doc':'11222333000181','empresa':'EMP','cnpj':'11222333000181'}
linhas=[L('nfe','Saída','1000'),L('nfce','Saída','200'),L('nfse','Prestado','300'),L('cte','Prestado','50'),L('nfe','Entrada','400',parte='FORNECEDOR A'),L('nfse','Tomado','60',parte='FORNECEDOR B'),L('cte','Tomado','20',parte='FORNECEDOR C'),
        L('nfe','Saída','999','Cancelada')]
a=X.analise(linhas)
assert a['faturamento']==Decimal('1550.00') and a['despesa']==Decimal('480.00') and a['resultado']==Decimal('1070.00')          # NF-e saída + NFC-e saída + NFS-e prestados + CT-e prestados; cancelada fora
assert a['clientes'][0][0]=='CLIENTE' and a['fornecedores'][0][0]=='FORNECEDOR A'
por=X.secoes(linhas); assert {k for k in por}=={(f,s) for f in ('nfe','nfce','nfse','cte') for s in (True,False)}          # os dois lados de cada tipo, sempre
ordem=X.ordem_secoes(por); assert [X.rotulo_secao(*k) for k in ordem][:4]==['NF-e (SAÍDA)','NFC-e (SAÍDA)','NFS-e (PRESTADOS)','CT-e (PRESTADOS)']          # faturamento primeiro
assert all(s for _,s in ordem[:4]) and not any(s for _,s in ordem[4:])
# CT-e: Saída/Entrada do banco = Prestado/Tomado
n=X.normalizar([{'doc_id':'1','family':'cte','direction':'Saída','number':'5','issued_at':'2026-09-01','value':'10','status':'Autorizado','cnpj':'1'},{'doc_id':'2','family':'cte','direction':'Entrada','number':'6','issued_at':'2026-09-01','value':'10','status':'Autorizado','cnpj':'1'}])
assert [x['movimentacao'] for x in n]==['Prestado','Tomado']
# ---- PDF
tmp=Path(tempfile.mkdtemp(prefix='exato_v183_pdf_')); pdf=tmp/'r.pdf'
linhas.append(L('nfe','Saída','10',parte=longo,n='77'))
X.gerar(linhas,str(pdf),'EMPRESA TESTE','11222333000181','01/09/2026 a 30/09/2026',['Tipo: Todos'])
pg=[' '.join((p.extract_text() or '').split()) for p in pypdf.PdfReader(str(pdf)).pages]; tx=' '.join(pg)
for sec in ('NF-e (SAÍDA)','NF-e (ENTRADA)','NFC-e (SAÍDA)','NFC-e (ENTRADA)','NFS-e (PRESTADOS)','NFS-e (TOMADOS)','CT-e (PRESTADOS)','CT-e (TOMADOS)'): assert sec in tx,sec
i_s=next(i for i,t in enumerate(pg) if t.startswith('NF-e (SAÍDA)')); i_e=next(i for i,t in enumerate(pg) if t.startswith('NF-e (ENTRADA)'))
assert i_s<i_e and 'FORNECEDOR A' not in pg[i_s] and 'FORNECEDOR A' in pg[i_e]          # entrada e saída em páginas diferentes
assert 'FATURAMENTO' in pg[0] and 'DESPESA' in pg[0] and 'FATURAMENTO − DESPESA' in pg[0]
for proibido in ('Total autorizadas','TOTAL AUTORIZADAS','Total geral','Entradas x saídas'): assert proibido not in tx,proibido          # nada de total geral misturado
assert '…' in tx and longo not in tx          # o nome longo foi cortado com reticências
print('V182 relatório estrutura OK')
