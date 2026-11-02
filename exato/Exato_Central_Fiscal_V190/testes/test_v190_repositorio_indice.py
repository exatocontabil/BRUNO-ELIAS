"""V169: o Repositório mostra OS MESMOS números em todos os computadores (índice no servidor), "Copiar agora" ignora a pausa de erro,
motivos em português e máquina nova só confere."""
import os, sys, sqlite3, tempfile, shutil, json, time
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_repositorio as R
tmp=Path(tempfile.mkdtemp(prefix='exato_v174_idx_')); servidor=tmp/'srv'; servidor.mkdir()
CNPJ='11222333000181'
def banco(nome,docs,empresa='ELETROTAK MANUTENCAO LTDA'):
    db=str(tmp/nome); c=sqlite3.connect(db)
    c.execute("CREATE TABLE companies(cnpj TEXT PRIMARY KEY,name TEXT)")
    c.execute("""CREATE TABLE documents(doc_id TEXT PRIMARY KEY,cnpj TEXT,family TEXT,doc_type TEXT,direction TEXT,number TEXT,series TEXT,issued_at TEXT,value TEXT,status TEXT,access_key TEXT,source_nsu TEXT,xml BLOB,first_seen_at TEXT,last_seen_at TEXT)""")
    c.execute("INSERT INTO companies VALUES(?,?)",(CNPJ,empresa))
    for i,data in docs:
        c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,issued_at,status,access_key,xml,first_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (f'd{i}',CNPJ,'nfe','NF-e','Saída',data,'Autorizado','%044d'%i,f'<nfe n="{i}"/>'.encode(),'2026-10-01T10:00:00'))
    c.commit(); c.close(); return db
# computador A tem as notas 1-5 de setembro; computador B tem as notas 4-8 (3 repetidas) de setembro e outubro
A=banco('a.db',[(i,'2026-09-10T10:00:00') for i in range(1,6)])
B=banco('b.db',[(i,'2026-09-10T10:00:00') for i in (4,5,6)]+[(i,'2026-10-02T10:00:00') for i in (7,8)])

# --- A copia as suas notas; B ainda não copiou nada
assert R.copiar_pendentes(A,str(servidor))['novos']==5
cacheA=str(tmp/'cacheA.json'); cacheB=str(tmp/'cacheB.json')
ia=R.atualizar_indice(A,str(servidor),computador='PC-A',cache=cacheA); assert ia
ta=R.indice_totais(ia); assert ta['xmls']==5 and ta['faltam']==0 and ta['empresas']==1 and ta['diferentes']==0,ta
# --- B (que tem 3 documentos que A não tem) publica o que conhece SEM varrer o servidor: os dois passam a ver "faltam"
assert R.publicar_conhecidos(B,str(servidor),computador='PC-B',cache=cacheB)
ib,origem=R.ler_indice(str(servidor),cacheB); assert origem=='servidor'
tb=R.indice_totais(ib); assert tb['xmls']==5 and tb['conhecidos']==7 and tb['faltam']==2,tb       # por mês vale o MAIOR número conhecido: setembro 5 (A) e outubro 2 (B)
ia2,_=R.ler_indice(str(servidor),cacheA); assert R.indice_totais(ia2)==tb and R.indice_linhas(ia2)==R.indice_linhas(ib)       # A e B mostram o MESMO
# --- B copia o que tem e o índice refeito por QUALQUER computador dá o mesmo resultado
r=R.copiar_pendentes(B,str(servidor)); assert r['novos']==3 and r['existentes']==2,r         # 4 e 5 já estavam lá (copiados por A)
for banco_, pc, cache in ((A,'PC-A',cacheA),(B,'PC-B',cacheB)):
    ind=R.atualizar_indice(banco_,str(servidor),computador=pc,cache=cache); t=R.indice_totais(ind)
    assert t['xmls']==8 and t['faltam']==0 and t['conhecidos']==8 and t['meses']==2,t
linhas=R.indice_linhas(R.ler_indice(str(servidor))[0]); assert linhas==[(CNPJ,'ELETROTAK MANUTENCAO LTDA','2026-10',2,2),(CNPJ,'ELETROTAK MANUTENCAO LTDA','2026-09',6,6)],linhas      # mais recente primeiro
assert (servidor/'Repositório'/R.PASTA_INDICE/R.ARQ_INDICE).exists() and not list((servidor/'Repositório'/R.PASTA_INDICE).glob('.*tmp'))
# o índice não atrapalha o resto (restaurar, prazo, nome das pastas)
assert all('.indice' not in c for _,_,c in R.listar_para_restaurar(str(servidor))) and R.vencidos(str(servidor),12)['arquivos']==0
# idade do índice
assert R.indice_idade(ia2)<60 and R.indice_idade({})==float('inf')
# sem acesso ao servidor: usa a última cópia local (e diz de onde veio)
ind,origem=R.ler_indice(str(tmp/'fora'),cacheA); assert origem=='local' and R.indice_totais(ind)['xmls']==8
assert R.ler_indice(str(tmp/'fora'),str(tmp/'nao.json'))==(None,'')
# contagem incompleta (erro de rede no meio) NÃO vira número errado
_v=R._varrer_pasta
def quebrada(pasta,falhas=None):
    r=_v(pasta,falhas)
    if falhas is not None and Path(str(pasta)).name=='09': falhas.append(OSError('rede caiu'))
    return r
R._varrer_pasta=quebrada; assert R.atualizar_indice(A,str(servidor),computador='PC-A') is None; R._varrer_pasta=_v
assert R.indice_totais(R.ler_indice(str(servidor))[0])['xmls']==8          # o índice bom continua lá
# --- conteúdo diferente: arquivo chave.<8 letras>.xml ao lado entra na contagem e na lista, sem inflar "no servidor"
c=sqlite3.connect(A); c.execute("UPDATE documents SET xml=? WHERE doc_id='d1'",(b'<nfe n="1" outro="sim"/>',)); c.execute("DELETE FROM repositorio_copias WHERE doc_id='d1'"); c.commit(); c.close()
r=R.copiar_pendentes(A,str(servidor)); assert r['diferentes']==1,r
ind=R.atualizar_indice(A,str(servidor),computador='PC-A',cache=cacheA); t=R.indice_totais(ind)
assert t['diferentes']==1 and t['xmls']==8 and t['faltam']==0,t
assert len(ind['diferentes'])==1 and ind['diferentes'][0]['mes']=='2026-09' and ind['diferentes'][0]['tamanho_original']==len(b'<nfe n="1"/>') and ind['diferentes'][0]['arquivo'].endswith('.xml')
assert R.indice_totais(R.ler_indice(str(servidor),cacheB)[0])==t          # B vê o mesmo
# --- prazo: meses apagados do servidor deixam de contar como "faltam" em todos os computadores
c=sqlite3.connect(A); c.execute("UPDATE documents SET issued_at='2020-01-10T10:00:00' WHERE doc_id='d2'"); c.execute("DELETE FROM repositorio_copias WHERE doc_id='d2'"); c.commit(); c.close()
R.copiar_pendentes(A,str(servidor)); R.atualizar_indice(A,str(servidor),computador='PC-A')
assert any(l[2]=='2020-01' for l in R.indice_linhas(R.ler_indice(str(servidor))[0]))
info=R.apagar_vencidos(A,str(servidor),12); assert info['arquivos']==1
idx,_=R.ler_indice(str(servidor)); assert not any(l[2]=='2020-01' for l in R.indice_linhas(idx)) and R.indice_totais(idx)['faltam']==0
# B (que ainda conhece o documento de 2020 no seu banco) refaz o índice: continua sem "faltar"
c=sqlite3.connect(B); c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,issued_at,status,access_key,xml,first_seen_at) VALUES('d2',?,?,?,?,?,?,?,?,?)",(CNPJ,'nfe','NF-e','Saída','2020-01-10T10:00:00','Autorizado','%044d'%2,b'<nfe n="2"/>','2026-10-01')); c.commit(); c.close()
ind=R.atualizar_indice(B,str(servidor),computador='PC-B'); assert R.indice_totais(ind)['faltam']==0 and not any(l[2]=='2020-01' for l in R.indice_linhas(ind))

# --- erros em português claro
assert 'permissão' in R.erro_amigavel(PermissionError(13,'Permission denied')) and 'não respondeu' in R.erro_amigavel(OSError(53,'x'))
assert 'espaço' in R.erro_amigavel(OSError(28,'No space left')) and 'em uso' in R.erro_amigavel('[WinError 32] O arquivo está sendo usado em uso')
assert R.erro_amigavel(R.erro_amigavel(OSError('qualquer coisa estranha')))==R.erro_amigavel(OSError('outra coisa')) and 'WinError' not in R.erro_amigavel('[WinError 9999] bobagem')
# "Copiar agora" tenta já de novo o que falhou há pouco; a cópia automática respeita a pausa de 1 hora
C=banco('c.db',[(i,'2026-09-10T10:00:00') for i in (21,22)]); srv2=tmp/'srv2'; srv2.mkdir()
orig=R.copiar_arquivo
def falha(*a,**k): raise PermissionError(13,'Permission denied')
R.copiar_arquivo=falha
r=R.copiar_pendentes(C,str(srv2)); assert r['erros']>=1 and not r['ok'] or r['erros']==2
s=R.resumo(C); assert s['fila']==2 and s['erros']==2 and s['motivos'] and 'permissão' in s['motivos'][0][0] and s['motivos'][0][1]==2 and s['proxima_tentativa'],s
R.copiar_arquivo=orig
r=R.copiar_pendentes(C,str(srv2)); assert r['novos']==0 and R.resumo(C)['fila']==2          # pausa de 1 hora: o automático não tenta
r=R.copiar_pendentes(C,str(srv2),ignorar_pausa=True); assert r['novos']==2 and R.resumo(C)['fila']==0 and not R.resumo(C)['motivos'],r        # "Copiar agora"
# o que falha DURANTE a rodada manual não fica em repetição infinita
R.copiar_arquivo=falha; D=banco('d.db',[(31,'2026-09-10T10:00:00')]); t0=time.time()
r=R.copiar_pendentes(D,str(srv2),ignorar_pausa=True); R.copiar_arquivo=orig; assert time.time()-t0<10 and r['erros']==1
# máquina nova (todos os XMLs já no servidor): só confere, não copia de novo, e diz isso
E=banco('e.db',[(i,'2026-09-10T10:00:00') for i in (21,22)]); r=R.copiar_pendentes(E,str(srv2)); assert r['existentes']==2 and r['novos']==0 and R.resumo(E)['fila']==0
shutil.rmtree(tmp,ignore_errors=True)
print('V169 repositório (índice, erros, copiar agora): OK')
