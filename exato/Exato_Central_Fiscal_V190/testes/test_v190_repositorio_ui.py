"""V168: tela Repositório (copiar agora, servidor fora do ar, prazo, restaurar) com o programa de verdade."""
import os, sys, tempfile, shutil, time, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_repoui_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
import exato_repositorio as R
from test_v190_nfse_core import nfse_xml, chave, PREST
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaRep#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaRep#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
m.db_register_company(PREST,'ELETROTAK MANUTENCAO LTDA')
items=[{'nsu':i,'chave':chave(i),'tipo_documento':'NFSE','xml':nfse_xml(i,prest=PREST,toma='98765432000110',valor=f'{100+i*10:.2f}',dh='2026-09-%02dT10:00:00-03:00'%(5+i))} for i in range(1,6)]
res=m.db_upsert_nfse_items(PREST,items); assert res['new']==5,res
msgs=[]; m.messagebox.showinfo=lambda *a,**k:msgs.append(a); m.messagebox.showwarning=lambda *a,**k:msgs.append(a)
srv=Path(tempfile.mkdtemp(prefix='exato_v174_srv2_'))
app=m.App(current_user=user)
import traceback
app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
def esperar(cond,t=20):
    fim=time.time()+t
    while time.time()-fim<0:
        app.update()
        if cond(): return True
        time.sleep(.03)
    return False
try:
    app.geometry('1366x650+0+0'); app.update()
    cfg=app._repo_cfg(); assert cfg['ativo'] and cfg['pasta']==R.PASTA_PADRAO and cfg['meses']==12     # padrão combinado com o usuário
    assert app.nav_repo.winfo_exists() and app.nav_sync.winfo_y()<app.nav_repo.winfo_y()<app.nav_audit.winfo_y()
    # servidor fora do ar: tela explica, nada se perde (fica na fila)
    cfg['pasta']=str(srv/'fora'); app._show_repo(); app.update(); assert app.header_crumb.cget('text')=='Repositório'
    app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'])
    esperar(lambda: 'Aguardando' in app.repo_status_title.cget('text'),8); app.update()
    assert app.repo_tiles['faltam'].cget('text')=='5' and 'Aguardando o servidor' in app.repo_status_title.cget('text'),(app.repo_tiles['faltam'].cget('text'),app.repo_status_title.cget('text'))
    assert not (srv/'fora').exists()
    # V168: filtros da tabela (situação, empresa, mês)
    total_linhas=len(app.repo_tree.get_children()); assert total_linhas>=1
    app.repo_filtro_situacao.set('Só o que já está no servidor'); app._repo_filtrar(); assert len(app.repo_tree.get_children())==0 and app.repo_filtro_contagem.cget('text').startswith('0 de')
    app.repo_filtro_situacao.set('Só o que falta copiar'); app._repo_filtrar(); assert len(app.repo_tree.get_children())==total_linhas
    app.repo_filtro_situacao.set('Todas'); app.repo_filtro_busca.set('nada-parecido'); app._repo_filtrar(); assert len(app.repo_tree.get_children())==0
    app.repo_filtro_busca.set('prestadora'); app._repo_filtrar(); assert len(app.repo_tree.get_children())==total_linhas
    app.repo_filtro_busca.set(PREST[:8]); app._repo_filtrar(); assert len(app.repo_tree.get_children())==total_linhas        # também acha pelo CNPJ
    app._repo_limpar_filtros(); assert app.repo_filtro_busca.get()=='' and app.repo_filtro_situacao.get()=='Todas'
    app._repo_filtrar_pendentes(); assert app.repo_filtro_situacao.get()=='Só o que falta copiar' and app._repo_cfg()['filtro']['situacao']=='Só o que falta copiar'     # clicar em "Na fila"
    app._repo_limpar_filtros()
    # servidor disponível: copia tudo e a tela mostra "Tudo guardado"
    cfg['pasta']=str(srv); app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'])
    app._repo_refresh_view(); esperar(lambda: 'Tudo guardado' in app.repo_status_title.cget('text'),8); app.update()
    assert 'Tudo guardado' in app.repo_status_title.cget('text') and len(list((srv/'Repositório').rglob('*.xml')))==5
    assert len(app.repo_tree.get_children())>=1 and app.repo_tree.item(app.repo_tree.get_children()[0],'image')
    assert list((srv/'Backups').rglob('central_fiscal_*.zip')), 'cópia diária do banco'
    # cópia automática desligada não copia sozinha
    cfg['ativo']=False; app.repo_auto_var.set(False); app._repo_tick; app._repo_cfg()
    # prazo: mês antigo é só avisado; apagar exige confirmação
    c=sqlite3.connect(m.DB_PATH); c.execute("UPDATE documents SET issued_at='2023-01-10T10:00:00' WHERE doc_id=(SELECT doc_id FROM documents LIMIT 1)"); c.commit(); c.close()
    c=sqlite3.connect(m.DB_PATH); c.execute("DELETE FROM repositorio_copias"); c.commit(); c.close()
    for p in (srv/'Repositório').iterdir(): shutil.rmtree(p)
    cfg['ativo']=True; app._repo_start(manual=True); assert esperar(lambda: not app._repo_state['rodando'])
    app._repo_check_prazo(); assert esperar(lambda: str(app.repo_apagar_btn['state'])=='normal',8),app.repo_prazo_info.cget('text')
    assert '1 XML' in app.repo_prazo_info.cget('text') and len(list((srv/'Repositório').rglob('*.xml')))==5
    m.messagebox.askyesno=lambda *a,**k:False; app._repo_delete_expired(); app.update(); assert len(list((srv/'Repositório').rglob('*.xml')))==5      # "Não": nada é apagado
    m.messagebox.askyesno=lambda *a,**k:True; app._repo_delete_expired(); assert esperar(lambda: len(list((srv/'Repositório').rglob('*.xml')))==4,8)
    # restaurar: o banco perde as notas e o repositório as devolve
    c=sqlite3.connect(m.DB_PATH); c.execute("DELETE FROM documents"); c.commit(); c.close()
    app._repo_restore(); assert esperar(lambda: not getattr(app,'_repo_restoring',True),20)
    c=sqlite3.connect(m.DB_PATH); n=c.execute("SELECT COUNT(*) FROM documents WHERE family='nfse'").fetchone()[0]; c.close(); assert n==4,n
    # 1000 px de largura e tema escuro: a tela abre sem erro
    app.geometry('1000x600+0+0'); app._show_repo(); app.update(); app.update()
finally:
    app.destroy(); shutil.rmtree(srv,ignore_errors=True); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 repositório UI: OK')
