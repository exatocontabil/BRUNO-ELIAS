"""V168: rolagem suave — roda/touchpad rola o que está sob o ponteiro, sem pular nem rolar a janela de trás."""
import os, sys, tempfile, shutil, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_rolagem_'); sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(ROOT/'programa'/'third_party'))
import tkinter as tk
from tkinter import ttk
import exato_central_fiscal as m
import exato_ui as ui
m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'SenhaRol#2026'); user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaRol#2026')
m.enumerate_windows_certificates=lambda *a,**k:([],'')
app=m.App(current_user=user)
class Ev:
    def __init__(s,w,delta,num=0): s.widget=w; s.delta=delta; s.num=num; s.x_root=w.winfo_rootx()+5; s.y_root=w.winfo_rooty()+5
def pump(t=.6):
    end=time.time()+t
    while time.time()<end: app.update(); time.sleep(.01)
try:
    app.geometry('1366x650+0+0'); app._show_documents(); pump(.5)
    r=app._wheel; page=app.workspace_canvas
    # página alta de propósito (conteúdo maior que a janela)
    tall=tk.Frame(app.page_host,height=2500); tall.pack(); pump(.5)
    total,view=r._extent(); assert total>view+100,(total,view)
    w=app.page_host
    assert page.yview()[0]==0.0
    # touchpad: passos pequenos (30) somados -> a página anda mesmo assim
    for _ in range(6): assert r.on_wheel(Ev(tall,-30))=='break'
    pump(.8); y1=page.yview()[0]; assert y1>0.0,'touchpad deve rolar a página'
    r.on_wheel(Ev(tall,120)); r.on_wheel(Ev(tall,120)); pump(.8); assert page.yview()[0]<y1
    # rolagem animada termina sozinha (sem tremer) e nunca passa do fim
    for _ in range(80): r.on_wheel(Ev(tall,-120))
    t0=time.time(); n=0
    while (r._target is not None or r._job) and time.time()-t0<6: pump(.05); n+=1
    print("TEMPO",time.time()-t0,page.yview(),r._job,r._target); assert abs(page.yview()[1]-1.0)<0.002 and r._job is None and r._target is None
    # Linux (Button-4/5)
    r.on_wheel(Ev(tall,0,4)); pump(.5); assert page.yview()[1]<1.0
    # Tabela interna rola primeiro; a página fica parada
    page.yview_moveto(0); pump(.2)
    host=tk.Frame(app.page_host); host.pack(); tr=ttk.Treeview(host,height=4,columns=('a',)); tr.pack()
    for i in range(60): tr.insert('','end',values=(i,))
    pump(.4); y0=page.yview()[0]; r._inner_at=0
    r.on_wheel(Ev(tr,-120)); pump(.3); assert tr.yview()[0]>0.0 and page.yview()[0]==y0,'tabela rola, página não'
    # no fim da tabela, a página não "pula" de imediato
    tr.yview_moveto(1.0); r._inner_at=time.monotonic(); r.on_wheel(Ev(tr,-120)); pump(.3); assert page.yview()[0]==y0
    # depois da pausa a página segue
    r._inner_at=0; r.on_wheel(Ev(tr,-120)); pump(.8); assert page.yview()[0]>y0
    # combobox não troca o valor ao rolar por cima
    cb=ttk.Combobox(app.page_host,values=['a','b','c'],state='readonly'); cb.pack(); cb.current(0); pump(.3)
    r.on_wheel(Ev(cb,-120)); assert cb.get()=='a'
    # diálogo: não rola a página de trás
    dlg=tk.Toplevel(app); dlg.geometry('300x200+50+50'); lab=tk.Label(dlg,text='x'); lab.pack(); pump(.3)
    t0=time.time()
    while (r._target is not None or r._job) and time.time()-t0<5: pump(.05)
    y_before=page.yview()[0]; r.on_wheel(Ev(lab,-120)); pump(.5); assert page.yview()[0]==y_before
    dlg.destroy()
    # desenho lento: sem animação, pula direto (evita rastro de imagem no Windows)
    page.yview_moveto(0); pump(.2); r.stop(); r._slow=False
    orig=page.update_idletasks
    page.update_idletasks=lambda: (time.sleep(.06), orig())[1]
    r.on_wheel(Ev(tall,-120)); pump(.3)
    assert r._slow and r._target is None and r._job is None and page.yview()[0]>0.0
    page.update_idletasks=orig; r._slow=False; page.yview_moveto(0)
    # trocar de tela volta ao topo e cancela a animação
    r.on_wheel(Ev(tall,-120)); app._show_history(); pump(.8); assert page.yview()[0]==0.0 and r._target is None
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V169 rolagem: OK')
