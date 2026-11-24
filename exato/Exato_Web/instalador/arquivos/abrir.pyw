"""Atalho "Exato Web": liga o Exato se preciso, espera ficar pronto e abre no navegador."""
import sys, time, webbrowser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from supervisor import iniciar_se_preciso, ligar_endereco, site_responde, pasta_dados, RAIZ, PORTA


def _nome_do_caddyfile(arq):
    """Primeira linha 'nome.do.site {' do arquivo do endereço com cadeado (instalação antiga)."""
    try:
        for linha in arq.read_text(encoding='utf-8-sig').splitlines():
            t = linha.strip()
            if t.endswith('{') and '.' in t and not t.startswith(('{', '#')):
                return t[:-1].strip()
    except OSError: pass
    return ''


def _responde(nome, espera=0):
    """Responde na porta do cadeado? Com `espera`, tenta por esse tempo (o endereço pode estar acabando de ligar)."""
    import socket
    fim = time.time() + espera
    while True:
        try:
            with socket.create_connection((nome, 443), timeout=2): return True
        except OSError: pass
        if time.time() >= fim: return False
        time.sleep(1)


def endereco():
    """Endereço do escritório (com cadeado) se existir e responder; senão o endereço deste computador."""
    local = f'http://127.0.0.1:{PORTA}'
    candidatos = []
    try: candidatos.append(pasta_dados() / 'endereco.txt')
    except Exception: pass
    candidatos.append(RAIZ / 'endereco.txt')
    for arq in candidatos:
        try:
            linha = arq.read_text(encoding='utf-8-sig').splitlines()[0].strip()
            if linha.startswith('https://'):
                nome = linha[8:].strip('/')
                # Endereço com cadeado: liga e espera; se não responder, abre direto neste computador.
                if _responde(nome) or (ligar_endereco() or True) and _responde(nome, 30): return linha
                return local
            if linha.startswith('http'): return linha
        except (OSError, IndexError): pass
    # Quem já usava o endereço do escritório na instalação antiga: aproveita o mesmo nome, sem pedir nada.
    for antiga in (Path('C:/ExatoWeb'), Path.home() / 'ExatoWeb'):
        nome = _nome_do_caddyfile(antiga / 'caddy' / 'Caddyfile')
        if nome and (_responde(nome) or (ligar_endereco() or True) and _responde(nome, 25)):
            try: (pasta_dados() / 'endereco.txt').write_text(f'https://{nome}\n', encoding='utf-8')
            except Exception: pass
            return f'https://{nome}'
    return local


iniciar_se_preciso()
fim = time.time() + 60
while time.time() < fim and not site_responde(): time.sleep(1)
if site_responde(): webbrowser.open(endereco())
else:
    try:
        import tkinter; from tkinter import messagebox
        r = tkinter.Tk(); r.withdraw(); messagebox.showerror('Exato Web', 'O Exato não ligou. Espere um minuto e tente de novo. Se continuar, chame o suporte.'); r.destroy()
    except Exception: pass
