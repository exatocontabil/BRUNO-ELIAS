"""Exato Web: endereço seguro do escritório (cadeado) feito pelo instalador: nome, configuração, arquivo de nomes, preparo e supervisão do programinha do cadeado."""
import os, stat, sys, tempfile, threading, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'instalador' / 'arquivos'))
import endereco as en

# nomes
assert en.normalizar(' HTTPS://Fiscal.Exemplo.com.br/ ') == 'fiscal.exemplo.com.br' and en.normalizar('http://a.b/x?y') == 'a.b' and en.normalizar('') == ''
for ok in ('fiscal.exemplo.com.br', 'exato-teste.test', 'a.b', 'x1.y2.z3'): assert en.nome_valido(ok), ok
for ruim in ('', 'semponto', 'com espaco.com', '-a.com', 'a..com', 'a.com;rm', '.com', 'a' * 120 + '.com', 'fiscal.exemplo.com/x'.replace('/x', ' x')): assert not en.nome_valido(ruim), ruim
# configuração do cadeado
c = en.caddyfile('Fiscal.Exemplo.com.br'); assert 'fiscal.exemplo.com.br {' in c and 'tls internal' in c and 'reverse_proxy 127.0.0.1:8443' in c and 'auto_https disable_redirects' in c
# arquivo de nomes do computador: idempotente, troca a linha do Exato, preserva o resto
base = '127.0.0.1\tlocalhost\r\n# comentario\r\n10.0.0.5\tfiscal.exemplo.com.br\r\n'
h = en.hosts_com(base, 'fiscal.exemplo.com.br'); assert h == '127.0.0.1\tlocalhost\r\n# comentario\r\n127.0.0.1\tfiscal.exemplo.com.br\t# Exato Web\r\n', repr(h)
assert en.hosts_com(h, 'fiscal.exemplo.com.br') == h and en.hosts_com('', 'a.b') == '127.0.0.1\ta.b\t# Exato Web\r\n'
h2 = en.hosts_com(h, 'outro.exemplo.com'); assert 'fiscal.exemplo.com.br' not in h2 and 'outro.exemplo.com' in h2 and 'localhost' in h2          # trocar de endereço troca a linha do Exato
# marca
d = Path(tempfile.mkdtemp(prefix='dados_')); assert en.configurado(d) == {}
en.marcar(d, 'Fiscal.Exemplo.com.br', 'novo'); assert en.configurado(d) == {'nome': 'fiscal.exemplo.com.br', 'modo': 'novo', 'versao': 1}
assert '"nome": "fiscal.exemplo.com.br"' in en.arquivo_marca(d).read_text(encoding='utf-8')          # o instalador procura exatamente este trecho

# preparo (com um "caddy" de mentira, fora do Windows)
def instalacao(corpo):
    raiz = Path(tempfile.mkdtemp(prefix='inst_')); (raiz / 'app').mkdir(); (raiz / 'caddy').mkdir()
    e = raiz / 'caddy' / 'caddy.exe'; e.write_text('#!/bin/sh\n' + corpo); e.chmod(e.stat().st_mode | stat.S_IEXEC); return raiz / 'app'
ok_caddy = 'mkdir -p "$XDG_DATA_HOME/caddy/pki/authorities/local"; echo CERT > "$XDG_DATA_HOME/caddy/pki/authorities/local/root.crt"; exec sleep 600\n'
app = instalacao(ok_caddy); dados = Path(tempfile.mkdtemp(prefix='dados_')); hosts = Path(tempfile.mkdtemp()) / 'hosts'; hosts.write_text('127.0.0.1\tlocalhost\n')
ok, msg = en.configurar(app, dados, 'fiscal.exemplo.com.br', hosts=hosts, esperar_ca=10); assert ok, msg
assert en.arquivo_config(dados).read_text().startswith('{') and 'fiscal.exemplo.com.br {' in en.arquivo_config(dados).read_text()
assert 'fiscal.exemplo.com.br\t# Exato Web' in hosts.read_text() and 'localhost' in hosts.read_text()
assert (en.pasta_caddy(dados) / 'para_os_outros_pcs' / 'CERTIFICADO_DO_ESCRITORIO.crt').read_text().strip() == 'CERT'
assert en.configurado(dados)['modo'] == 'novo'
# erros em português, sem marcar como pronto
assert en.configurar(app, dados, 'sem ponto', hosts=hosts, esperar_ca=1)[1].startswith('O endereço do escritório não parece válido')
sem = Path(tempfile.mkdtemp(prefix='inst_')) / 'app'; sem.mkdir(); assert 'não está na instalação' in en.configurar(sem, dados, 'a.b', hosts=hosts)[1]
app2 = instalacao('exit 0\n'); d2 = Path(tempfile.mkdtemp(prefix='dados_')); ok, msg = en.configurar(app2, d2, 'a.b', hosts=hosts, esperar_ca=3)
assert not ok and 'certificado do escritório não foi criado' in msg and en.configurado(d2) == {}

# supervisão do cadeado: só no modo novo; espera a configuração ficar pronta; religa se cair; desliga quando mandado
class Proc:
    def __init__(s, vive): s.pid = 4242; s.vivo = vive
    def poll(s): return None if s.vivo else 1
    def terminate(s): s.vivo = False
def esperar_ate(cond, seg=5):
    for _ in range(int(seg * 40)):
        if cond(): return True
        time.sleep(0.025)
    return False
abertos = []
sem_marca = Path(tempfile.mkdtemp()); parar = threading.Event()
t1 = threading.Thread(target=en.supervisionar_caddy, args=(app, sem_marca, parar), kwargs={'abrir': lambda: abertos.append(1) or Proc(True), 'espera_config': 0.05}); t1.start()
time.sleep(0.3); assert not abertos                                              # sem configuração: nada
dl = Path(tempfile.mkdtemp(prefix='dados_')); parar_b = threading.Event(); en.marcar(dl, 'a.b', 'legado')
t2 = threading.Thread(target=en.supervisionar_caddy, args=(app, dl, parar_b), kwargs={'abrir': lambda: abertos.append(2) or Proc(True), 'espera_config': 0.05}); t2.start()
time.sleep(0.3); assert not abertos                                              # instalação antiga (legado): não mexe
# a configuração fica pronta DEPOIS de o supervisor começar (o instalador prepara em paralelo): ele percebe e liga
en.pasta_caddy(sem_marca).mkdir(parents=True, exist_ok=True); en.arquivo_config(sem_marca).write_text('x'); en.marcar(sem_marca, 'a.b', 'novo')
assert esperar_ate(lambda: abertos == [1]), abertos
assert (sem_marca / 'caddy.pid').read_text() == '4242'
parar.set(); t1.join(5); parar_b.set(); t2.join(5); assert not t1.is_alive() and not t2.is_alive() and not (sem_marca / 'caddy.pid').exists()
# religa depois de cair
d.joinpath('caddy').mkdir(parents=True, exist_ok=True); en.arquivo_config(d).write_text('x'); procs = []
def abrir_real():
    p = Proc(len(procs) >= 1); procs.append(p); return p          # o 1º "cai" na hora, o 2º fica vivo
fim = threading.Event(); t3 = threading.Thread(target=en.supervisionar_caddy, args=(app, d, fim), kwargs={'abrir': abrir_real, 'esperar': lambda s: None}); t3.start()
assert esperar_ate(lambda: len(procs) >= 2) and (d / 'caddy.pid').exists()                                          # religou depois de cair e guardou o número
fim.set(); t3.join(5); assert not t3.is_alive() and not (d / 'caddy.pid').exists() and not procs[-1].vivo                              # parou: desligou e limpou
# o cadeado não tenta instalar o certificado sozinho (isso abriria uma janela de segurança no Windows): o instalador já fez
assert 'skip_install_trust' in en.caddyfile('a.b')
print('Exato Web (endereço seguro): OK')
