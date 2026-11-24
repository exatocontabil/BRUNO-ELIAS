"""Atualizar o Exato Web pela própria tela (só administrador).

O administrador escolhe o arquivo `Exato_Web_Instalador_<versão>.exe`; o site confere o arquivo, guarda-o e pede a um pequeno auxiliar (`atualizar.pyw`) para rodar o instalador em
silêncio. O auxiliar é quem inicia o instalador (assim ele não morre quando o instalador desliga o site para trocar os arquivos). Os dados não são tocados: ficam fora da pasta do programa.
Só funciona numa instalação feita pelo instalador do Exato Web (a antiga, por pacote, continua com o atalho de atualizar)."""
import hashlib, json, re, subprocess, sys
from datetime import datetime
from pathlib import Path

from . import config

PASTA = 'atualizacao'; PEDIDO = 'atualizacao.json'
PADRAO_NOME = re.compile(r'^Exato_Web_Instalador_(\d+(?:\.\d+)*)\.exe$', re.I)
TAMANHO_MIN = 20 * 1024 * 1024; TAMANHO_MAX = 600 * 1024 * 1024


class AtualizacaoErro(Exception): pass


def raiz_instalada(raiz=None):
    """Pasta do programa instalado pelo instalador (onde existe o Python próprio), ou None se este Exato não foi instalado assim."""
    raiz = Path(raiz or config.RAIZ); base = raiz.parent
    return base if (base / 'python' / 'pythonw.exe').exists() and (raiz / 'atualizar.pyw').exists() else None


def versao_atual(raiz=None):
    try: t = (Path(raiz or config.RAIZ) / 'VERSAO.txt').read_text(encoding='utf-8-sig').strip()
    except OSError: return ''
    m = re.search(r'(\d+(?:\.\d+)*)\s*$', t); return m.group(1) if m else t


def versao_do_nome(nome):
    m = PADRAO_NOME.match(Path(nome or '').name); return m.group(1) if m else ''


def _num(v): return tuple(int(x) for x in re.findall(r'\d+', v or '')) or (0,)


def comparar(nova, atual):
    """1 = nova é mais recente; 0 = igual; -1 = mais antiga (ou não dá para comparar, tratada como a mesma)."""
    a, b = _num(nova), _num(atual)
    return (a > b) - (a < b)


def guardar(arquivo, nome, dados=None, ler=None):
    """Grava o arquivo enviado em <dados>/atualizacao (por partes, sem carregar tudo na memória) e confere. Devolve o caminho. Levanta AtualizacaoErro em português."""
    nome = Path(str(nome or '')).name
    if not PADRAO_NOME.match(nome): raise AtualizacaoErro('Esse não parece ser o arquivo de atualização do Exato. O nome deve ser parecido com Exato_Web_Instalador_20261124.11.exe.')
    pasta = Path(dados or config.DADOS) / PASTA; pasta.mkdir(parents=True, exist_ok=True)
    parcial = pasta / (nome + '.parcial'); total = 0
    try:
        with open(parcial, 'wb') as f:
            while True:
                bloco = arquivo.read(1024 * 1024)
                if not bloco: break
                total += len(bloco)
                if total > TAMANHO_MAX: raise AtualizacaoErro('O arquivo é grande demais para ser a atualização do Exato.')
                f.write(bloco)
        conferir(parcial)
        for velho in pasta.glob('Exato_Web_Instalador_*.exe'):
            try: velho.unlink()
            except OSError: pass
        destino = pasta / nome; parcial.replace(destino); return destino
    finally:
        try: parcial.unlink()
        except OSError: pass


def conferir(caminho):
    caminho = Path(caminho)
    try: tam = caminho.stat().st_size
    except OSError: raise AtualizacaoErro('Não consegui ler o arquivo enviado.')
    if tam < TAMANHO_MIN: raise AtualizacaoErro('O arquivo está pequeno demais ou incompleto. Baixe de novo e envie outra vez.')
    with open(caminho, 'rb') as f:
        if f.read(2) != b'MZ': raise AtualizacaoErro('Esse arquivo não é um instalador do Windows.')
    achou = False
    with open(caminho, 'rb') as f:
        cauda = b''
        while True:
            bloco = f.read(4 * 1024 * 1024)
            if not bloco: break
            if b'Inno Setup Setup Data' in cauda + bloco: achou = True; break
            cauda = bloco[-32:]
    if not achou: raise AtualizacaoErro('Esse arquivo não é um instalador do Exato Web.')


def sha(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def endereco_guardado(raiz=None):
    try: l = (Path(raiz or config.RAIZ) / 'endereco.txt').read_text(encoding='utf-8-sig').splitlines()[0].strip()
    except (OSError, IndexError): return ''
    return re.sub(r'^https?://', '', l).strip('/')


def comando_auxiliar(exe, raiz=None, dados=None, instalacao=None):
    """Linha de comando do auxiliar que roda o instalador (só montada aqui; testável)."""
    raiz = Path(raiz or config.RAIZ); inst = instalacao or raiz.parent
    pythonw = inst / 'python' / 'pythonw.exe'
    return [str(pythonw), str(raiz / 'atualizar.pyw'), str(exe), str(inst), str(dados or config.DADOS), endereco_guardado(raiz)]


def iniciar(exe, por='', dados=None, raiz=None, rodar=None):
    """Pede a atualização: registra o pedido e chama o auxiliar. Depois disso o site vai sair do ar e voltar sozinho."""
    inst = raiz_instalada(raiz)
    if not inst: raise AtualizacaoErro('Este Exato não foi instalado pelo instalador novo. Para atualizar, rode o instalador novo no computador onde o Exato está.')
    dados = Path(dados or config.DADOS)
    Path(dados, PEDIDO).write_text(json.dumps({'arquivo': Path(exe).name, 'de': versao_atual(raiz), 'para': versao_do_nome(Path(exe).name), 'pedido_em': datetime.now().isoformat(timespec='seconds'), 'por': por}, ensure_ascii=False), encoding='utf-8')
    (dados / 'logs').mkdir(parents=True, exist_ok=True)
    (rodar or subprocess.Popen)(comando_auxiliar(exe, raiz, dados, inst), cwd=str(Path(raiz or config.RAIZ)), close_fds=True)


def ultimo_pedido(dados=None):
    try: return json.loads(Path(dados or config.DADOS, PEDIDO).read_text(encoding='utf-8'))
    except Exception: return None


def resultado(dados=None, raiz=None):
    """Texto para a tela depois de uma atualização: ('ok'|'falhou'|'', mensagem)."""
    p = ultimo_pedido(dados)
    if not p: return '', ''
    atual = versao_atual(raiz)
    if p.get('para') and atual == p['para']: return 'ok', f"O Exato foi atualizado para a versão {atual} em {p['pedido_em'][8:10]}/{p['pedido_em'][5:7]} às {p['pedido_em'][11:16]}."
    if p.get('para') and atual == p.get('de'): return 'falhou', 'A última atualização não terminou: o Exato continua na versão anterior. Tente de novo ou fale com o suporte.'
    return '', ''
