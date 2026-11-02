"""V177 (tela): Situação da busca mostra a causa quando não deu para buscar, "Por que?" explica em português, relatório em PDF, aviso de leitura e sem travar."""
import os, sys, sqlite3, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v177_motui_'); os.environ['EXATO_UI_SYNC']='1'
sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party')); sys.path.insert(0,str(Path(__file__).parent))
import tkinter as tk
from tkinter import ttk
import exato_central_fiscal as m, exato_busca_motivos as M
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaMot#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaMot#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
A,B='11222333000181','12345678000195'; m.db_register_company(A,'ALFA LTDA'); m.db_register_company(B,'BETA LTDA')
app=m.App(current_user=user); toasts=[]; app._toast=lambda t,k='info',ms=0: toasts.append((t,k))
import traceback
app.report_callback_exception=lambda e,v,t: print(''.join(traceback.format_exception(e,v,t)))
def esperar(cond,t=25):
    fim=time.time()+t
    while time.time()<fim:
        app.update()
        if cond(): return True
        time.sleep(.03)
    return False
def textos(w):
    out=[]
    for x in w.winfo_children():
        try: out.append(str(x.cget('text')))
        except Exception: pass
        out+=textos(x)
    return out
try:
    app.geometry('1366x650+0+0'); app.update()
    # ---- rodada sem certificado: cada empresa ganha a causa (não "Com observação" sem explicação)
    app.selected=None; app._auto_round_start(manual=True); assert esperar(lambda: not app._auto_round_active,40)
    u_=M.ultimas(str(m.DB_PATH)); assert u_[(A,'nfe')]['codigo']=='sem_certificado' and u_[(B,'cte')]['codigo']=='sem_certificado' and u_[(A,'nfse')]['codigo']=='sem_certificado_empresa',u_
    # ---- a aba mostra a causa e explica ao clicar
    app._show_companies(); app.update(); app._sit_aba('situacao'); assert esperar(lambda: app._sit_lista and not app._sit_lendo)
    tx=app._sit_textos(); assert 'Falta escolher o certificado digital' in tx and 'Esta empresa não tem certificado neste computador' in tx,tx
    assert app._sit_info.cget('text').endswith('Clique em um selo para ver o porquê.')
    app._sit_porque(A,'nfe'); app.update(); win=app._sit_porque_win; assert win.winfo_exists()
    def achar_texto(w):
        for x in w.winfo_children():
            if isinstance(x,tk.Text): return x
            r=achar_texto(x)
            if r is not None: return r
    corpo=achar_texto(win).get('1.0','end')
    assert 'Falta escolher o certificado digital' in corpo and 'O que fazer:' in corpo and 'menu Certificado' in corpo and 'Últimas tentativas' in corpo and 'Traceback' not in corpo,corpo[:400]
    assert corpo.index('NF-e')<corpo.index('NFC-e')                      # o tipo clicado vem primeiro
    win.destroy()
    # ---- relatório em PDF (uma empresa e todas)
    pdf=Path(tempfile.mkdtemp())/'relatorio.pdf'; app._sit_pdf([A],destino=str(pdf)); assert pdf.exists() and pdf.stat().st_size>1500
    import pypdf; t=' '.join(' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(pdf)).pages).split()); assert 'ALFA LTDA' in t and 'BETA LTDA' not in t and 'O que fazer:' in t
    pdf2=Path(tempfile.mkdtemp())/'todas.pdf'; app._sit_pdf(None,destino=str(pdf2)); t2=' '.join(' '.join((p.extract_text() or '') for p in pypdf.PdfReader(str(pdf2)).pages).split()); assert 'ALFA LTDA' in t2 and 'BETA LTDA' in t2
    # ---- resultado real vence a previsão; busca bem-sucedida limpa o aviso
    M.registrar(str(m.DB_PATH),A,('nfe','nfce','cte'),'ok'); app._sit_lendo=False; app._sit_refresh(); assert esperar(lambda: not app._sit_lendo)
    la=app._sit_linha(A)['celulas']; assert la['nfe']['ocorrencia']['codigo']=='ok' and la['nfe']['causa'].get('previsto')      # a busca deu certo, mas sem certificado escolhido continua previsto o problema
    # ---- aviso de leitura e erro sem travar
    app._sit_lendo=False; app._sit_lista=[]; app._sit_indicador(True); app.update(); assert app._sit_barra_on and 'Lendo a situação' in app._sit_info.cget('text'); app._sit_indicador(False); assert not app._sit_barra_on
    orig=m.situacao_mod.linhas
    def quebra(*a,**k): raise RuntimeError('banco quebrou')
    m.situacao_mod.linhas=quebra; app._sit_lista=[]; app._sit_refresh(); assert esperar(lambda: not app._sit_lendo); assert 'Não consegui ler a situação' in app._sit_info.cget('text') and 'RuntimeError' not in app._sit_info.cget('text')
    m.situacao_mod.linhas=orig
    app.update(); print('V177 busca motivos UI OK')
finally:
    try: app.destroy()
    except Exception: pass
