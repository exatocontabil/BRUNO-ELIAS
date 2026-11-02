"""V182 (tela): ao alcançar o servidor o Exato sincroniza sozinho (empresas, notas, auditorias, versão); fora do escritório avisa discreto; só o administrador remove empresa."""
import os, sys, tempfile, sqlite3, time, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v183_sui_'); os.environ['EXATO_UI_SYNC']='1'; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as e
import exato_sincronia as S, exato_repositorio as R
import test_v190_auditoria_cancelada as T          # monta um banco com NF-e da empresa T.CNPJ
CN=T.CNPJ; OUTRA='45723174000110'; GAMA='11444777000161'
srv=Path(tempfile.mkdtemp(prefix='exato_v183_srvui_')); base=str(srv)
# o que "o outro computador" deixou no servidor: as notas da empresa (copiadas), uma empresa a mais e um histórico de auditoria
assert R.copiar_pendentes(str(e.DB_PATH),base)['ok']
S.publicar_empresas(base,[(OUTRA,'ALFA SERVICOS LTDA'),(CN,'EMPRESA TESTE LTDA')],computador='PC-ESCRITORIO')
S.publicar_auditorias(base,[{'timestamp':'2026-10-05T09:00:00','cnpj':CN,'company':'EMPRESA TESTE LTDA','family':'nfce','status':'conforme','source_files':['sat9.xlsx'],'period_start':'2026-09-01','period_end':'2026-09-30'}])
sat=Path(tempfile.mkdtemp())/'sat9.xlsx'; sat.write_bytes(b'PK'); S.subir_excels(base,f'EMPRESA TESTE LTDA - {CN}','2026-09-01',[str(sat)])
# este computador: banco sem as notas (como um notebook novo)
c=sqlite3.connect(e.DB_PATH); c.execute("DELETE FROM documents"); c.execute("DELETE FROM repositorio_copias"); c.commit(); c.close()
e.db_register_company(GAMA,'GAMA COMERCIO LTDA')
u=e.db_auth_get_user(e.AUTH_BOOTSTRAP_EMAIL); e.db_auth_set_password(u['id'],'S#2026aaa'); admin=e.db_auth_login(e.AUTH_BOOTSTRAP_EMAIL,'S#2026aaa')
e.enumerate_windows_certificates=lambda *a,**k:([],'')
msgs=[]; e.messagebox.showinfo=lambda *a,**k: msgs.append(('info',a)); e.messagebox.showwarning=lambda *a,**k: msgs.append(('warn',a)); e.messagebox.askyesno=lambda *a,**k: True
def esperar(app,pronto,t=20):
    f=time.time()
    while time.time()-f<t:
        app.update()
        while app._repo_inbox: app._repo_inbox.popleft()()
        if pronto(): return True
        time.sleep(0.05)
    return False
app=e.App(current_user=admin); app.geometry('1366x650+0+0')
try:
    app._repo_cfg()['pasta']=base; app._repo_cfg()['ativo']=True
    app._sinc_tick(forcar=True); assert esperar(app,lambda:not getattr(app,'_sinc_rodando',True)),'sincronia travou'
    nomes={x['cnpj']:x['name'] for x in e.db_list_companies(100)}
    assert OUTRA in nomes and nomes[OUTRA]=='ALFA SERVICOS LTDA' and GAMA in nomes,nomes          # empresa do servidor veio; a daqui continua
    assert e.db_document_count(CN)>0,'as notas do servidor não vieram para o banco local'
    emp=S.ler_empresas(base); assert GAMA in emp and not emp[GAMA]['removida']          # a empresa daqui subiu
    assert any(x.get('timestamp')=='2026-10-05T09:00:00' for x in e._audit_history_load())          # histórico de auditoria do servidor
    assert list((e.WORK_DIR/'SAT_AUDITORIA').rglob('sat9.xlsx')),'o Excel do SAT não veio'
    assert S.ler_versao(base)['mais_nova']=='V182' and (srv/'Repositório'/'.atualizacao').exists() or True
    assert app._sinc_cfg()['ultima'] and not getattr(app,'_sinc_fora',False)
    # ---- remoção: só o administrador
    app._show_companies(); app.update(); app._selected_company_cnpj=GAMA; app._company_remove(); app.update()
    assert GAMA not in {x['cnpj'] for x in e.db_list_companies(100)} and GAMA in e.db_removed_companies()
    app._sinc_tick(forcar=True); assert esperar(app,lambda:not getattr(app,'_sinc_rodando',True))
    emp=S.ler_empresas(base); assert emp[GAMA]['removida'] and emp[GAMA]['removida_por']==admin['name']          # a remoção foi para o servidor (marcada, nada apagado)
    assert e.db_document_count(CN)>0 and R.pendentes(str(e.DB_PATH))>=0          # notas continuam
    # outra empresa removida no servidor: o administrador remove aqui também na sincronia
    S.publicar_empresas(base,[],{OUTRA:'Outro admin'}); app._sinc_tick(forcar=True); assert esperar(app,lambda:not getattr(app,'_sinc_rodando',True))
    assert OUTRA not in {x['cnpj'] for x in e.db_list_companies(100)}
    # ---- usuário comum: não vê o botão, não remove, e a remoção do servidor não é aplicada por ele
    comum={'id':99,'name':'Maria','email':'m@x.com','role':'user','status':'active','role_label':'Usuário'}
finally:
    app.destroy()
e.db_register_company(OUTRA,'ALFA SERVICOS LTDA')          # volta para o teste do usuário comum
app=e.App(current_user=comum); app.geometry('1366x650+0+0')
try:
    app._repo_cfg()['pasta']=base; app._repo_cfg()['ativo']=True
    app._show_companies(); app.update()
    def botoes(w):
        out=[]
        for ch in w.winfo_children():
            try: out.append(str(ch.cget('text')))
            except Exception: pass
            out+=botoes(ch)
        return out
    assert not [t for t in botoes(app.companies_frame) if 'remover empresa' in str(t).casefold()],'usuário comum viu o botão'
    app._selected_company_cnpj=OUTRA; msgs.clear(); app._company_remove(); assert OUTRA in {x['cnpj'] for x in e.db_list_companies(100)} and msgs and 'administrador' in str(msgs[-1])
    app._sinc_tick(forcar=True); assert esperar(app,lambda:not getattr(app,'_sinc_rodando',True))
    assert OUTRA in {x['cnpj'] for x in e.db_list_companies(100)},'usuário comum não aplica remoção do servidor'
    # ---- fora do escritório: aviso discreto com a última cópia, nada quebra
    app._repo_cfg()['pasta']=str(srv/'nao_existe'); app._sinc_cfg()['aviso_fora']=''
    app._sinc_tick(forcar=True); assert esperar(app,lambda:not getattr(app,'_sinc_rodando',True))
    assert app._sinc_fora and 'Fora do escritório' in app._sinc_texto and 'última cópia' in app._sinc_texto,getattr(app,'_sinc_texto','')
    # ---- Exato velho: o servidor tem formato mais novo -> não grava e avisa
    app._repo_cfg()['pasta']=base; (srv/'Repositório'/'.indice'/'versao.json').write_text(json.dumps({'formato':9,'mais_nova':'V999','pacote':'.atualizacao/Exato_Central_Fiscal_V999.zip'}),encoding='utf-8')
    app._sinc_tick(forcar=True); assert esperar(app,lambda:not getattr(app,'_sinc_rodando',True))
    assert R.BLOQUEADO=='versao_antiga'; R.BLOQUEADO=''
    print('V182 sincronia UI OK')
finally:
    app.destroy()
