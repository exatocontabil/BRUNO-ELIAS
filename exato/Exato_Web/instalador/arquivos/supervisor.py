"""Mantém o Exato Web de pé: liga, e liga de novo se ele cair ou se pedir reinício (ex.: depois de restaurar uma cópia de segurança).

Roda escondido (pythonw). Só uma cópia por vez (arquivo de número do processo na pasta de dados). Fechar de propósito = `parar.pyw`.
Código de saída 0 do site = parada normal (o supervisor também termina); qualquer outro = religar em poucos segundos."""
import os, socket, subprocess, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PORTA = int(os.environ.get('EXATO_WEB_PORT', '8443')); HOST = '127.0.0.1'
SEM_JANELA = 0x08000000 | 0x00000008          # CREATE_NO_WINDOW | DETACHED_PROCESS


def pasta_dados():
    """A mesma regra do site: variável de ambiente, depois `dados.txt` (escolhido na instalação), depois <usuário>/ExatoWebDados."""
    if os.environ.get('EXATO_WEB_DADOS'): return Path(os.environ['EXATO_WEB_DADOS'])
    try:
        linha = (RAIZ / 'dados.txt').read_text(encoding='utf-8-sig').splitlines()[0].strip().strip('"')
        if linha: return Path(linha)
    except (OSError, IndexError): pass
    return Path.home() / 'ExatoWebDados'


def site_responde(porta=PORTA, host=HOST, espera=1.0):
    try:
        with socket.create_connection((host, porta), timeout=espera): return True
    except OSError: return False


def processo_vivo(pid):
    """O número do processo ainda existe? (no Windows NÃO usa os.kill(pid, 0), que ali encerraria o processo)"""
    try: pid = int(pid)
    except (TypeError, ValueError): return False
    if pid <= 0: return False
    if sys.platform == 'win32':
        import ctypes
        k = ctypes.windll.kernel32; h = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h: return False
        try:
            codigo = ctypes.c_ulong(); ok = k.GetExitCodeProcess(h, ctypes.byref(codigo)); return bool(ok) and codigo.value == 259          # STILL_ACTIVE
        finally: k.CloseHandle(h)
    try: os.kill(pid, 0)
    except OSError: return False
    return True


def comando_site():
    pythonw = Path(sys.executable).with_name('pythonw.exe'); exe = pythonw if pythonw.exists() else Path(sys.executable)
    return [str(exe), '-m', 'web.servico']


def executar(comando, cwd, esperar=time.sleep, agora=time.time, max_rapidas=5, abrir=None):
    """Roda o site e religa quando ele sai com erro. Devolve 0 quando o site termina normalmente. `abrir`: fábrica do processo (para testes)."""
    rapidas = 0
    while True:
        inicio = agora()
        p = (abrir or (lambda: subprocess.Popen(comando, cwd=str(cwd), creationflags=SEM_JANELA if sys.platform == 'win32' else 0)))()
        codigo = p.wait()
        if codigo == 0: return 0
        rapidas = rapidas + 1 if agora() - inicio < 60 else 0          # caiu logo depois de ligar várias vezes: espera mais antes de tentar de novo
        esperar(30 if rapidas >= max_rapidas else 3)


def ligar_endereco():
    """Se a pessoa já usa o endereço do escritório (tarefa do Caddy), liga ele também. Sem a tarefa, não faz nada."""
    if sys.platform != 'win32': return
    try: subprocess.run(['schtasks', '/Run', '/TN', 'Exato Web Endereco'], capture_output=True, creationflags=SEM_JANELA, timeout=20)
    except Exception: pass


def principal():
    dados = pasta_dados(); dados.mkdir(parents=True, exist_ok=True); pidf = dados / 'supervisor.pid'
    try:
        antigo = int(pidf.read_text(encoding='ascii').strip())
        if antigo != os.getpid() and processo_vivo(antigo): return 0          # já existe um supervisor
    except (OSError, ValueError): pass
    pidf.write_text(str(os.getpid()), encoding='ascii')
    ligar_endereco()
    try: return executar(comando_site(), RAIZ)
    finally:
        try:
            if pidf.read_text(encoding='ascii').strip() == str(os.getpid()): pidf.unlink()
        except OSError: pass


def iniciar_se_preciso():
    """Liga o supervisor (escondido) se o site ainda não responde. Devolve True se mandou ligar."""
    if site_responde(): return False
    pythonw = Path(sys.executable).with_name('pythonw.exe'); exe = pythonw if pythonw.exists() else Path(sys.executable)
    subprocess.Popen([str(exe), str(RAIZ / 'supervisor.py')], cwd=str(RAIZ), creationflags=SEM_JANELA if sys.platform == 'win32' else 0, close_fds=True)
    return True


if __name__ == '__main__': sys.exit(principal())
