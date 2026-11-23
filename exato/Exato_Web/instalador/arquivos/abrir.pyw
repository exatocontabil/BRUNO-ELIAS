"""Atalho "Exato Web": liga o Exato se preciso, espera ficar pronto e abre no navegador."""
import sys, time, webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from supervisor import iniciar_se_preciso, site_responde, RAIZ, PORTA


def endereco():
    try:
        linha = (RAIZ / 'endereco.txt').read_text(encoding='utf-8-sig').splitlines()[0].strip()
        if linha.startswith('http'): return linha
    except (OSError, IndexError): pass
    return f'http://127.0.0.1:{PORTA}'


iniciar_se_preciso()
fim = time.time() + 60
while time.time() < fim and not site_responde(): time.sleep(1)
if site_responde(): webbrowser.open(endereco())
else:
    try:
        import tkinter; from tkinter import messagebox
        r = tkinter.Tk(); r.withdraw(); messagebox.showerror('Exato Web', 'O Exato não ligou. Espere um minuto e tente de novo. Se continuar, chame o suporte.'); r.destroy()
    except Exception: pass
