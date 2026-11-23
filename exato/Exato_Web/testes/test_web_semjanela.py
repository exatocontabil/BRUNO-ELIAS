"""Exato Web: programas filhos (PowerShell) nunca abrem janela no Windows."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web import semjanela as sj

class SI:
    def __init__(self): self.dwFlags = 0; self.wShowWindow = 1
k = sj.argumentos_sem_janela({'capture_output': True}, SI)
assert k['creationflags'] & sj.CREATE_NO_WINDOW and k['startupinfo'].wShowWindow == 0 and k['startupinfo'].dwFlags & 1 and k['capture_output'] is True
k = sj.argumentos_sem_janela({'creationflags': 0x200}, SI); assert k['creationflags'] == 0x200 | sj.CREATE_NO_WINDOW          # mantém o que já pediu
k = sj.argumentos_sem_janela({'creationflags': sj.CREATE_NEW_CONSOLE}, SI); assert not (k['creationflags'] & sj.CREATE_NO_WINDOW)          # quem quer console de propósito continua com ele
mine = SI(); mine.dwFlags = 0x100; k = sj.argumentos_sem_janela({'startupinfo': mine}, SI); assert k['startupinfo'] is mine and mine.dwFlags & 0x100 and mine.dwFlags & 1
assert sj.instalar() is False or sys.platform == 'win32'          # fora do Windows não muda nada
print('Exato Web (sem janelas): OK')
