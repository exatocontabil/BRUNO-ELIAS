"""V168: Enviar Box-e no programa (tela NFS-e, diálogo de e-mail, envio automático)."""
import os, sys, socket, sqlite3, tempfile, shutil, threading, time, email, json
from email import policy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_boxeui_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import tkinter as tk
from tkinter import ttk
import exato_central_fiscal as m
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
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaBox#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaBox#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
CNPJ='11222333000181'; m.db_register_company(CNPJ,'PRESTADORA SERVICOS LTDA')
c=sqlite3.connect(m.DB_PATH)
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'n{i}',CNPJ,'nfse','NFS-e','Saída',str(i),'2026-09-10T10:00:00','Autorizado','%050d'%i,b'<NFSe n="%d"/>'%i,'2020-01-01T00:00:00','2020-01-01T00:00:00') for i in range(1,8)]); c.commit(); c.close()
srv=Path(tempfile.mkdtemp(prefix='exato_v174_srvbox_'))
app=m.App(current_user=user); toasts=[]; app._toast=lambda t,k='info',ms=0: toasts.append((t,k))
avisos=[]; m.messagebox.showinfo=lambda *a,**k: avisos.append(a); m.messagebox.showwarning=lambda *a,**k: avisos.append(a); m.messagebox.showerror=lambda *a,**k: avisos.append(a)
def esperar(cond,t=15):
    fim=time.time()+t
    while time.time()<fim:
        app.update()
        if cond(): return True
        time.sleep(.02)
    return False
def achar(w,texto):
    for x in w.winfo_children():
        try:
            if str(x.cget('text'))==texto: return x
        except Exception: pass
        r=achar(x,texto)
        if r is not None: return r
try:
    app.geometry('1366x650+0+0'); app.update(); app._repo_cfg()['pasta']=str(srv)
    app._show_nfse(); app.update()
    cfg=app._boxe_cfg(); assert cfg['destino']=='exatoara@dominioboxe.com.br' and not cfg['ativo'] and not app._boxe_pronto()
    assert 'falta configurar' in app.boxe_status_label.cget('text')
    # ligar sem configurar: abre o diálogo e a opção volta para desligada
    app.boxe_ativo_var.set(True); app._boxe_toggle(); app.update()
    win=app._boxe_win; assert win.winfo_exists() and not app.boxe_ativo_var.get() and not cfg['ativo']
    # campo vazio: não salva e explica
    achar(win,'Salvar e ligar').invoke(); app.update(); assert win.winfo_exists() and not cfg['ativo']
    grade=[f for f in win.winfo_children() if isinstance(f,tk.Frame) and len([w for w in f.winfo_children() if isinstance(w,(ttk.Entry,ttk.Combobox))])>=7][0]
    entradas=sorted([w for w in grade.winfo_children() if isinstance(w,(ttk.Entry,ttk.Combobox))],key=lambda w:int(w.grid_info()['row']))
    assert len(entradas)>=7
    vals={0:'exatoara@dominioboxe.com.br',1:'127.0.0.1',2:str(smtp.porta),3:'NENHUMA',4:'exato@exemplo.com',5:'segredo',6:'exato@exemplo.com'}
    for i,w in vals.items():
        if isinstance(entradas[i],ttk.Combobox): entradas[i].set(w)
        else: entradas[i].delete(0,'end'); entradas[i].insert(0,w)
    # teste de envio (vai para o remetente, não para o Box-e)
    achar(win,'Enviar e-mail de teste').invoke(); esperar(lambda: len(smtp.msgs)==1,4); assert esperar(lambda: len(smtp.msgs)==1) and smtp.msgs[0][0]==['exato@exemplo.com']
    # salvar e ligar: por padrão NÃO manda o histórico (as 7 NFS-e que já estavam guardadas), só as novas daqui para frente
    achar(win,'Salvar e ligar').invoke(); app.update()
    assert cfg['ativo'] and cfg['senha_protegida'] and cfg['senha_protegida']!='segredo' and app.boxe_ativo_var.get() and app._boxe_pronto() and cfg['desde'] not in ('','0000')
    esperar(lambda: not app._boxe_state['rodando'],5); time.sleep(.4); app.update(); assert len(smtp.msgs)==1,len(smtp.msgs)       # só o e-mail de teste
    # NFS-e nova: o agendador envia sozinha (e as antigas continuam sem ir)
    agora=time.strftime('%Y-%m-%dT%H:%M:%S',time.localtime(time.time()+5))
    c=sqlite3.connect(m.DB_PATH); c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES('n99',?,?,?,?,?,?,?,?,?,?,?)",(CNPJ,'nfse','NFS-e','Saída','99','2026-09-12T10:00:00','Autorizado','%050d'%99,b'<NFSe n="99"/>',agora,agora)); c.commit(); c.close()
    app._boxe_tick(); assert esperar(lambda: len(smtp.msgs)==2)
    assert smtp.msgs[1][0]==['exatoara@dominioboxe.com.br'] and [a.get_filename() for a in smtp.msgs[1][1].iter_attachments()]==['%050d.xml'%99]
    assert esperar(lambda: any('NFS-e enviada' in t for t,_ in toasts)) and esperar(lambda: not app._boxe_state['rodando'])
    app._boxe_update_label(); assert '1 NFS-e enviada(s)' in app.boxe_status_label.cget('text')
    app._boxe_tick(); esperar(lambda: not app._boxe_state['rodando']); time.sleep(.3); app.update(); assert len(smtp.msgs)==2            # nada reenviado
    # desligar: para de enviar
    app.boxe_ativo_var.set(False); app._boxe_toggle(); assert not cfg['ativo']
    c=sqlite3.connect(m.DB_PATH); c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES('n100',?,?,?,?,?,?,?,?,?,?,?)",(CNPJ,'nfse','NFS-e','Saída','100','2026-09-13T10:00:00','Autorizado','%050d'%100,b'<NFSe n="100"/>',agora,agora)); c.commit(); c.close()
    app._boxe_tick(); app.update(); time.sleep(.3); assert len(smtp.msgs)==2
    # servidor de e-mail fora do ar: um aviso em português claro, sem janela
    app.boxe_ativo_var.set(True); app._boxe_toggle(); smtp.derrubar=True; toasts.clear()
    assert esperar(lambda: any('Box-e:' in t and ('conex' in t.lower() or 'servidor' in t.lower()) for t,_ in toasts),10),toasts
    assert not avisos
finally:
    smtp.parar(); app.destroy(); shutil.rmtree(srv,ignore_errors=True); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 Box-e UI: OK')
