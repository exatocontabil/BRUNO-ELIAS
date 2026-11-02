"""V169 (tela): Repositório com os números do servidor (iguais em todos os computadores), motivo da fila em português, lista dos "diferentes",
máquina nova só confere; diálogo do Box-e com servidor sugerido, aviso e teste da conexão."""
import os, sys, sqlite3, tempfile, shutil, time, json, socket, threading
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_idxui_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import tkinter as tk
from tkinter import ttk
import exato_central_fiscal as m
import exato_repositorio as R
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaIdx#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaIdx#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
CNPJ='11222333000181'; m.db_register_company(CNPJ,'ELETROTAK MANUTENCAO LTDA')
c=sqlite3.connect(m.DB_PATH)
c.executemany("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              [(f'n{i}',CNPJ,'nfe','NF-e','Saída',str(i),'2026-09-10T10:00:00','Autorizado','%044d'%i,b'<nfe n="%d"/>'%i,'2026-10-01T10:00:00','2026-10-01T10:00:00') for i in range(1,7)]); c.commit(); c.close()
srv=Path(tempfile.mkdtemp(prefix='exato_v174_srvidx_'))
app=m.App(current_user=user); toasts=[]; app._toast=lambda t,k='info',ms=0: toasts.append((t,k))
avisos=[]; m.messagebox.showinfo=lambda *a,**k: avisos.append(a); m.messagebox.showwarning=lambda *a,**k: avisos.append(a)
import traceback
app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
def esperar(cond,t=20):
    fim=time.time()+t
    while time.time()<fim:
        app.update()
        if cond(): return True
        time.sleep(.03)
    return False
def achar(w,texto):
    for x in w.winfo_children():
        try:
            if str(x.cget('text'))==texto: return x
        except Exception: pass
        r=achar(x,texto)
        if r is not None: return r
try:
    app.geometry('1366x650+0+0'); app.update(); cfg=app._repo_cfg(); cfg['pasta']=str(srv)
    # ---- máquina nova: 6 XMLs já estão no servidor (copiados por outro computador); este só confere
    for i in range(1,7):
        p=srv/'Repositório'/f'ELETROTAK MANUTENCAO LTDA - {CNPJ}'/'2026'/'09'/'NF-e'/'Saída'; p.mkdir(parents=True,exist_ok=True); (p/('%044d.xml'%i)).write_bytes(b'<nfe n="%d"/>'%i)
    app._show_repo(); app.update()
    app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'] and not app._repo_indice_rodando)
    assert any('já estavam no servidor' in t and 'nada foi copiado de novo' in t for t,_ in toasts),toasts
    app._repo_refresh_view(); esperar(lambda: app.repo_tiles['xmls'].cget('text')=='6',8); app.update()
    assert app.repo_tiles['xmls'].cget('text')=='6' and app.repo_tiles['empresas'].cget('text')=='1' and app.repo_tiles['faltam'].cget('text')=='0' and app.repo_tiles['diferentes'].cget('text')=='0'
    assert 'Tudo guardado' in app.repo_status_title.cget('text') and 'iguais em todos os computadores' in app.repo_indice_label.cget('text')
    app._repo_refresh_view(); assert esperar(lambda: not app.repo_local_label.winfo_ismapped(),8)          # (a tela termina de se atualizar logo depois do fim da cópia)
    # ---- OUTRO computador avisa (pelo índice) que tem 4 documentos de outubro que ainda não chegaram: esta tela mostra o mesmo "Ainda faltam 4"
    idx,_=R.ler_indice(str(srv)); idx['computador']='PC-DO-JONATHA'; idx['empresas'][CNPJ]['meses']['2026-10']={'conhecidos':4,'no_servidor':0,'diferentes':0}
    R._gravar_indice(str(srv),idx,'PC-DO-JONATHA'); app._repo_indice_iniciar(forcar=False); assert esperar(lambda: not app._repo_indice_rodando)
    esperar(lambda: app.repo_tiles['faltam'].cget('text')!='0',8); app.update()
    # (o índice é refeito se tiver mais de 5 minutos; aqui é novo, então vale o que o outro computador escreveu)
    assert app.repo_tiles['faltam'].cget('text')=='4' and 'Faltam 4' in app.repo_status_title.cget('text') and 'PC-DO-JONATHA' in app.repo_indice_label.cget('text'),(app.repo_tiles['faltam'].cget('text'),app.repo_status_title.cget('text'),app.repo_indice_label.cget('text'))
    app._repo_filtrar_pendentes(); app.update(); filhos=app.repo_tree.get_children(); assert len(filhos)==1 and '2026-10' in app.repo_tree.item(filhos[0],'values')      # filtro do que falta
    app._repo_limpar_filtros()
    # ---- servidor some: mostra a última leitura e avisa
    cfg['pasta']=str(srv/'fora'); app._repo_indice_ultimo=0; app._repo_indice_iniciar(); assert esperar(lambda: not app._repo_indice_rodando)
    app._repo_refresh_view(); esperar(lambda: 'não respondeu' in app.repo_indice_label.cget('text'),8); app.update(); assert 'não respondeu' in app.repo_indice_label.cget('text') and app.repo_tiles['xmls'].cget('text')=='6'
    cfg['pasta']=str(srv)
    # ---- motivo da fila em português e "Copiar agora" tenta de novo
    c=sqlite3.connect(m.DB_PATH); c.execute("INSERT INTO documents(doc_id,cnpj,family,doc_type,direction,number,issued_at,status,access_key,xml,first_seen_at,last_seen_at) VALUES('nx',?,?,?,?,?,?,?,?,?,?,?)",(CNPJ,'nfe','NF-e','Saída','77','2026-10-05T10:00:00','Autorizado','%044d'%77,b'<nfe n="77"/>','2026-10-06T10:00:00','2026-10-06T10:00:00')); c.commit(); c.close()
    orig=R.copiar_arquivo
    def falha(*a,**k): raise PermissionError(13,'Permission denied')
    R.copiar_arquivo=falha; app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'])
    app._repo_refresh_view(); esperar(lambda: app.repo_local_label.winfo_ismapped(),8); app.update()
    txt=app.repo_local_label.cget('text'); assert 'Neste computador' in txt and 'permissão' in txt and 'Nova tentativa automática' in txt and 'Copiar agora' in txt and 'Errno' not in txt,txt
    R.copiar_arquivo=orig; app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'])
    app._repo_refresh_view(); app.update(); assert (srv/'Repositório'/f'ELETROTAK MANUTENCAO LTDA - {CNPJ}'/'2026'/'10'/'NF-e'/'Saída'/('%044d.xml'%77)).exists()
    # ---- conteúdo diferente: a lista abre e mostra os dois arquivos
    c=sqlite3.connect(m.DB_PATH); c.execute("UPDATE documents SET xml=? WHERE doc_id='n1'",(b'<nfe n="1" mudou="sim"/>',)); c.execute("DELETE FROM repositorio_copias WHERE doc_id='n1'"); c.commit(); c.close()
    app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'] and not app._repo_indice_rodando)
    app._repo_indice_iniciar(forcar=True); assert esperar(lambda: not app._repo_indice_rodando); app._repo_refresh_view(); esperar(lambda: app.repo_tiles['diferentes'].cget('text')=='1',8); app.update()
    assert app.repo_tiles['diferentes'].cget('text')=='1'
    app._repo_diferentes_dialog(); app.update(); win=app._repo_dif_win; assert win.winfo_exists()
    arv=[w for w in win.winfo_children() if isinstance(w,tk.Frame)][0].winfo_children()[0]; fila=arv.get_children(); assert len(fila)==1 and arv.item(fila[0],'values')[2].startswith('…') and '8 / 2' not in arv.item(fila[0],'values')[3]
    achar(win,'Fechar').invoke(); app.update(); assert not win.winfo_exists()
    # ---- relógio adiantado: aviso claro
    c=sqlite3.connect(m.DB_PATH); c.execute("UPDATE repositorio_copias SET copiado_em=? WHERE copiado_em IS NOT NULL",((datetime.now()+timedelta(hours=1)).isoformat(timespec='seconds'),)); c.commit(); c.close()
    app._repo_refresh_view(); esperar(lambda: 'relógio' in app.repo_local_label.cget('text'),8); assert 'relógio' in app.repo_local_label.cget('text')
    # ---- janela estreita e baixa
    app.geometry('1000x600+0+0'); app._show_repo(); app.update(); app.update()

    # ================= Box-e: diálogo com servidor sugerido, aviso e teste da conexão
    class Smtp:
        def __init__(self):
            self.sock=socket.socket(); self.sock.bind(('127.0.0.1',0)); self.sock.listen(5); self.porta=self.sock.getsockname()[1]; self.ativo=True; threading.Thread(target=self._loop,daemon=True).start()
        def _loop(self):
            while self.ativo:
                try: c,_=self.sock.accept()
                except OSError: return
                threading.Thread(target=self._atende,args=(c,),daemon=True).start()
        def _atende(self,c):
            f=c.makefile('rwb'); w=lambda t:(f.write((t+'\r\n').encode()),f.flush()); w('220 falso')
            try:
                while True:
                    l=f.readline().decode(errors='replace').rstrip('\r\n'); u=l.upper()
                    if not l: break
                    if u.startswith('EHLO'): w('250-falso'); w('250 AUTH PLAIN')
                    elif u.startswith('AUTH'): w('535 5.7.8 senha errada')
                    elif u=='QUIT': w('221 tchau'); break
                    else: w('250 ok')
            finally: c.close()
    smtp=Smtp()
    app._boxe_dialog(); app.update(); win=app._boxe_win
    grade=[f for f in win.winfo_children() if isinstance(f,tk.Frame) and len([w for w in f.winfo_children() if isinstance(w,(ttk.Entry,ttk.Combobox))])>=7][0]
    ent=sorted([w for w in grade.winfo_children() if isinstance(w,(ttk.Entry,ttk.Combobox))],key=lambda w:int(w.grid_info()['row']))
    avisoslb=win._aviso_srv
    # digitar o e-mail do Gmail preenche servidor, porta e segurança e o remetente
    ent[4].insert(0,'exato.ararangua@gmail.com'); app.update()
    assert ent[1].get()=='smtp.gmail.com' and ent[2].get()=='587' and ent[3].get()=='STARTTLS' and ent[6].get()=='exato.ararangua@gmail.com',[e.get() for e in ent]
    # provedor muda enquanto digita: não deixa um servidor que não é daquele e-mail
    ent[4].delete(0,'end'); ent[4].insert(0,'a@live.com'); app.update(); assert ent[1].get()=='smtp.office365.com'
    ent[4].insert('end','.mycorp'); app.update(); assert ent[1].get()==''
    ent[4].delete(0,'end'); ent[4].insert(0,'exato.ararangua@gmail.com'); app.update(); assert ent[1].get()=='smtp.gmail.com'
    # colocar o e-mail no campo do servidor: aviso claro
    ent[1].delete(0,'end'); ent[1].insert(0,'exato.ararangua@gmail.com'); app.update(); assert 'não o e-mail' in avisoslb.cget('text') and 'smtp.gmail.com' in avisoslb.cget('text')
    ent[1].delete(0,'end'); ent[1].insert(0,'127.0.0.1'); app.update(); assert avisoslb.cget('text')==''
    ent[2].delete(0,'end'); ent[2].insert(0,str(smtp.porta)); ent[3].set('NENHUMA'); ent[5].insert(0,'senha-comum')
    msg=[w for w in win.winfo_children() if isinstance(w,tk.Label) and w.cget('wraplength')==520][-1]
    achar(win,'Testar a conexão').invoke()
    assert esperar(lambda: 'Usuário e senha' in msg.cget('text'),10),msg.cget('text')
    t=msg.cget('text'); assert 'senha de aplicativo' in t and 'Achar o servidor' not in t.split('✗')[-1] and 'Não consegui conectar' not in t,t
    achar(win,'Cancelar').invoke(); smtp.ativo=False; smtp.sock.close()
finally:
    app.destroy(); shutil.rmtree(srv,ignore_errors=True); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 Repositório e Box-e (tela): OK')
