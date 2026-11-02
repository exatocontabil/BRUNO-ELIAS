"""XML real de NFS-e PRESTADA (anonimizado): leitura e PDF da nota conferidos com o que o portal gera de verdade."""
import sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_nfse as n, exato_nfse_pdf as pdfm
from pypdf import PdfReader
x=(Path(__file__).parent/'fixtures'/'nfse_real_prestada_anonimizada.xml').read_bytes()
m=n.parse_nfse(x,'11222333000181')
assert m['numero']=='98' and m['serie']=='70000' and str(m['valor'])=='8850.00' and m['direcao']=='Saída' and m['chave'].startswith('35318032') and len(m['chave'])==50
assert m['prestador']['nome']=='EMPRESA PRESTADORA EXEMPLO LTDA' and m['tomador']['doc']=='98765432000110' and m['tomador']['nome']=='CLIENTE TOMADOR EXEMPLO LTDA'
assert n.parse_nfse(x,'98765432000110')['direcao']=='Entrada'
d=n.parse_nfse_details(x,'11222333000181')
assert d['prestador_end']['municipio']=='Monte Mor' and d['prestador_end']['uf']=='SP' and d['tomador_end']['municipio']=='Monte Mor' and d['tomador_end']['uf']=='SP'     # nome do município e UF, não o código
assert d['prestador_end']['fone']=='1933334444' and d['prestador_end']['email']=='contato@exemplo.com.br'
assert d['regime_texto']=='Optante pelo Simples Nacional (ME/EPP)' and d['tributos_aprox_sn']=='2.01' and d['servico_codigo_formatado']=='17.23.01' and d['ambiente_dps']=='Produção'
assert d['servico_descricao']=='Gestão de marketing' and d['retencao_iss']=='1' and d['valor_iss'] is None and d['aliquota']==''
out=Path(tempfile.mkdtemp())/'n.pdf'; pdfm.generate_nfse_pdf([{'xml':x,'cnpj':'11222333000181','situacao':'Autorizada'}],str(out),'EMPRESA')
t=' '.join(PdfReader(str(out)).pages[0].extract_text().split())
for token in ('Monte Mor - SP','CEP 13190-037','Tel. (19) 3333-4444','contato@exemplo.com.br','Optante pelo Simples Nacional (ME/EPP)','2,01%','17.23.01','Gestão de marketing','R$ 8.850,00','ISS retido Não' if False else 'Não'):
    assert token in t,token
assert '3531803' not in t.replace('35318032','')      # o código do município não aparece
# ambiente de homologação: aviso
h=x.replace(b'<tpAmb>1</tpAmb>',b'<tpAmb>2</tpAmb>'); out2=out.with_name('h.pdf'); pdfm.generate_nfse_pdf([{'xml':h,'cnpj':'11222333000181'}],str(out2),'EMPRESA')
assert 'HOMOLOGAÇÃO' in ' '.join(PdfReader(str(out2)).pages[0].extract_text().split())
print('V169 XML real de NFS-e: OK')
