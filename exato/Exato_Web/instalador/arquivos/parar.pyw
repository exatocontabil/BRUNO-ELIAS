"""Atalho "Parar o Exato": desliga o Exato Web (o supervisor e o site). Com o argumento /silencioso não mostra mensagem."""
import os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from supervisor import pasta_dados, processo_vivo


def encerrar(pid):
    if not processo_vivo(pid): return False
    if sys.platform == 'win32': subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, creationflags=0x08000000)
    else:
        import signal; os.kill(int(pid), signal.SIGTERM)
    return True


feitos = 0
for nome in ('supervisor.pid', 'servidor.pid', 'caddy.pid'):          # primeiro o supervisor (para não religar), depois o site e o endereço seguro
    arq = pasta_dados() / nome
    try: feitos += 1 if encerrar(arq.read_text(encoding='ascii').strip()) else 0
    except (OSError, ValueError): pass
    try: arq.unlink()
    except OSError: pass
if '/silencioso' not in [a.lower() for a in sys.argv[1:]]:
    try:
        import tkinter; from tkinter import messagebox
        r = tkinter.Tk(); r.withdraw(); messagebox.showinfo('Exato Web', 'O Exato foi desligado.' if feitos else 'O Exato já estava desligado.'); r.destroy()
    except Exception: pass
