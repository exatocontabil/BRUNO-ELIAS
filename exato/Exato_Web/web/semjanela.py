"""Nenhum programa filho (PowerShell etc.) abre janela no Windows.

O site roda com `pythonw` (sem console). Nesse caso, cada `powershell.exe` que o site (ou os módulos do Exato) chama para colocar/retirar o certificado,
consultar a Receita ou a SEFAZ abre uma janela azul vazia por um instante: aparecia "toda hora". Aqui o Python passa a pedir "sem janela" por padrão em todo
programa filho. Só no Windows; quem pedir outra coisa de propósito (DETACHED_PROCESS, CREATE_NEW_CONSOLE) continua com o que pediu."""
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_CONSOLE = 0x00000010


def argumentos_sem_janela(kw, startupinfo_cls):
    """Devolve os argumentos do `Popen` com "sem janela" acrescentado (sem mudar o que a chamada pediu de propósito)."""
    kw = dict(kw); flags = int(kw.get('creationflags') or 0)
    if not (flags & (DETACHED_PROCESS | CREATE_NEW_CONSOLE)): kw['creationflags'] = flags | CREATE_NO_WINDOW
    si = kw.get('startupinfo') or startupinfo_cls()
    si.dwFlags |= getattr(subprocess, 'STARTF_USESHOWWINDOW', 1); si.wShowWindow = 0
    kw['startupinfo'] = si
    return kw


def instalar():
    if sys.platform != 'win32' or getattr(subprocess.Popen, '_exato_sem_janela', False): return False
    original = subprocess.Popen.__init__
    def init(self, *args, **kw): original(self, *args, **argumentos_sem_janela(kw, subprocess.STARTUPINFO))
    subprocess.Popen.__init__ = init; subprocess.Popen._exato_sem_janela = True
    return True
