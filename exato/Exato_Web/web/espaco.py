"""Espaço em disco do Exato Web: quanto cada parte ocupa e uma limpeza SEGURA só do que se refaz sozinho.

Regras (pedido do usuário: o disco C: vive cheio):
- A medição roda em segundo plano (pastas grandes levam tempo) e fica guardada por alguns minutos.
- A limpeza é por LISTA BRANCA, só dentro da pasta de dados do Exato: instaladores baixados, relatórios em PDF e ZIPs de exportação antigos, e as pastas
  "dados guardados antes de uma restauração". NUNCA toca em empresas e notas (banco), certificados, auditorias, usuários, nem nas cópias de XML.
- Não segue atalhos/junções, nunca apaga fora da pasta de dados, e conta o que apagou."""
import os, shutil, threading, time
from datetime import datetime, timedelta
from pathlib import Path

from . import config

IDADE_DIAS = 30
LIMITE_AVISO = 1024 * 1024 * 1024          # abaixo de 1 GB livre: aviso em todas as telas do administrador
LIMITE_CRITICO = 300 * 1024 * 1024
_trava = threading.Lock()
medicao = {'rodando': False, 'inicio': '', 'fim': '', 'itens': [], 'disco': {}, 'erro': ''}

# (chave, nome na tela, o que é, limpável?)
PARTES = (
    ('nucleo', 'Empresas e notas', 'O banco do Exato: empresas, notas (XML), usuários e histórico. É o coração do Exato e fica no C:.', False),
    ('copias', 'Cópias dos XMLs (Repositório)', 'Os XMLs organizados em pastas. Dá para guardar em outro lugar (servidor).', False),
    ('cofre', 'Certificados', 'Os certificados A1 guardados com segurança.', False),
    ('auditorias', 'Auditorias', 'Resultados das auditorias já feitas.', False),
    ('atualizacao', 'Instaladores baixados', 'Arquivos de atualização já usados. Podem ser apagados.', True),
    ('relatorios', 'Relatórios em PDF', 'Relatórios gerados. Se precisar, o Exato gera de novo.', True),
    ('exportacoes', 'ZIPs de XML para baixar', 'Pacotes gerados na tela Baixar XMLs. Se precisar, o Exato gera de novo.', True),
    ('restauracao', 'Dados guardados antes de uma restauração', 'Cópia do que existia antes de restaurar uma cópia de segurança. Apague só se a restauração deu certo.', True),
    ('logs', 'Registros de funcionamento', 'Para o suporte achar problemas.', False),
)


def _conta(pasta, limite_s=40.0):
    """Soma dos tamanhos de uma pasta (sem seguir atalhos). Devolve (bytes, arquivos, completo)."""
    total = n = 0; fim = time.time() + limite_s; pilha = [str(pasta)]
    while pilha:
        if time.time() > fim: return total, n, False
        d = pilha.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_symlink(): continue
                        if e.is_dir(follow_symlinks=False): pilha.append(e.path)
                        elif e.is_file(follow_symlinks=False): total += e.stat(follow_symlinks=False).st_size; n += 1
                    except OSError: continue
        except OSError: continue
    return total, n, True


def pastas(dados=None, arquivos=None):
    """Onde está cada parte (lista de (chave, [pastas ou arquivos]))."""
    dados = Path(dados or config.DADOS); arquivos = Path(arquivos or config.ARQUIVOS)
    antes = sorted(p for p in dados.glob('_antes_da_restauracao_*') if p.is_dir())
    prep = dados / '_restauracao_preparo'
    return {'nucleo': [dados / 'nucleo', dados / 'web.db'], 'copias': [arquivos], 'cofre': [dados / 'cofre'], 'auditorias': [dados / 'auditorias'], 'atualizacao': [dados / 'atualizacao'],
            'relatorios': [dados / 'relatorios'], 'exportacoes': [dados / 'exportacoes'], 'restauracao': antes + ([prep] if prep.exists() else []), 'logs': [dados / 'logs']}


def _tam(caminho):
    p = Path(caminho)
    if p.is_file():
        try: return p.stat().st_size, 1, True
        except OSError: return 0, 0, True
    if p.is_dir(): return _conta(p)
    return 0, 0, True


def disco_de(pasta):
    try: u = shutil.disk_usage(str(pasta)); return {'total': u.total, 'usado': u.used, 'livre': u.free}
    except OSError: return {'total': 0, 'usado': 0, 'livre': 0}


def medir(dados=None, arquivos=None):
    """Mede tudo (bloqueia). Devolve o dicionário no formato de `medicao`."""
    dados = Path(dados or config.DADOS); mapa = pastas(dados, arquivos); itens = []
    for chave, nome, que, limpavel in PARTES:
        b = n = 0; completo = True
        for p in mapa.get(chave, []):
            x, y, c = _tam(p); b += x; n += y; completo = completo and c
        itens.append({'chave': chave, 'nome': nome, 'que': que, 'limpavel': limpavel, 'bytes': b, 'arquivos': n, 'completo': completo, 'onde': str((mapa.get(chave) or [''])[0])})
    return {'itens': itens, 'disco': disco_de(dados), 'disco_copias': disco_de(arquivos or config.ARQUIVOS)}


def medir_em_segundo_plano(dados=None, arquivos=None, forcar=False):
    """Começa a medir (uma só vez por vez). Reaproveita a medida de menos de 5 minutos, a não ser que `forcar`."""
    with _trava:
        if medicao['rodando']: return False
        if not forcar and medicao['fim']:
            try:
                if datetime.now() - datetime.fromisoformat(medicao['fim']) < timedelta(minutes=5): return False
            except ValueError: pass
        medicao.update(rodando=True, inicio=datetime.now().isoformat(timespec='seconds'), erro='')
    def tarefa():
        try:
            r = medir(dados, arquivos); medicao.update(itens=r['itens'], disco=r['disco'], disco_copias=r['disco_copias'], fim=datetime.now().isoformat(timespec='seconds'))
        except Exception: medicao['erro'] = 'Não consegui medir o espaço agora.'
        finally: medicao['rodando'] = False
    threading.Thread(target=tarefa, daemon=True, name='medir-espaco').start(); return True


# ------------------------------------------------------------------ limpeza segura
def _e_atalho(p):
    try:
        if os.path.islink(p): return True
        st = os.lstat(p); return bool(getattr(st, 'st_file_attributes', 0) & 0x400)          # junção/atalho do Windows
    except OSError: return True


def _dentro(p, base):
    try: Path(p).resolve().relative_to(Path(base).resolve()); return True
    except Exception: return False


def _apagar_arquivo(p, base, antes_de=None):
    p = Path(p)
    if _e_atalho(p) or not _dentro(p, base): return 0
    try:
        st = p.stat()
        if antes_de and datetime.fromtimestamp(st.st_mtime) > antes_de: return 0
        p.unlink(); return st.st_size
    except OSError: return 0


def _apagar_pasta(pasta, base):
    """Apaga os arquivos de uma pasta (sem seguir atalhos) e depois as pastas vazias. Devolve (bytes, arquivos)."""
    pasta = Path(pasta)
    if _e_atalho(pasta) or not _dentro(pasta, base) or pasta.resolve() == Path(base).resolve(): return 0, 0
    total = n = 0
    for raiz, dirs, arqs in os.walk(str(pasta), topdown=False, followlinks=False):
        for a in arqs:
            b = _apagar_arquivo(Path(raiz) / a, base)
            if b or not (Path(raiz) / a).exists(): total += b; n += 1
        try: os.rmdir(raiz)
        except OSError: pass
    return total, n


def limpar(chaves, dados=None, agora=None):
    """Apaga só o que está na lista branca e foi pedido. Devolve {'bytes', 'arquivos', 'por_parte': {chave: (bytes, arquivos)}}."""
    dados = Path(dados or config.DADOS); agora = agora or datetime.now(); corte = agora - timedelta(days=IDADE_DIAS); res = {'bytes': 0, 'arquivos': 0, 'por_parte': {}}
    for chave in chaves:
        b = n = 0
        if chave == 'atualizacao':
            pasta = dados / 'atualizacao'
            for p in (list(pasta.glob('Exato_Web_Instalador_*.exe')) + list(pasta.glob('*.parcial'))) if pasta.is_dir() else []:
                x = _apagar_arquivo(p, dados)
                if x: b += x; n += 1
        elif chave in ('relatorios', 'exportacoes'):
            pasta = dados / chave
            for p in (pasta.glob('*.pdf' if chave == 'relatorios' else '*.zip') if pasta.is_dir() else []):
                x = _apagar_arquivo(p, dados, antes_de=corte)
                if x: b += x; n += 1
        elif chave == 'restauracao':
            for p in sorted(dados.glob('_antes_da_restauracao_*')):
                if p.is_dir():
                    x, y = _apagar_pasta(p, dados); b += x; n += y
        else: continue          # qualquer outra coisa NUNCA é apagada
        res['por_parte'][chave] = (b, n); res['bytes'] += b; res['arquivos'] += n
    return res


def legivel(b):
    b = float(b or 0)
    for u in ('bytes', 'KB', 'MB', 'GB', 'TB'):
        if b < 1024 or u == 'TB': return (f'{b:.0f} {u}' if u in ('bytes', 'KB') else f'{b:.1f} {u}'.replace('.', ','))
        b /= 1024


def situacao_disco(livre):
    """'critico' | 'baixo' | '' para o aviso. Sem dado (0) não avisa."""
    if not livre: return ''
    return 'critico' if livre < LIMITE_CRITICO else ('baixo' if livre < LIMITE_AVISO else '')
