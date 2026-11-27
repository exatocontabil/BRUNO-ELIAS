"""Endereço seguro do escritório (com cadeado) para o Exato Web instalado pelo instalador.

O Exato abre em https://<nome do escritório> (por exemplo fiscal.seuescritorio.com.br): um programinha de apoio (Caddy, já dentro do instalador) recebe o endereço seguro e entrega ao site.
Uma só vez, com permissão de administrador, `configurar` prepara o computador: escreve a configuração, faz o computador reconhecer o nome, libera a porta do cadeado para a rede do
escritório e faz o Windows confiar no certificado do escritório. Depois, o supervisor (sem permissão especial) mantém o programinha ligado junto com o site.
Instalações antigas (endereço montado à mão em C:\\ExatoWeb) ficam como estão: `modo` = 'legado'."""
import json, os, re, subprocess, sys, time
from pathlib import Path

SEM_JANELA = 0x08000000
MARCA_HOSTS = '# Exato Web'
REGRA_FIREWALL = 'Exato Web (endereco do escritorio)'
_NOME = re.compile(r'[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+')


def normalizar(nome):
    n = str(nome or '').strip().lower()
    n = re.sub(r'^https?://', '', n)
    return n.split('/')[0].strip('.')


def nome_valido(nome):
    n = normalizar(nome); return bool(n) and len(n) <= 100 and bool(_NOME.fullmatch(n))


def pasta_caddy(dados): return Path(dados) / 'caddy'
def exe_caddy(app_dir): return Path(app_dir).parent / 'caddy' / 'caddy.exe'
def arquivo_config(dados): return pasta_caddy(dados) / 'Caddyfile'
def ca_raiz(dados): return pasta_caddy(dados) / 'dados' / 'caddy' / 'pki' / 'authorities' / 'local' / 'root.crt'
def arquivo_marca(dados): return pasta_caddy(dados) / 'configurado.json'


def caddyfile(nome, porta_site=8443):
    return ('{\n\tauto_https disable_redirects\n}\n' + f'{normalizar(nome)} {{\n\ttls internal\n\tencode gzip\n\treverse_proxy 127.0.0.1:{int(porta_site)}\n}}\n')


def ambiente(dados):
    env = dict(os.environ); base = str(pasta_caddy(dados) / 'dados'); env['XDG_DATA_HOME'] = base; env['XDG_CONFIG_HOME'] = base; return env


def hosts_com(texto, nome, ip='127.0.0.1'):
    """O arquivo de nomes do computador com `nome` apontando para `ip` (troca a linha antiga do Exato; não repete)."""
    nome = normalizar(nome); linhas = [l for l in (texto or '').splitlines() if not (MARCA_HOSTS in l or re.search(r'\s' + re.escape(nome) + r'(\s|$)', l))]
    while linhas and not linhas[-1].strip(): linhas.pop()
    linhas.append(f'{ip}\t{nome}\t{MARCA_HOSTS}'); return '\r\n'.join(linhas) + '\r\n'


def configurado(dados):
    try: return json.loads(arquivo_marca(dados).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError): return {}


def marcar(dados, nome, modo):
    pasta_caddy(dados).mkdir(parents=True, exist_ok=True)
    arquivo_marca(dados).write_text(json.dumps({'nome': normalizar(nome), 'modo': modo, 'versao': 1}, ensure_ascii=False), encoding='utf-8')


def _rodar(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, creationflags=SEM_JANELA if sys.platform == 'win32' else 0, **kw)


def _administrador():
    try:
        import ctypes; return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False


def _log_caddy(dados, nome='caddy.log'):
    """Arquivo onde o programinha do cadeado escreve o que está acontecendo (ajuda o suporte)."""
    try:
        (Path(dados) / 'logs').mkdir(parents=True, exist_ok=True); return open(Path(dados) / 'logs' / nome, 'ab')
    except OSError: return subprocess.DEVNULL


def _parar_caddy_do_exato(dados):
    """Desliga o programinha do cadeado que o supervisor tenha ligado (para liberar a porta durante a configuração)."""
    pidf = Path(dados) / 'caddy.pid'
    try: pid = int(pidf.read_text(encoding='ascii').strip())
    except (OSError, ValueError): return
    if sys.platform == 'win32': _rodar(['taskkill', '/PID', str(pid), '/T', '/F'])
    try: pidf.unlink()
    except OSError: pass


def configurar(app_dir, dados, nome, hosts=None, esperar_ca=60):
    """Prepara o computador para o endereço seguro. Precisa de permissão de administrador. Devolve (ok, mensagem em português)."""
    nome = normalizar(nome); dados = Path(dados); exe = exe_caddy(app_dir)
    if not nome_valido(nome): return False, 'O endereço do escritório não parece válido. Use algo como fiscal.seuescritorio.com.br.'
    if not exe.exists(): return False, 'O programa do endereço seguro não está na instalação.'
    if sys.platform == 'win32' and not _administrador(): return False, 'É preciso permissão de administrador para preparar o endereço seguro.'
    _parar_caddy_do_exato(dados)
    pasta_caddy(dados).mkdir(parents=True, exist_ok=True); arquivo_config(dados).write_text(caddyfile(nome), encoding='ascii')
    hosts = Path(hosts or os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'drivers', 'etc', 'hosts'))
    try:
        atual = hosts.read_text(encoding='utf-8', errors='replace') if hosts.exists() else ''; novo = hosts_com(atual, nome)
        if novo != atual: hosts.write_text(novo, encoding='ascii', errors='replace')
    except OSError: return False, 'Não consegui registrar o endereço neste computador.'
    if sys.platform == 'win32':
        _rodar(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', f'name={REGRA_FIREWALL}'])
        r = _rodar(['netsh', 'advfirewall', 'firewall', 'add', 'rule', f'name={REGRA_FIREWALL}', 'dir=in', 'action=allow', 'protocol=TCP', 'localport=443', 'remoteip=localsubnet', 'profile=any'])
        if r.returncode != 0: return False, 'Não consegui liberar o endereço seguro para a rede do escritório.'
    # liga o programinha só para ele criar o certificado do escritório, confia nele e desliga
    p = subprocess.Popen([str(exe), 'run', '--config', str(arquivo_config(dados)), '--adapter', 'caddyfile'], cwd=str(pasta_caddy(dados)), env=ambiente(dados), stdout=_log_caddy(dados, 'caddy_preparo.log'), stderr=subprocess.STDOUT, creationflags=SEM_JANELA if sys.platform == 'win32' else 0)
    try:
        for _ in range(int(esperar_ca)):
            if ca_raiz(dados).exists() or p.poll() is not None: break
            time.sleep(1)
        if not ca_raiz(dados).exists(): return False, 'O certificado do escritório não foi criado. Confira se a porta do endereço seguro não está em uso por outro programa.'
        if sys.platform == 'win32':
            r = _rodar(['certutil', '-addstore', '-f', 'Root', str(ca_raiz(dados))])
            if r.returncode != 0: return False, 'Não consegui fazer o Windows confiar no certificado do escritório.'
        saida = pasta_caddy(dados) / 'para_os_outros_pcs'; saida.mkdir(parents=True, exist_ok=True)
        (saida / 'CERTIFICADO_DO_ESCRITORIO.crt').write_bytes(ca_raiz(dados).read_bytes())
    finally:
        try: p.terminate(); p.wait(10)
        except Exception:
            try: p.kill()
            except Exception: pass
    marcar(dados, nome, 'novo'); return True, 'Endereço seguro pronto.'


def supervisionar_caddy(app_dir, dados, parar, abrir=None, esperar=time.sleep, agora=time.time, max_rapidas=5):
    """Mantém o programinha do cadeado ligado (religa se cair). `parar` é um threading.Event; ao ser acionado, desliga. Só age se a configuração é do modo 'novo'."""
    if configurado(dados).get('modo') != 'novo': return
    exe = exe_caddy(app_dir); cfg = arquivo_config(dados)
    if not exe.exists() or not cfg.exists(): return
    abrir = abrir or (lambda: subprocess.Popen([str(exe), 'run', '--config', str(cfg), '--adapter', 'caddyfile'], cwd=str(pasta_caddy(dados)), env=ambiente(dados), stdout=_log_caddy(dados), stderr=subprocess.STDOUT, creationflags=SEM_JANELA if sys.platform == 'win32' else 0))
    rapidas = 0; pidf = Path(dados) / 'caddy.pid'
    while not parar.is_set():
        inicio = agora(); p = abrir()
        try: pidf.write_text(str(getattr(p, 'pid', 0)), encoding='ascii')
        except OSError: pass
        while p.poll() is None and not parar.is_set(): parar.wait(1)
        if parar.is_set():
            try: p.terminate()
            except Exception: pass
            break
        rapidas = rapidas + 1 if agora() - inicio < 60 else 0; esperar(30 if rapidas >= max_rapidas else 3)
    try: pidf.unlink()
    except OSError: pass
