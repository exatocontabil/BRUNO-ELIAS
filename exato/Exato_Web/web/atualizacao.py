"""Atualizar o Exato Web pela própria tela (só administrador).

O administrador escolhe o arquivo `Exato_Web_Instalador_<versão>.exe`; o site confere o arquivo, guarda-o e pede a um pequeno auxiliar (`atualizar.pyw`) para rodar o instalador em
silêncio. O auxiliar é quem inicia o instalador (assim ele não morre quando o instalador desliga o site para trocar os arquivos). Os dados não são tocados: ficam fora da pasta do programa.
Só funciona numa instalação feita pelo instalador do Exato Web (a antiga, por pacote, continua com o atalho de atualizar)."""
import hashlib, json, os, re, shutil, subprocess, sys, threading
from datetime import datetime, timedelta
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
    garantir_espaco(pasta, 400 * 1048576)
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


# ------------------------------------------------------------------ atualização automática (consulta e baixa sozinho)
# O endereço fica num lugar PÚBLICO só com as versões novas (o código-fonte não está lá). Esse lugar guarda `versao.json` (versão, nome do arquivo, tamanho e a "impressão digital" SHA-256)
# e o instalador. O endereço de download do instalador é SEMPRE montado a partir do endereço da consulta (nunca vem de dentro do arquivo), e o arquivo só é aceito se bater com a impressão digital.
URL_PADRAO = 'https://github.com/exatocontabil/exato-web-atualizacoes/releases/latest/download/versao.json'
ESPERA_CONSULTA_HORAS = 24
estado = {'fase': '', 'bytes': 0, 'total': 0, 'erro': '', 'versao': ''}          # fase: '' | baixando | conferindo | reiniciando | erro
_trava = threading.Lock()


def url_de_consulta():
    return (os.environ.get('EXATO_WEB_ATUALIZACOES') or URL_PADRAO).strip()


def _http(url, **kw):
    import httpx
    return httpx.Client(follow_redirects=True, timeout=kw.get('timeout', 20), headers={'User-Agent': 'ExatoWeb'})


def consultar(url=None, atual=None, cliente=None):
    """Pergunta ao lugar das atualizações se há versão nova. Devolve um dicionário:
    {'ok': bool, 'nova': bool, 'versao', 'arquivo', 'sha256', 'tamanho', 'notas', 'url_arquivo', 'erro'}. Nunca levanta erro: falha vira ok=False com texto em português."""
    url = url or url_de_consulta(); atual = versao_atual() if atual is None else atual
    r = {'ok': False, 'nova': False, 'versao': '', 'arquivo': '', 'sha256': '', 'tamanho': 0, 'notas': '', 'url_arquivo': '', 'erro': ''}
    if not url.lower().startswith('https://'): r['erro'] = 'O endereço das atualizações não é seguro.'; return r
    try:
        c = cliente or _http(url)
        resp = c.get(url)
        if resp.status_code == 404: r['erro'] = 'Ainda não há nenhuma versão publicada no lugar das atualizações.'; return r
        if resp.status_code != 200: r['erro'] = 'Não consegui consultar as atualizações agora. Tente de novo mais tarde.'; return r
        d = resp.json()
    except Exception:
        r['erro'] = 'Não consegui consultar as atualizações. Confira a internet deste computador.'; return r
    try:
        versao = str(d['versao']).strip(); arquivo = str(d['arquivo']).strip(); sha = str(d['sha256']).strip().lower(); tam = int(d['tamanho'])
    except Exception:
        r['erro'] = 'A resposta das atualizações veio incompleta.'; return r
    if not re.fullmatch(r'\d+(?:\.\d+)*', versao) or versao_do_nome(arquivo) != versao or not re.fullmatch(r'[0-9a-f]{64}', sha) or not (TAMANHO_MIN <= tam <= TAMANHO_MAX):
        r['erro'] = 'A resposta das atualizações não parece confiável e foi ignorada.'; return r
    base = url.rsplit('/', 1)[0] + '/'
    r.update(ok=True, versao=versao, arquivo=arquivo, sha256=sha, tamanho=tam, notas=str(d.get('notas') or '')[:600], url_arquivo=base + arquivo, nova=(comparar(versao, atual) > 0))
    return r


def garantir_espaco(dados, precisa):
    """Antes de baixar/gravar o instalador: confere se o disco aguenta (instalador + cópia dos arquivos trocados). Mensagem em português com o caminho para liberar espaço."""
    try: livre = shutil.disk_usage(str(dados)).free
    except OSError: return
    if livre < precisa:
        raise AtualizacaoErro(f'Falta espaço no disco para atualizar: são necessários uns {precisa // 1048576} MB livres e há só {livre // 1048576} MB. Abra "Espaço em disco" no menu, libere espaço e tente de novo.')


def baixar(info, dados=None, progresso=None, cliente=None):
    """Baixa o instalador novo (por partes) para <dados>/atualizacao e confere tamanho, impressão digital e tipo. Devolve o caminho. Levanta AtualizacaoErro em português."""
    pasta = Path(dados or config.DADOS) / PASTA; pasta.mkdir(parents=True, exist_ok=True)
    garantir_espaco(pasta, int(info['tamanho']) * 2 + 150 * 1048576)
    nome = info['arquivo']; parcial = pasta / (nome + '.parcial'); h = hashlib.sha256(); total = 0
    try:
        c = cliente or _http(info['url_arquivo'], timeout=60)
        with c.stream('GET', info['url_arquivo']) as resp:
            if resp.status_code != 200: raise AtualizacaoErro('Não consegui baixar a atualização agora. Tente de novo mais tarde.')
            with open(parcial, 'wb') as f:
                for bloco in resp.iter_bytes(1024 * 1024):
                    total += len(bloco)
                    if total > TAMANHO_MAX: raise AtualizacaoErro('O arquivo baixado é grande demais e foi descartado.')
                    h.update(bloco); f.write(bloco)
                    if progresso: progresso(total, info['tamanho'])
        if total != info['tamanho'] or h.hexdigest() != info['sha256']: raise AtualizacaoErro('O arquivo baixado veio incompleto ou diferente do esperado e foi descartado. Tente de novo.')
        conferir(parcial)
        for velho in pasta.glob('Exato_Web_Instalador_*.exe'):
            try: velho.unlink()
            except OSError: pass
        destino = pasta / nome; parcial.replace(destino); return destino
    except AtualizacaoErro: raise
    except Exception: raise AtualizacaoErro('A internet falhou durante o download. Tente de novo.')
    finally:
        try: parcial.unlink()
        except OSError: pass


def baixar_e_iniciar(info, por='', dados=None, raiz=None, cliente=None, rodar=None):
    """Roda em segundo plano: baixa, confere e pede a atualização. O andamento fica em `estado` (a tela consulta)."""
    if not _trava.acquire(blocking=False): return False
    def rodar_tudo():
        try:
            estado.update(fase='baixando', bytes=0, total=info['tamanho'], erro='', versao=info['versao'])
            exe = baixar(info, dados, lambda b, t: estado.update(bytes=b, total=t), cliente)
            estado.update(fase='conferindo'); iniciar(exe, por=por, dados=dados, raiz=raiz, rodar=rodar); estado.update(fase='reiniciando')
        except AtualizacaoErro as e: estado.update(fase='erro', erro=str(e))
        except Exception: estado.update(fase='erro', erro='Não consegui iniciar a atualização. Tente de novo.')
        finally: _trava.release()
    threading.Thread(target=rodar_tudo, daemon=True, name='atualizacao-download').start(); return True


def memoria(cfg):
    return cfg.setdefault('atualizacao', {})


def guardar_consulta(cfg, info, agora=None):
    """Lembra o resultado da consulta (para o aviso no menu e para consultar só uma vez por dia)."""
    m = memoria(cfg); m['ultima'] = (agora or datetime.now()).isoformat(timespec='seconds')
    m['nova'] = info['versao'] if (info.get('ok') and info.get('nova')) else ''; m['erro'] = '' if info.get('ok') else info.get('erro', '')
    m['notas'] = info.get('notas', '') if m['nova'] else ''


def consulta_devida(cfg, agora=None):
    try: return (agora or datetime.now()) - datetime.fromisoformat(memoria(cfg).get('ultima') or '') >= timedelta(hours=ESPERA_CONSULTA_HORAS)
    except Exception: return True
