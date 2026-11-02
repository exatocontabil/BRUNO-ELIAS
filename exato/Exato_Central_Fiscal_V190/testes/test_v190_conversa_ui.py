"""Exatinho conversando na tela (V168): Ctrl+J, perguntas com dados reais do Arquivo Fiscal Local, resumo do dia e tarefas com confirmação."""
import os, sys, tempfile, shutil, time
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_chat_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m
from test_v190_nfse_core import nfse_xml, evento_xml, chave, PREST
out=Path(tempfile.mkdtemp(prefix='exato_v174_chat_out_'))
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaChat#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaChat#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
m.db_register_company(PREST,'PRESTADORA SERVICOS LTDA'); m.db_register_company('11222333000181','CLIENTE SEM BUSCA LTDA')
items=[{'nsu':i,'chave':chave(i),'tipo_documento':'NFSE','xml':nfse_xml(i,valor=f'{1000*i}.00',dh=f'2026-09-{10+i:02d}T10:00:00-03:00')} for i in (1,2,3,4)]
items.append({'nsu':9,'chave':chave(5),'tipo_documento':'NFSE','xml':nfse_xml(5,prest='11222333000181',toma=PREST,valor='300.00',dh='2026-09-20T10:00:00-03:00')})
m.db_upsert_nfse_items(PREST,items)
docs=m.db_load_documents_as_payload(PREST,family='nfse'); m.db_mark_documents_exported([d for d in docs if d['chave'] in (chave(1),chave(2))],str(out/'x'))
m.db_upsert_nfse_items(PREST,[{'nsu':100,'chave':chave(2),'tipo_documento':'EVENTO','tipo_evento':'101101','xml':evento_xml(2)}])
run=m.db_start_run(PREST); m.db_update_run(run,'Concluído com observações',finished=True,error_text='Alguns XMLs não foram baixados.')
# ---------- consultas no banco
s=m.db_assistant_summary(PREST,'2026-09-01','2026-09-30'); assert sum(r['count'] for r in s if r['status']!='Evento')==5
assert [x['count'] for x in m.db_assistant_cancelled_exported()]==[1] and sum(x['count'] for x in m.db_assistant_unexported())==3        # 3, 4 e 5 ainda não exportadas (a 2 foi cancelada)
lr=m.db_assistant_last_runs(); assert lr[PREST]['ok_at'] and 'XML' in lr[PREST]['last_error']
rws=m.db_assistant_nfse_rows(PREST,'2026-09-01','2026-09-30'); assert len(rws)==5 and any(r['status']=='Cancelado' and r['exported'] for r in rws)
infos=[]; m.messagebox.showinfo=lambda *a,**k:infos.append(a); m.messagebox.showwarning=lambda *a,**k:infos.append(a); m.messagebox.showerror=lambda *a,**k:infos.append(a); m.messagebox.askyesno=lambda *a,**k:True
app=m.App(current_user=user)
def chat_text(): return app.chat_text.get('1.0','end')
try:
    app.geometry('1366x650+0+0'); app.update(); app.update()
    app.config_data['assistente_resumo_em']=''
    # ---------- aviso do resumo do dia: uma vez por dia
    toasts=[]; app._toast=lambda text,kind='info',ms=0:toasts.append(text)
    app._assistant_startup_briefing(); assert toasts and 'ponto(s) para você hoje' in toasts[0] and 'Ctrl+J' in toasts[0] and app.config_data['assistente_resumo_em']==datetime.now().strftime('%Y-%m-%d')
    n=len(toasts); app._assistant_startup_briefing(); assert len(toasts)==n
    # ---------- Ctrl+J abre a conversa, com o resumo do dia
    app.focus_force(); app.event_generate('<Control-Key-j>'); app.update(); app.update()
    assert app._chat_is_open and app.ia_chat_card.winfo_ismapped()
    t=chat_text(); assert 'ponto(s) para você hoje' in t and 'já exportada(s) foram canceladas' in t and 'sem busca' in t,t
    wx,wy,ww,wh=app.winfo_rootx(),app.winfo_rooty(),app.winfo_width(),app.winfo_height(); c=app.ia_chat_card
    assert c.winfo_rootx()>=wx and c.winfo_rootx()+c.winfo_width()<=wx+ww+2 and c.winfo_rooty()>=wy and c.winfo_rooty()+c.winfo_height()<=wy+wh+2,'cabe na janela 1366x650'
    app.event_generate('<Control-Key-j>'); app.update(); assert not app._chat_is_open and not app.ia_chat_card.winfo_ismapped()     # Ctrl+J de novo fecha
    # ---------- pergunta com conta e evidência
    app._chat_open(); app._chat_submit('Quanto a prestadora prestou em setembro?'); app.update()
    t=chat_text()
    assert 'PRESTADORA SERVICOS LTDA prestou R$ 8.000,00' in t and '3 nota(s) autorizada(s)' in t and '1 cancelada' in t and 'NFS-e' in t,t[-900:]     # 1000 + 3000 + 4000; a nota 2 (R$ 2.000) está cancelada e fica fora da soma
    app._chat_submit('quanto tomou?'); app.update(); assert 'R$ 300,00' in chat_text() or 'tomou' in chat_text()
    # V168: memória da conversa, 'como calculei', sugestões em botão e vários pedidos numa frase
    app._assistant_ctx.clear(); app._chat_submit('Quanto a prestadora prestou em setembro?'); app.update()
    assert 'Como calculei' in chat_text() and app._assistant_ctx['company']==PREST and app._assistant_ctx['period'][2]=='setembro/2026'
    app._chat_submit('e as tomadas?'); app.update(); assert 'tomou R$ 300,00 em setembro/2026' in chat_text(),chat_text()[-500:]
    app._assistant_perform({'kind':'ask','text':'Comparar com o período anterior'}); app.update(); assert 'comparado a agosto/2026' in chat_text()
    app._chat_submit('quanto prestou em setembro; quais notas canceladas eu já exportei'); app.update(); assert chat_text().count('Exatinho\n')>=2 and '1 NFS-e cancelada' in chat_text()
    app._chat_submit('qual a maior nota em setembro?'); app.update(); assert 'maiores NFS-e' in chat_text() and 'R$ 4.000,00' in chat_text()
    app._chat_submit('quais sao os maiores clientes em setembro'); app.update(); assert 'Maiores clientes' in chat_text()
    app._chat_submit('quais notas canceladas eu já exportei'); app.update(); assert '1 NFS-e cancelada' in chat_text() or '1 nota' in chat_text()
    app._chat_submit('qual a capital da França?'); app.update(); assert 'Ainda não sei responder' in chat_text()
    # ---------- botão de ação: ver canceladas exportadas abre Documentos já filtrado
    app._assistant_perform({'kind':'docs_cancelled_exported'}); app.update(); assert app.doc_status.get()=='Cancelado' and app.doc_export_status.get()=='Exportado' and len(app.doc_tree.get_children())==1
    app._assistant_perform({'kind':'goto','screen':'nfse','cnpj':PREST,'df':'2026-09-01','dt':'2026-09-30'}); app.update(); assert app.nfse_from.get()=='01/09/2026' and app.nfse_to.get()=='30/09/2026' and m._format_cnpj(PREST) in app.nfse_company.get()
    # ---------- tarefas sempre pedem confirmação e só então executam
    calls=[]; app._nfse_search_and_save=lambda: calls.append('salvar'); app._nfse_start=lambda: calls.append('buscar')
    app._chat_submit('busque e salve tudo da prestadora'); app.update(); assert calls==[] and 'Posso começar?' in chat_text()
    cert={'Thumbprint':'AA','FriendlyName':'PRESTADORA:'+PREST,'NotAfter':'2099-01-01','Document':m._format_cnpj(PREST),'Subject':'CN=PRESTADORA SERVICOS LTDA:'+PREST}
    app.certificates=[cert]; previous={'Thumbprint':'ZZ'}; app.selected=previous
    app._assistant_perform({'kind':'nfse_search_save','cnpj':PREST}); app.update()
    assert calls==['salvar'] and app.nfse_mode.get()=='cert' and app.selected is previous      # usou o certificado da empresa e devolveu o que estava selecionado
    app._assistant_perform({'kind':'nfse_search','cnpj':PREST}); assert calls==['salvar','buscar']
    app.certificates=[]; calls.clear(); app._assistant_perform({'kind':'nfse_search_save','cnpj':'11222333000181'}); app.update(); assert calls==[] and 'não tem certificado' in chat_text()
    m.ACESSOS.save_login('11222333000181','11222333000181','x'); app._assistant_perform({'kind':'nfse_search_save','cnpj':'11222333000181'}); app.update(); assert calls==['salvar'] and app.nfse_mode.get()=='login'   # senha salva: usa o portal
    all_calls=[]; app._nfse_run_all=lambda auto=False,save=False:all_calls.append((auto,save)); app._nfse_company_certificates=lambda:([],[(1)])
    app._assistant_perform({'kind':'nfse_all_save'}); assert all_calls==[] and 'Nenhuma empresa cadastrada tem certificado' in chat_text()
    app._nfse_company_certificates=lambda:([({'cnpj':PREST,'name':'X'},cert)],[]); app._assistant_perform({'kind':'nfse_all_save'}); assert all_calls==[(True,True)]
    # ---------- relatório pelo Exatinho: salvo na pasta dos clientes, sem janela
    opened=[]; m._open_default_path=lambda p:opened.append(p); app._auto_search_config()['root_folder']=str(out/'clientes'); (out/'clientes').mkdir()
    app._assistant_perform({'kind':'nfse_report','cnpj':PREST,'df':'2026-09-01','dt':'2026-09-30'}); app.update()
    pdfs=list((out/'clientes').rglob('Relatorio_mensal_NFS-e_*.pdf')); assert len(pdfs)==1 and 'Relatórios' not in str(pdfs[0]) and 'Relatorios_NFS-e' in str(pdfs[0]) and 'com 5 nota(s)' in chat_text(),chat_text()[-400:]
    # ---------- botões do painel e da janela
    app._chat_close(); app._exatinho_open_panel(); app.update()
    texts=[w.cget('text') for w in app.ia_sidebar_interaction.winfo_children()[-1].winfo_children() if hasattr(w,'cget')]
    assert any('Conversar com o Exatinho' in x for x in texts),texts
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True); shutil.rmtree(out,ignore_errors=True)
print('V169 conversa com o Exatinho (tela): OK')
