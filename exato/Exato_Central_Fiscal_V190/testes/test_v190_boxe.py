"""V168: envio automático de NFS-e para o Box-e: nunca reenvia, um único computador envia cada nota, falha devolve a nota para a fila."""
import os, sys, socket, sqlite3, tempfile, shutil, threading, time, json, base64, email
from datetime import datetime, timedelta
from email import policy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_boxe as B
import exato_repositorio as R

# ---------- servidor de e-mail de mentira (guarda as mensagens recebidas)
class SmtpFalso:
    def __init__(self):
        self.msgs=[]; self.sock=socket.socket(); self.sock.bind(('127.0.0.1',0)); self.sock.listen(5); self.porta=self.sock.getsockname()[1]; self.rodando=True; self.derrubar=False
        threading.Thread(target=self._loop,daemon=True).start()
    def _loop(self):
        while self.rodando:
            try: c,_=self.sock.accept()
            except OSError: return
            threading.Thread(target=self._atende,args=(c,),daemon=True).start()
    def _atende(self,c):
        f=c.makefile('rwb'); w=lambda t: (f.write((t+'\r\n').encode()),f.flush())
        if self.derrubar: w('421 servidor indisponível'); c.close(); return
        w('220 falso ESMTP'); remetente=''; dest=[]
        try:
            while True:
                linha=f.readline().decode(errors='replace').rstrip('\r\n')
                if not linha: break
                cmd=linha.upper()
                if cmd.startswith('EHLO'): w('250-falso'); w('250-AUTH PLAIN'); w('250 8BITMIME')
                elif cmd.startswith('AUTH PLAIN'): w('235 ok')
                elif cmd.startswith('MAIL FROM'): remetente=linha; dest=[]; w('250 ok')
                elif cmd.startswith('RCPT TO'): dest.append(linha.split(':',1)[1].strip(' <>')); w('250 ok')
                elif cmd=='DATA':
                    w('354 envie'); dados=[]
                    while True:
                        l=f.readline().decode(errors='replace')
                        if l.rstrip('\r\n')=='.': break
                        dados.append(l[1:] if l.startswith('..') else l)
                    self.msgs.append((dest,email.message_from_string(''.join(dados),policy=policy.default))); w('250 recebido')
                elif cmd=='QUIT': w('221 tchau'); break
                else: w('250 ok')
        finally: c.close()
    def parar(self): self.rodando=False; self.sock.close()
smtp=SmtpFalso()
tmp=Path(tempfile.mkdtemp(prefix='exato_v174_boxe_')); servidor=tmp/'srv'; servidor.mkdir()
CFG={'destino':B.DESTINO_PADRAO,'servidor':'127.0.0.1','porta':smtp.porta,'seguranca':'NENHUMA','usuario':'exato@exemplo.com','senha':'segredo','remetente':'exato@exemplo.com'}
def novo_banco(nome):
    db=str(tmp/nome); c=sqlite3.connect(db)
    c.execute("CREATE TABLE companies(cnpj TEXT PRIMARY KEY,name TEXT)")
    c.execute("""CREATE TABLE documents(doc_id TEXT PRIMARY KEY,cnpj TEXT,family TEXT,doc_type TEXT,direction TEXT,number TEXT,series TEXT,issued_at TEXT,value TEXT,status TEXT,access_key TEXT,source_nsu TEXT,xml BLOB,first_seen_at TEXT,last_seen_at TEXT)""")
    c.execute("INSERT INTO companies VALUES('11222333000181','PRESTADORA SERVICOS LTDA')"); c.commit(); c.close(); return db
def nota(db,i,direcao='Saída',mes='2026-09',status='Autorizado',fam='nfse',chave=None):
    c=sqlite3.connect(db); k=chave or ('%050d'%i)
    c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (f'd{i}','11222333000181',fam,'NFS-e' if status!='Evento' else 'Evento',direcao if status!='Evento' else '',str(i),mes+'-10T10:00:00',status,k,b'<NFSe n="%d"/>'%i,'x','x')); c.commit(); c.close()
db=novo_banco('pc1.db')
for i in range(1,46): nota(db,i)                                # 45 prestadas em setembro
for i in range(46,51): nota(db,i,mes='2026-10')                 # 5 prestadas em outubro
for i in range(51,54): nota(db,i,direcao='Entrada')             # 3 tomadas (não entram por padrão)
# ---------- envio: lotes de 20 por empresa/mês; só prestadas; marcas no servidor
r=B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1')
assert r['ok'] and r['enviadas']==50 and r['emails']==4 and r['erros']==0,r                  # 20+20+5 (setembro) + 5 (outubro)
assert len(smtp.msgs)==4 and all(d==[B.DESTINO_PADRAO] for d,_ in smtp.msgs)
assunto=[m['Subject'] for _,m in smtp.msgs]; assert all('11222333000181' in a and 'PRESTADORA SERVICOS LTDA' in a for a in assunto) and any('2026-10' in a for a in assunto),assunto
anexos=[a for _,m in smtp.msgs for a in m.iter_attachments()]; assert len(anexos)==50 and all(a.get_filename().endswith('.xml') for a in anexos)
marcas=list((servidor/'Box-e'/'11222333000181').glob('*.json')); assert len(marcas)==50 and all(json.loads(x.read_text())['estado']=='enviado' for x in marcas)
assert B.resumo(db)['enviadas']==50
# ---------- nunca reenvia
n=len(smtp.msgs); r=B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1'); assert r['enviadas']==0 and len(smtp.msgs)==n
# ---------- tomadas só se pedido
r=B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1',incluir_tomadas=True); assert r['enviadas']==3 and len(smtp.msgs)==n+1
# ---------- outro computador (mesmo banco, sem o controle local): não duplica, só marca como enviada
db2=str(tmp/'pc2.db'); shutil.copy(db,db2); c=sqlite3.connect(db2); c.execute("DROP TABLE boxe_envios"); c.commit(); c.close()
n=len(smtp.msgs); r=B.enviar_pendentes(db2,CFG,str(servidor),computador='PC-2',incluir_tomadas=True)
assert r['enviadas']==0 and r['puladas_outro_pc']==53 and len(smtp.msgs)==n and B.resumo(db2)['enviadas']==53,r
# ---------- falha de envio: devolve a vez e volta para a fila; depois da pausa envia
nota(db,60,mes='2026-11'); smtp.derrubar=True
r=B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1'); assert not r['ok'] and r['motivo']=='falha' and r['erros']==1
assert not (servidor/'Box-e'/'11222333000181'/('%050d.json'%60)).exists()                    # a marca foi devolvida
smtp.derrubar=False; n=len(smtp.msgs)
assert B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1')['enviadas']==0                # ainda na pausa de 30 min
c=sqlite3.connect(db); c.execute("UPDATE boxe_envios SET ultima_tentativa='2020-01-01T00:00:00' WHERE doc_id='d60'"); c.commit(); c.close()
r=B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1'); assert r['enviadas']==1 and len(smtp.msgs)==n+1
# ---------- marca "enviando" recente = outro computador está enviando (espera); parada há muito tempo = retoma
nota(db,61,mes='2026-11'); nota(db,62,mes='2026-11')
pasta=servidor/'Box-e'/'11222333000181'
(pasta/('%050d.json'%61)).write_text(json.dumps({'estado':'enviando','por':'PC-9','em':datetime.now().isoformat(timespec='seconds')}))
(pasta/('%050d.json'%62)).write_text(json.dumps({'estado':'enviando','por':'PC-9','em':(datetime.now()-timedelta(hours=2)).isoformat(timespec='seconds')}))
n=len(smtp.msgs); r=B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1'); assert r['enviadas']==1 and len(smtp.msgs)==n+1
nomes=[a.get_filename() for a in list(smtp.msgs[-1][1].iter_attachments())]; assert nomes==['%050d.xml'%62],nomes
# ---------- servidor de arquivos fora do ar: não envia (evita duplicar)
nota(db,70,mes='2026-12'); n=len(smtp.msgs); r=B.enviar_pendentes(db,CFG,str(tmp/'nao_existe'),computador='PC-1'); assert not r['ok'] and r['motivo']=='servidor' and len(smtp.msgs)==n
# ---------- sem configuração
assert B.enviar_pendentes(db,{},str(servidor))['motivo']=='sem_configuracao'
# ---------- cancelada: a nota e o evento de cancelamento seguem
nota(db,80,mes='2027-01',status='Cancelado',chave='8'*50); nota(db,81,mes='2027-01',status='Evento',chave='8'*50)
n=len(smtp.msgs); r=B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1'); assert r['enviadas']>=1
nomes=[a.get_filename() for _,m in smtp.msgs[n:] for a in m.iter_attachments()]; assert any(x.endswith('_evento.xml') for x in nomes) and any(x==('8'*50)+'.xml' for x in nomes),nomes
# ---------- "desde": o histórico anterior à ativação não é enviado
nota(db,90,mes='2027-02'); c=sqlite3.connect(db); c.execute("UPDATE documents SET first_seen_at='2020-01-01T00:00:00' WHERE doc_id='d90'"); c.commit(); c.close()
n=len(smtp.msgs); assert B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1',desde='2026-10-01T00:00:00')['enviadas']==0 and len(smtp.msgs)==n
assert B.enviar_pendentes(db,CFG,str(servidor),computador='PC-1',desde='0000')['enviadas']==1 and len(smtp.msgs)==n+1
# ---------- e-mail de teste vai para o próprio remetente (não incomoda o Box-e)
n=len(smtp.msgs); B.enviar_teste(CFG); assert len(smtp.msgs)==n+1 and smtp.msgs[-1][0]==[CFG['remetente']]
smtp.parar(); shutil.rmtree(tmp,ignore_errors=True)
print('V169 Box-e: OK')
