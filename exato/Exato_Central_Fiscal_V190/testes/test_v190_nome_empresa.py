"""V168: nome da empresa sempre correto (nunca o de fornecedor) e pasta do repositório que acompanha o nome correto."""
import os, sys, sqlite3, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_nome_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_central_fiscal as m
import exato_repositorio as R
BENVALE='59069269000177'; SHPS='11222333000181'; TRANSP='12345678000195'
def nfe(emit,emit_nome,dest,dest_nome,n=1,extra=''):
    return (f'<nfeProc><NFe><infNFe Id="NFe{n:044d}"><ide><mod>55</mod><nNF>{n}</nNF><dhEmi>2026-09-10T10:00:00-03:00</dhEmi></ide>'
            f'<emit><CNPJ>{emit}</CNPJ><xNome>{emit_nome}</xNome></emit><dest><CNPJ>{dest}</CNPJ><xNome>{dest_nome}</xNome></dest>{extra}'
            f'<total><ICMSTot><vNF>10.00</vNF></ICMSTot></total></infNFe></NFe></nfeProc>').encode()
# --- o nome só vem de nota em que a empresa é parte (emitente/destinatário), nunca de fornecedor
pick=m._pick_authoritative_company_name
assert pick([{'xml':nfe(SHPS,'SHPS TECNOLOGIA E SERVICOS LTDA',BENVALE,'BENVALE LTDA'),'family':'nfe'}],BENVALE)=='BENVALE LTDA'
assert pick([{'xml':nfe(BENVALE,'BENVALE LTDA',SHPS,'SHPS TECNOLOGIA E SERVICOS LTDA',2),'family':'nfe'}],BENVALE)=='BENVALE LTDA'
# empresa que só aparece como transportadora (não é emitente nem destinatária): antes o nome do fornecedor virava o nome dela
assert pick([{'xml':nfe(SHPS,'SHPS TECNOLOGIA E SERVICOS LTDA','99999999000191','CLIENTE QUALQUER',3,f'<transp><transporta><CNPJ>{BENVALE}</CNPJ><xNome>BENVALE LTDA</xNome></transporta></transp>'),'family':'nfe'}],BENVALE)==''
# destinatário sem nome: não cai para o nome do emitente
assert pick([{'xml':nfe(SHPS,'SHPS TECNOLOGIA E SERVICOS LTDA',BENVALE,'',4),'family':'nfe'}],BENVALE)==''
# CT-e: só tomador ou emitente
cte=lambda tom,tomn: (f'<cteProc><CTe><infCte Id="CTe{5:044d}"><emit><CNPJ>{SHPS}</CNPJ><xNome>TRANSPORTADORA SHPS</xNome></emit><rem><CNPJ>{BENVALE}</CNPJ><xNome>BENVALE LTDA</xNome></rem><ide><toma3><toma>3</toma></toma3></ide><dest><CNPJ>{tom}</CNPJ><xNome>{tomn}</xNome></dest></infCte></CTe></cteProc>').encode()
assert pick([{'xml':cte('99999999000191','OUTRA'),'family':'cte'}],BENVALE)==''     # remetente não é tomador
# --- banco: nome errado é corrigido pelos XMLs; sem prova, fica como está; documento sem relação não troca o nome
m.init_database(); m.db_register_company(BENVALE,'SHPS TECNOLOGIA E SERVICOS LTDA')
assert m.db_company_verified_name(BENVALE)==('SHPS TECNOLOGIA E SERVICOS LTDA',False)
c=sqlite3.connect(m.DB_PATH)
c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES('x1',?,?,?,?,?,?,?,?,?,?,?)",(BENVALE,'nfe','NF-e','Entrada','1','2026-09-10T10:00:00','Autorizado','%044d'%1,nfe(SHPS,'SHPS TECNOLOGIA E SERVICOS LTDA',BENVALE,'BENVALE LTDA'),'2026-01-01','2026-01-01')); c.commit(); c.close()
assert m.db_company_verified_name(BENVALE)==('BENVALE LTDA',True) and m.db_get_company_name(BENVALE)=='BENVALE LTDA'
m.db_upsert_documents(BENVALE,[{'xml':nfe(SHPS,'SHPS TECNOLOGIA E SERVICOS LTDA','99999999000191','CLIENTE QUALQUER',7),'family':'nfe'}])
assert m.db_get_company_name(BENVALE)=='BENVALE LTDA'            # nota em que a empresa não é parte não muda o nome
# --- repositório: a pasta acompanha o nome correto
tmp=Path(tempfile.mkdtemp(prefix='exato_v174_srv_')); servidor=tmp/'srv'; servidor.mkdir()
c=sqlite3.connect(m.DB_PATH); c.execute("UPDATE companies SET name='SHPS TECNOLOGIA E SERVICOS LTDA' WHERE cnpj=?",(BENVALE,)); c.commit(); c.close()    # volta ao nome errado
db=str(m.DB_PATH)
R.copiar_pendentes(db,str(servidor))                           # sem nome verificado: usa o nome do cadastro (errado) na primeira vez
rep=servidor/'Repositório'; velho=f'SHPS TECNOLOGIA E SERVICOS LTDA - {BENVALE}'; novo=f'BENVALE LTDA - {BENVALE}'
assert (rep/velho).is_dir() and not (rep/novo).exists()
arquivos=sorted(p.name for p in (rep/velho).rglob('*.xml')); assert arquivos
# nome NÃO verificado: a pasta existente não é mexida (evita vai-e-volta entre computadores)
R.copiar_pendentes(db,str(servidor),nome_empresa=lambda c,n:('OUTRO NOME QUALQUER',False)); assert (rep/velho).is_dir() and not (rep/novo).exists()
# nome verificado: a pasta é renomeada com todos os arquivos e os caminhos do banco acompanham
R.copiar_pendentes(db,str(servidor),nome_empresa=lambda c,n:('BENVALE LTDA',True))
assert (rep/novo).is_dir() and not (rep/velho).exists() and sorted(p.name for p in (rep/novo).rglob('*.xml'))==arquivos
cam=[r[0] for r in sqlite3.connect(db).execute("SELECT caminho FROM repositorio_copias WHERE caminho IS NOT NULL AND caminho<>''")]
assert cam and all(x.startswith(f'Repositório/{novo}/') for x in cam),cam[:2]
assert R.verificar(db,str(servidor),amostra=1000)==[] and R.pendentes(db)==0
# as duas pastas existem (dois computadores criaram com nomes diferentes): une tudo na correta, sem perder nada
(rep/velho/'2026'/'09'/'NF-e').mkdir(parents=True); (rep/velho/'2026'/'09'/'NF-e'/'so_no_velho.xml').write_bytes(b'<x/>')
R.copiar_pendentes(db,str(servidor),nome_empresa=lambda c,n:('BENVALE LTDA',True))
assert not (rep/velho).exists() and (rep/novo/'2026'/'09'/'NF-e'/'so_no_velho.xml').exists()
# nomes longos: até 60 letras
assert R.nome_seguro('A'*100)=='A'*60 and R.nome_seguro('a/b:c*')=='a b c'
shutil.rmtree(tmp,ignore_errors=True); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 nome da empresa: OK')
