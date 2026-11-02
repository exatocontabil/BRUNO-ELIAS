"""V169: Box-e com mensagens de erro separadas (servidor não achado, porta bloqueada, senha), servidor sugerido pelo e-mail, aviso de e-mail no campo
Servidor e teste da conexão por etapas."""
import socket, smtplib, ssl, sys, threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import exato_boxe as B

class Smtp:
    def __init__(self,auth_ok=True):
        self.auth_ok=auth_ok; self.sock=socket.socket(); self.sock.bind(('127.0.0.1',0)); self.sock.listen(5); self.porta=self.sock.getsockname()[1]; self.ativo=True
        threading.Thread(target=self._loop,daemon=True).start()
    def _loop(self):
        while self.ativo:
            try: c,_=self.sock.accept()
            except OSError: return
            threading.Thread(target=self._atende,args=(c,),daemon=True).start()
    def _atende(self,c):
        f=c.makefile('rwb'); w=lambda t:(f.write((t+'\r\n').encode()),f.flush()); w('220 falso')
        try:
            while True:
                l=f.readline().decode(errors='replace').rstrip('\r\n')
                if not l: break
                u=l.upper()
                if u.startswith('EHLO'): w('250-falso'); w('250 AUTH PLAIN')
                elif u.startswith('AUTH'): w('235 ok' if self.auth_ok else '535 5.7.8 senha errada')
                elif u=='QUIT': w('221 tchau'); break
                else: w('250 ok')
        finally: c.close()
    def parar(self): self.ativo=False; self.sock.close()

# --- mensagens separadas
m=B.erro_amigavel
assert 'senha de aplicativo' in m(smtplib.SMTPAuthenticationError(535,b'x'))
assert 'Não achei o servidor' in m(socket.gaierror(-2,'Name or service not known')) and 'smtp.gmail.com' in m(socket.gaierror(-2,'x'))
assert 'não respondeu a tempo' in m(socket.timeout()) and '465' in m(socket.timeout())
assert 'recusada' in m(ConnectionRefusedError(111,'Connection refused')) and 'antivírus' in m(ConnectionRefusedError(111,'x'))
assert 'caiu' in m(smtplib.SMTPServerDisconnected('x')) and 'conexão segura' in m(ssl.SSLError('x'))
assert len({m(socket.gaierror(-2,'x')),m(socket.timeout()),m(ConnectionRefusedError(111,'x')),m(smtplib.SMTPServerDisconnected('x'))})==4
assert 'Não consegui conectar' not in m(OSError('x')) and 'WinError' not in m(OSError(10061,'WinError 10061'))
# --- servidor sugerido pelo e-mail e aviso no campo Servidor
assert B.servidor_sugerido('exato.ararangua@gmail.com')==('smtp.gmail.com',587,'STARTTLS') and B.servidor_sugerido('x@Outlook.com')[0]=='smtp.office365.com' and B.servidor_sugerido('x@hotmail.com')[0]=='smtp.office365.com'
assert B.servidor_sugerido('x@empresa.com.br') is None and B.servidor_sugerido('sem-arroba') is None and B.servidor_sugerido('')is None
assert 'smtp.gmail.com' in B.conferir_servidor('exato.ararangua@gmail.com') and 'não o e-mail' in B.conferir_servidor('a@b.com')
assert B.conferir_servidor('smtp.gmail.com')=='' and B.conferir_servidor('')=='' and 'sem espaços' in B.conferir_servidor('https://smtp.x.com') and B.conferir_servidor('smtp.x.com:587')
# --- teste por etapas
ok=Smtp(); cfg={'servidor':'127.0.0.1','porta':ok.porta,'seguranca':'NENHUMA','usuario':'a@b.com','senha':'x'}
et=B.testar_conexao(cfg); assert [e[0] for e in et]==['Achar o servidor','Abrir a porta %d'%ok.porta,'Conexão segura','Usuário e senha'] and all(e[1] for e in et),et
ruim=Smtp(auth_ok=False); et=B.testar_conexao(dict(cfg,porta=ruim.porta)); assert et[-1][0]=='Usuário e senha' and not et[-1][1] and 'senha de aplicativo' in et[-1][2] and all(e[1] for e in et[:-1]),et
ok.parar(); ruim.parar()
fechada=socket.socket(); fechada.bind(('127.0.0.1',0)); porta=fechada.getsockname()[1]; fechada.close()
et=B.testar_conexao(dict(cfg,porta=porta)); assert et[-1][0].startswith('Abrir a porta') and not et[-1][1] and ('recusada' in et[-1][2] or 'antivírus' in et[-1][2]) and len(et)==2,et
et=B.testar_conexao(dict(cfg,servidor='servidor-que-nao-existe.invalid')); assert et[-1][0]=='Achar o servidor' and not et[-1][1] and 'Não achei o servidor' in et[-1][2],et
et=B.testar_conexao(dict(cfg,servidor='exato@gmail.com')); assert et[0][0]=='Endereço do servidor' and not et[0][1] and 'smtp.gmail.com' in et[0][2]
et=B.testar_conexao(dict(cfg,servidor='')); assert not et[0][1]
print('V169 Box-e (erros, servidor sugerido, teste por etapas): OK')
