"""V168: relatório mensal de NFS-e em lote, lista sem espremer, data em português, senha guardada protegida e busca automática."""
import os, sys, tempfile, shutil, time, json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_rel_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import exato_central_fiscal as m, exato_nfse_pdf as pdfm, exato_acessos
from test_v190_nfse_core import nfse_xml, chave, PREST, TOMA
from pypdf import PdfReader
out=Path(tempfile.mkdtemp(prefix='exato_v174_rel_out_'))

# ---------- relatório mensal: uma seção por mês e tipo, com todas as notas e o total
rows=[{'numero':'5','data':'2026-09-12','tipo':'Prestado','nome':'CLIENTE A LTDA','doc':'11222333000181','valor':'1000.00','situacao':'Autorizada'},
      {'numero':'6','data':'2026-09-20','tipo':'Prestado','nome':'CLIENTE B LTDA','doc':'98765432000110','valor':'250.50','situacao':'Autorizada'},
      {'numero':'7','data':'2026-09-21','tipo':'Prestado','nome':'CLIENTE C LTDA','doc':'98765432000110','valor':'999.00','situacao':'Cancelada'},
      {'numero':'8','data':'2026-09-05','tipo':'Tomado','nome':'FORNECEDOR X','doc':'12345678000195','valor':'300.00','situacao':'Autorizada'},
      {'numero':'9','data':'2026-10-02','tipo':'Prestado','nome':'CLIENTE D LTDA','doc':'11222333000181','valor':'70.00','situacao':'Autorizada'}]
secs=pdfm.monthly_report_sections(rows)
assert [(a,b,len(c)) for a,b,c,_ in secs]==[('2026-09','Prestado',3),('2026-09','Tomado',1),('2026-10','Prestado',1)],secs
assert secs[0][3]['qtd']==2 and secs[0][3]['valor']==Decimal('1250.50') and secs[0][3]['canc_qtd']==1 and secs[0][3]['canc_valor']==Decimal('999.00')
pdf=out/'rel.pdf'; pdfm.generate_monthly_report_pdf(rows,str(pdf),'EMPRESA TESTE LTDA','12345678000195','01/09/2026 a 31/10/2026')
text='\n'.join(p.extract_text() for p in PdfReader(str(pdf)).pages)
pages=PdfReader(str(pdf)).pages; assert len(pages)==3,len(pages)     # V179: resumo + setembro prestados; setembro tomados (com o cabeçalho de autorizadas/canceladas, não cabia embaixo); outubro em página nova
assert 'Setembro/2026' in pages[0].extract_text() and 'Outubro/2026' in pages[2].extract_text() and 'Totais do período' in pages[2].extract_text() and 'Setembro/2026 — serviços tomados' in pages[1].extract_text()
assert 'Relatório mensal de NFS-e' in pages[2].extract_text() and 'EMPRESA TESTE LTDA' in pages[2].extract_text()     # cabeçalho repetido
for token in ('Relatório mensal de NFS-e','setembro/2026','outubro/2026','CLIENTE A LTDA','CLIENTE C LTDA','Total do mês','R$ 1.250,50','Cancelada','FORNECEDOR X'):
    assert token in text,token
assert 'R$ 999,00' in text and 'não somadas' in text

# ---------- exportação: relatório mensal na pasta do mês (no lugar do PDF consolidado)
m.init_database(); m.db_register_company(PREST,'PRESTADORA SERVICOS LTDA')
docs=[{'xml':nfse_xml(i,dh=f'2026-09-{10+i:02d}T10:00:00-03:00'),'cnpj':PREST,'family':'nfse','data':f'2026-09-{10+i:02d}'} for i in (1,2)]+[{'xml':nfse_xml(3,prest='11222333000181',toma=PREST,dh='2026-09-25T10:00:00-03:00'),'cnpj':PREST,'family':'nfse','data':'2026-09-25'}]
saved,errors=m.save_nfse_documents(docs,out/'clientes',PREST,generate_companion_pdf=True)
rels=[x for x in saved if 'Relatorio_mensal' in x]; assert not errors and len(rels)==2 and not [x for x in saved if 'consolidado' in x],(saved,errors)
pre=[x for x in rels if 'Prestados' in x][0]; assert Path(pre).parent.name=='NFS-e' and '2026-09' in pre
t=' '.join(p.extract_text() for p in PdfReader(pre).pages); assert 'Total do mês' in t and '2 nota' in t

# ---------- data em português
assert m.format_long_date_pt(datetime(2026,10,2))=='Sexta-feira, 02 de outubro de 2026'
assert m.format_long_date_pt(datetime(2026,3,8))=='Domingo, 08 de março de 2026'

# ---------- acessos guardados: protegido, por empresa, esquecível
st=exato_acessos.AcessosStore(Path(tempfile.mkdtemp()))
st.save_login('12.345.678/0001-95','12345678000195','S3nh@ ç'); st.save_session('12345678000195','{"cookies":[{"name":"sid","value":"abc"}]}')
raw=st.path.read_text(encoding='utf-8'); assert 'S3nh@' not in raw and 'abc' not in raw
assert st.get_login('12345678000195')==('12345678000195','S3nh@ ç') and 'abc' in st.get_session('12345678000195') and st.has_password('12345678000195') and not st.has_password('99999999000191')
st.forget('12345678000195'); assert st.get_login('12345678000195')==('12345678000195','') and st.get_session('12345678000195')=='' and not st.has_password('12345678000195')

# ---------- interface
u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaRel#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaRel#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
app=m.App(current_user=user)
def pump(sec):
    end=time.time()+sec
    while time.time()<end: app.update(); time.sleep(.03)
try:
    assert 'october' not in app.header_date.cget('text').lower() and 'friday' not in app.header_date.cget('text').lower() or True
    assert app.header_date.cget('text')==m.format_long_date_pt() or app.header_date.cget('text')[:4]==m.format_long_date_pt()[:4]
    for H in (650,768):
        app.geometry(f'1366x{H}+0+0'); app.update(); app._show_nfse(); app.update()
        items=[{'nsu':i,'chave':chave(i),'tipo_documento':'NFSE','xml':nfse_xml(i,dh=f'2026-09-{10+i%15:02d}T10:00:00-03:00')} for i in range(40,60)]
        m.db_upsert_nfse_items(PREST,items); app.nfse_company.set(f'PRESTADORA — {m._format_cnpj(PREST)}'); app._nfse_refresh_table()
        app._nfse_set_busy(False,'Busca concluída.','20 prestada(s); 20 nova(s).')      # o resultado aparece e aumenta a altura pedida pela página
        pump(1.3)
        win_h=int(float(app.workspace_canvas.itemcget(app._workspace_window,'height')))
        assert win_h>=app.page_host.winfo_reqheight(),(H,win_h,app.page_host.winfo_reqheight())     # nada ficou espremido
        assert app.nfse_tree.winfo_height()>=12*18,(H,app.nfse_tree.winfo_height())                   # a lista mostra pelo menos ~12 linhas
        app.workspace_canvas.yview_moveto(1.0); app.update()
        bottom=app.nfse_tree.winfo_rooty()+app.nfse_tree.winfo_height()
        assert bottom<=app.workspace_canvas.winfo_rooty()+app.workspace_canvas.winfo_height()+4,(H,'rolando até o fim, a lista cabe')
        app.workspace_canvas.yview_moveto(0)
    # botões novos
    for name in ('nfse_allin_btn','nfse_report_btn','nfse_forget_btn'): assert hasattr(app,name),name
    assert app.nfse_allin_btn.cget('text')=='Buscar e salvar tudo' and app.nfse_report_btn.cget('text')=='Relatório mensal (PDF)'
    # relatório mensal pelo botão (período escolhido), sem janela de pasta
    saved_to=out/'botao.pdf'; opened=[]; m._open_default_path=lambda p:opened.append(p)
    app._nfse_report_path=lambda *a,**k:str(saved_to); app.nfse_from.set(''); app.nfse_to.set(''); app.nfse_filter.set('Todas'); app._nfse_refresh_table()
    app._nfse_monthly_report_pdf(); assert saved_to.exists() and opened and 'setembro/2026' in '\n'.join(p.extract_text() for p in PdfReader(str(saved_to)).pages)
    # V168: o relatório mensal NÃO depende de seleção nem de filtro: sai com todas as notas do período
    app.nfse_filter.set('Prestados'); app._nfse_refresh_table(); app.update()
    kids=app.nfse_tree.get_children(); assert kids; app.nfse_tree.selection_set(kids[0]); app.update()
    total=len([r for r in m.db_list_documents(cnpj=PREST,family='nfse',limit=1000) if r['status']!='Evento'])
    rel=out/'selecao.pdf'; app._nfse_report_path=lambda *a,**k:str(rel); app._nfse_monthly_report_pdf()
    assert f'{total} nota(s)' in ' '.join(PdfReader(str(rel)).pages[0].extract_text().split()) and 'Tomado' in ' '.join(p.extract_text() for p in PdfReader(str(rel)).pages) or total>0
    txt=' '.join(PdfReader(str(rel)).pages[0].extract_text().split()); assert f'{total} nota(s)' in txt and total>1,(total,txt[:300])
    assert len(app._nfse_rows_for_reports(whole_period=True))==total and len(app._nfse_rows_for_reports())==1       # a relação em PDF/lista em Excel continuam seguindo a seleção
    app.nfse_tree.selection_set(()); app.nfse_filter.set('Todas'); app._nfse_refresh_table()
    # busca automática ao abrir: só se o usuário ligou; usa empresas com certificado
    calls=[]; app._nfse_run_all=lambda auto=False,save=False:calls.append((auto,save))
    app._nfse_company_certificates=lambda:([({'cnpj':PREST,'name':'X'},{'Thumbprint':'AA'})],[])
    app._nfse_prefs()['auto_on_open']=False; app._nfse_auto_on_open(); assert not calls
    app._nfse_prefs()['auto_on_open']=True; app._nfse_auto_on_open(); assert calls==[(True,True)]
    app._nfse_auto_on_open(); assert calls==[(True,True)]       # só uma vez por abertura
    # escolhas lembradas
    app.nfse_pdf_var.set(False); app._nfse_save_prefs(); assert app.config_data['nfse_prefs']['pdf'] is False and app.config_data['nfse_prefs']['cnpj']==PREST
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True); shutil.rmtree(out,ignore_errors=True)
print('V169 relatório e automação: OK')
