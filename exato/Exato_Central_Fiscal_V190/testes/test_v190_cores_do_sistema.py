"""V168: cartões não quebram quando o fundo do pai tem nome de cor do Windows (ex.: SystemButtonFace)."""
import os, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v174_cores_'); sys.path.insert(0,str(ROOT/'programa'))
import tkinter as tk
import exato_ui as ui
# a conversão aceita hexadecimal, nome de cor e nome desconhecido (sem erro)
assert ui._hex('#FFF')==(255,255,255) and ui._hex('white')==(255,255,255) and ui._hex('SystemButtonFace')==(240,240,240)
root=tk.Tk(); root.geometry('400x300')
assert ui.to_hex(root,'white')=='#ffffff' and ui.to_hex(root,'SystemButtonFace')=='#FFFFFF' and ui.to_hex(root,'#E11D2E')=='#E11D2E'
for name in ('white','lightgray','SystemButtonFace'):
    parent=tk.Frame(root); parent.pack()
    try: parent.configure(bg=name)
    except tk.TclError: pass
    parent.cget  # (no Linux o nome do Windows não existe: o pai fica com a cor padrão)
    parent._real=parent.cget('bg')
    # simula o Windows: o Tk devolve o NOME da cor em cget
    orig=parent.cget; parent.cget=lambda k,_o=orig,_n=name: _n if k in ('bg','background') else _o(k)
    card=ui.ModernCard(parent,fill=name,border=name); card.pack(padx=10,pady=10); tk.Label(card,text='x').pack(padx=20,pady=20)
    root.update(); time.sleep(.1); root.update()
    assert card._page_bg.startswith('#') and len(card._page_bg)==7 and card._fill.startswith('#'),(name,card._page_bg)
    card.configure(bg=name); root.update(); time.sleep(.1); root.update()
    assert card._bg.cget('image'),name
root.destroy()
print('V169 cores do sistema: OK')
