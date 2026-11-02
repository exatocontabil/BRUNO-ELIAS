"""V168: ZIP para importação na Domínio — um por empresa/mês/tipo/direção, na própria pasta, sem mexer nos XMLs soltos."""
import os, sys, tempfile, shutil, zipfile, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_zip_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_zip_importacao as Z
import exato_central_fiscal as m
from test_v190_nfse_core import nfse_xml, chave, PREST
tmp=Path(tempfile.mkdtemp(prefix='exato_v174_clientes_'))
# ---------- módulo isolado
pasta=tmp/'EMPRESA TESTE'/'2026'/'09 - Setembro'/'Saída'/'NF-e'; pasta.mkdir(parents=True)
for i in range(3): (pasta/('%044d.xml'%i)).write_bytes(b'<nfe n="%d"/>'%i)
(pasta/('%044d.pdf'%0)).write_bytes(b'%PDF'); (pasta/'Relatorio_consolidado.pdf').write_bytes(b'%PDF')
salvos=[str(pasta/('%044d.xml'%i)) for i in range(3)]
r=Z.montar_zips(salvos,'12.345.678/0001-95'); assert r['criados']==1 and not r['erros'],r
zp=pasta/'12345678000195_2026-09_NF-e_Saída.zip'; assert zp.exists() and r['zips']==[str(zp)]
with zipfile.ZipFile(zp) as z: nomes=sorted(z.namelist()); assert nomes==[('%044d.xml'%i) for i in range(3)] and all('/' not in n for n in nomes)      # XMLs soltos, sem PDF, sem subpastas
assert all((pasta/('%044d.xml'%i)).exists() for i in range(3))                    # XMLs soltos continuam
# repetir não refaz; nota nova refaz; ZIP danificado refaz; nunca fica arquivo temporário
mt=zp.stat().st_mtime_ns; r=Z.montar_zips(salvos,'12345678000195'); assert r['iguais']==1 and r['criados']==0 and zp.stat().st_mtime_ns==mt
(pasta/('%044d.xml'%9)).write_bytes(b'<nfe n="9"/>'); r=Z.montar_zips([str(pasta/('%044d.xml'%9))],'12345678000195'); assert r['atualizados']==1
with zipfile.ZipFile(zp) as z: assert len(z.namelist())==4                     # tem TODOS os XMLs da pasta, não só o novo
zp.write_bytes(b'lixo'); r=Z.montar_zips(salvos,'12345678000195'); assert r['atualizados']==1 and zipfile.is_zipfile(zp)
assert not list(pasta.glob('.*.tmp')) and not list(pasta.glob('*.tmp'))
# eventos de cancelamento entram no ZIP
ev=lambda cnpj,chaves: [('evento_1.xml',b'<evento/>')]
r=Z.montar_zips(salvos,'12345678000195',eventos_fn=ev)
with zipfile.ZipFile(zp) as z: assert 'evento_1.xml' in z.namelist() and len(z.namelist())==5
# pasta fora do padrão é ignorada; entrada/saída, prestados/tomados e tipos ficam cada um no seu ZIP
outra=tmp/'solto'; outra.mkdir(); (outra/'a.xml').write_bytes(b'<a/>'); assert Z.montar_zips([str(outra/'a.xml')],'1')['criados']==0
for direc,tipo in (('Entrada','NF-e'),('Saída','NFC-e'),('Prestados','NFS-e'),('Tomados','NFS-e')):
    f=tmp/'EMPRESA TESTE'/'2026'/'10 - Outubro'/direc/tipo; f.mkdir(parents=True); (f/('%050d.xml'%1)).write_bytes(b'<x/>')
    Z.montar_zips([str(f/('%050d.xml'%1))],PREST); assert (f/f'{PREST}_2026-10_{tipo}_{direc}.zip').exists(),(direc,tipo)
# ---------- integração: salvar de verdade (NF-e + NFS-e) deixa os ZIPs; desligado não deixa
m.init_database(); m.db_register_company(PREST,'PRESTADORA SERVICOS LTDA')
nfse=[{'xml':nfse_xml(i,prest=PREST,toma='98765432000110',valor='100.00',dh='2026-09-%02dT10:00:00-03:00'%(5+i)),'family':'nfse','chave':chave(i),'cnpj':PREST} for i in range(1,4)]
dest=tmp/'clientes'; saved,errors=m.save_documents_any(nfse,str(dest),PREST,{'zip_importacao':True},None); assert not errors
zips=sorted(dest.rglob('*.zip')); assert len(zips)==1 and zips[0].name==f'{PREST}_2026-09_NFS-e_Prestados.zip' and zips[0].parent.name=='NFS-e' and zips[0].parent.parent.name=='Prestados',zips
with zipfile.ZipFile(zips[0]) as z: assert len(z.namelist())==3
dest2=tmp/'clientes2'; m.save_documents_any(nfse,str(dest2),PREST,{'zip_importacao':False},None); assert not list(dest2.rglob('*.zip')) and list(dest2.rglob('*.xml'))
assert m.zip_importacao_ativo({}) is True and m.zip_importacao_ativo({'zip_importacao':False}) is False       # ligado por padrão
# cancelada: o evento entra no ZIP
c=sqlite3.connect(m.DB_PATH)
c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,status,access_key,xml,first_seen_at,last_seen_at) VALUES('n1',?,?,?,?,?,?,?,?,?)",(PREST,'nfse','NFS-e','Saída','Cancelado',chave(1),nfse[0]['xml'],'x','x'))
c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,status,access_key,xml,first_seen_at,last_seen_at) VALUES('ev1',?,?,?,?,?,?,?,?,?)",(PREST,'nfse','Evento','','Evento',chave(1),b'<evento tipo="cancelamento"/>','x','x')); c.commit(); c.close()
m.save_documents_any(nfse,str(dest),PREST,{'zip_importacao':True},None)
with zipfile.ZipFile(zips[0]) as z: assert any(n.startswith('evento_') for n in z.namelist()) and len(z.namelist())==4

# V174: as quatro famílias (NF-e, NFC-e, CT-e e NFS-e) saem com ZIP no mesmo salvamento, cada uma na sua pasta
EMIT='11222333000181'; DEST='99888777000166'
def _nfe(mod,n,emit=EMIT,dest=DEST):
    ch='3526091122233300018155001%09d1%08d0'%(n,n) if mod=='55' else '3526091122233300018165001%09d1%08d0'%(n,n)
    ch=ch[:44].ljust(44,'0')
    return ch,('<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe%s"><ide><mod>%s</mod><nNF>%d</nNF><serie>1</serie><dhEmi>2026-09-1%d</dhEmi></ide>'
               '<emit><CNPJ>%s</CNPJ><xNome>EMITENTE LTDA</xNome></emit><dest><CNPJ>%s</CNPJ><xNome>DESTINATARIO</xNome></dest><total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe></nfeProc>'%(ch,mod,n,n%9,emit,dest)).encode()
def _cte(n):
    ch=('3526091122233300018157001%09d1%08d0'%(n,n))[:44].ljust(44,'0')
    return ch,('<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe><infCte Id="CTe%s"><ide><mod>57</mod><nCT>%d</nCT><serie>1</serie><dhEmi>2026-09-1%d</dhEmi></ide><emit><CNPJ>%s</CNPJ><xNome>TRANSP</xNome></emit>'
               '<rem><CNPJ>%s</CNPJ><xNome>REM</xNome></rem><vPrest><vTPrest>20.00</vTPrest></vPrest></infCte></CTe></cteProc>'%(ch,n,n%9,EMIT,DEST)).encode()
docs=[]
for n in (1,2): c1,x=_nfe('55',n); docs.append({'xml':x,'family':'nfe','chave':c1,'cnpj':EMIT})
c1,x=_nfe('65',3); docs.append({'xml':x,'family':'nfce','chave':c1,'cnpj':EMIT})
c1,x=_cte(4); docs.append({'xml':x,'family':'cte','chave':c1,'cnpj':EMIT})
m.db_register_company(EMIT,'EMITENTE LTDA'); dest4=tmp/'clientes4'
saved4,err4=m.save_documents_any(docs,str(dest4),EMIT,{'zip_importacao':True},None); assert not err4,err4
zs=sorted(p.name for p in dest4.rglob('*.zip')); tipos={n.split('_')[2] for n in zs}
assert {'NF-e','NFC-e','CT-e'}<=tipos,zs                                      # uma pasta e um ZIP por família
for zp4 in dest4.rglob('*.zip'):
    with zipfile.ZipFile(zp4) as z: assert z.namelist() and all(n.endswith('.xml') for n in z.namelist()),zp4
shutil.rmtree(tmp,ignore_errors=True); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 zip importação: OK')
