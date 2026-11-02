"""Sincronia entre os computadores pelo servidor do escritório (V182). Sem Tkinter.

A pasta do servidor (a mesma do Repositório) passa a guardar, em `<pasta>\\Repositório\\.indice\\`, o que precisa ser igual em qualquer computador:
- `empresas.json`: as empresas cadastradas (mescla por CNPJ; remoção SÓ pelo administrador, nunca apaga nota nem XML);
- `auditorias\\<CNPJ>.json`: o histórico de auditorias de cada empresa (mescla; nada some) e uma cópia do Excel do SAT usado, na pasta da empresa
  (`<empresa>\\<Ano>\\<Mês>\\Auditoria\\`), para reabrir a auditoria em outro computador;
- `versao.json`: formato dos arquivos compartilhados e a versão mais nova do Exato já vista. Um Exato mais velho que o formato do servidor NÃO grava
  (só lê e avisa para atualizar). A versão mais nova também guarda um pacote (`.atualizacao\\Exato_Central_Fiscal_Vxxx.zip`) para os outros computadores
  atualizarem sem receber ZIP.

Tudo é gravado por troca atômica (nunca fica pela metade), só cresce (mescla) e nunca levanta erro para a tela. Cada computador leva uma cópia no banco
local: fora do escritório o Exato mostra o que sincronizou da última vez.
"""
from __future__ import annotations
import json, os, re, shutil, tempfile, time, zipfile
from datetime import datetime
from pathlib import Path

import exato_repositorio as repo

FORMATO = 1                      # sobe quando um arquivo compartilhado muda de jeito (quem tem formato menor deixa de gravar)
ARQ_EMPRESAS = 'empresas.json'
ARQ_VERSAO = 'versao.json'
PASTA_AUDITORIAS = 'auditorias'
PASTA_ATUALIZACAO = '.atualizacao'
MAX_AUDITORIAS = 500


def _indice(base):
    return repo._pasta_repo(base) / repo.PASTA_INDICE


def _agora():
    return datetime.now().isoformat(timespec='seconds')


def _ler_json(caminho):
    try:
        with open(repo._longo(caminho), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _gravar_json(caminho, dados, tag='x'):
    """Troca atômica. Devolve True se gravou."""
    try:
        caminho = Path(caminho); os.makedirs(repo._longo(caminho.parent), exist_ok=True)
        tmp = caminho.with_name(f'.{caminho.name}.{tag}.{os.getpid()}.tmp')
        with open(repo._longo(tmp), 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False); f.flush()
            try: os.fsync(f.fileno())
            except Exception: pass
        for tentativa in range(4):
            try:
                os.replace(repo._longo(tmp), repo._longo(caminho)); return True
            except OSError:
                if tentativa == 3:
                    try: os.remove(repo._longo(tmp))
                    except OSError: pass
                    return False
                time.sleep(0.4 * (tentativa + 1))
    except Exception:
        return False
    return False


def _digitos(x):
    return re.sub(r'\D', '', str(x or ''))


# ------------------------------------------------------------------ versão e formato
def numero_versao(texto):
    """'V182' -> 182 (0 se não der para ler)."""
    m = re.search(r'(\d+)', str(texto or ''))
    return int(m.group(1)) if m else 0


def ler_versao(base):
    d = _ler_json(_indice(base) / ARQ_VERSAO)
    return d if isinstance(d, dict) else {}


def avaliar_versao(base, versao_app, formato=FORMATO):
    """{'pode_gravar','mais_nova','atualizar','motivo'}: pode gravar no servidor? há versão mais nova para instalar? Sem arquivo no servidor = pode gravar."""
    info = ler_versao(base)
    srv_formato = int(info.get('formato') or 0) if str(info.get('formato') or '0').isdigit() else 0
    mais_nova = str(info.get('mais_nova') or '')
    pode = srv_formato <= formato
    return {'pode_gravar': pode, 'mais_nova': mais_nova, 'atualizar': numero_versao(mais_nova) > numero_versao(versao_app) and bool(info.get('pacote')),
            'pacote': str(info.get('pacote') or ''), 'motivo': '' if pode else 'versao_antiga'}


def registrar_versao(base, versao_app, computador='', formato=FORMATO, pacote=''):
    """Anota no servidor a versão mais nova (só cresce) e o formato mais novo. Devolve True se mudou algo."""
    atual = ler_versao(base); novo = dict(atual); mexeu = False
    if formato > int(atual.get('formato') or 0): novo['formato'] = formato; mexeu = True
    if numero_versao(versao_app) > numero_versao(atual.get('mais_nova')):
        novo['mais_nova'] = versao_app; novo['publicado_em'] = _agora(); novo['por'] = repo.nome_seguro(computador or '', 30)
        if pacote: novo['pacote'] = pacote
        mexeu = True
    elif pacote and numero_versao(versao_app) == numero_versao(atual.get('mais_nova')) and not atual.get('pacote'):
        novo['pacote'] = pacote; mexeu = True
    if not mexeu: return False
    novo.setdefault('formato', formato)
    return _gravar_json(_indice(base) / ARQ_VERSAO, novo, 'versao')


def montar_pacote(raiz, destino_zip):
    """Zip da instalação (INICIAR.bat, LEIA-ME.txt, VERSAO.txt, programa, ferramentas, ajuda) para os outros computadores. Devolve o caminho ou ''."""
    raiz = Path(raiz)
    if not (raiz / 'programa').is_dir() or not (raiz / 'INICIAR.bat').exists(): return ''
    destino_zip = Path(destino_zip); os.makedirs(repo._longo(destino_zip.parent), exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix='exato_pkg_'))
    try:
        z_tmp = tmp / 'pacote.zip'
        with zipfile.ZipFile(z_tmp, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for item in ('INICIAR.bat', 'LEIA-ME.txt', 'VERSAO.txt'):
                if (raiz / item).exists(): z.write(raiz / item, f'{raiz.name}/{item}')
            for pasta in ('programa', 'ferramentas', 'ajuda'):
                for r, dirs, nomes in os.walk(raiz / pasta):
                    dirs[:] = [d for d in dirs if d != '__pycache__']
                    for n in nomes:
                        if n.endswith('.pyc'): continue
                        p = Path(r) / n; z.write(p, f'{raiz.name}/{p.relative_to(raiz).as_posix()}')
        parcial = Path(str(destino_zip) + '.tmp')
        shutil.copyfile(z_tmp, repo._longo(parcial)); os.replace(repo._longo(parcial), repo._longo(destino_zip))
        return str(destino_zip)
    except Exception:
        return ''
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def publicar_pacote(base, raiz, versao_app):
    """Guarda o pacote desta versão no servidor (uma vez por versão) e devolve o caminho relativo gravado em `versao.json`, ou ''."""
    rel = f'{PASTA_ATUALIZACAO}/Exato_Central_Fiscal_{versao_app}.zip'
    alvo = repo._pasta_repo(base) / PASTA_ATUALIZACAO / f'Exato_Central_Fiscal_{versao_app}.zip'
    if os.path.exists(repo._longo(alvo)): return rel
    return rel if montar_pacote(raiz, alvo) else ''


def instalar_pacote(base, pacote_rel, pasta_destino_pai):
    """Extrai o pacote do servidor numa pasta nova ao lado da instalação atual (a atual fica intacta). Devolve a pasta criada ou ''."""
    zip_srv = repo._pasta_repo(base) / pacote_rel
    if not os.path.exists(repo._longo(zip_srv)): return ''
    tmp = Path(tempfile.mkdtemp(prefix='exato_upd_'))
    try:
        local = tmp / 'pacote.zip'; shutil.copyfile(repo._longo(zip_srv), local)
        with zipfile.ZipFile(local) as z:
            nomes = z.namelist(); raiz = nomes[0].split('/')[0] if nomes else ''
            if not raiz or any(not n.startswith(raiz + '/') for n in nomes): return ''
            destino = Path(pasta_destino_pai) / raiz
            if destino.exists(): return str(destino)
            z.extractall(tmp / 'x'); shutil.move(str(tmp / 'x' / raiz), str(destino))
        return str(destino)
    except Exception:
        return ''
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ empresas
def ler_empresas(base):
    """{cnpj: {'nome','removida',...}} do servidor, ou None se o servidor não responde / ainda não existe."""
    d = _ler_json(_indice(base) / ARQ_EMPRESAS)
    if isinstance(d, dict) and isinstance(d.get('empresas'), dict): return d['empresas']
    return None


def comparar_empresas(servidor, locais, removidas_locais=()):
    """O que fazer depois de ler o servidor. `locais`: [(cnpj, nome)]; `removidas_locais`: CNPJs removidos neste computador.
    Devolve {'entram': [(cnpj, nome)] (estão no servidor e não aqui), 'saem': [cnpj] (removidas no servidor, ainda aqui), 'sobem': [(cnpj, nome)] (daqui, faltam lá),
    'removidas_sobem': [cnpj] (removidas aqui, ainda ativas lá)}."""
    servidor = servidor or {}; locais_map = {_digitos(c): n for c, n in locais}; rem_loc = {_digitos(c) for c in removidas_locais}
    entram = [(c, e.get('nome') or '') for c, e in servidor.items() if not e.get('removida') and c not in locais_map and c not in rem_loc]
    saem = [c for c, e in servidor.items() if e.get('removida') and c in locais_map]
    sobem = [(c, n) for c, n in locais_map.items() if c not in servidor]
    removidas_sobem = [c for c in rem_loc if not (servidor.get(c) or {}).get('removida')]
    return {'entram': sorted(entram, key=lambda x: x[1].casefold()), 'saem': saem, 'sobem': sobem, 'removidas_sobem': removidas_sobem}


def publicar_empresas(base, locais, removidas=None, computador=''):
    """Junta com o que já está no servidor (nunca apaga empresa). `locais`: [(cnpj, nome)] ativas aqui; `removidas`: {cnpj: quem} removidas por administrador.
    Devolve True se gravou alguma novidade."""
    try:
        atual = ler_empresas(base) or {}; novo = {c: dict(e) for c, e in atual.items()}; mexeu = False; por = repo.nome_seguro(computador or '', 30)
        for c, n in locais or []:
            c = _digitos(c)
            if len(c) != 14: continue
            nome = str(n or '').strip(); nome = '' if re.match(r'(?i)^empresa_\d+$', nome) else nome
            if c not in novo:
                novo[c] = {'nome': nome, 'cadastrada_em': _agora(), 'por': por, 'removida': False}; mexeu = True
            elif nome and not novo[c].get('nome') and not novo[c].get('removida'):
                novo[c]['nome'] = nome; mexeu = True
        for c, quem in (removidas or {}).items():
            c = _digitos(c)
            if len(c) == 14 and not (novo.get(c) or {}).get('removida'):
                e = novo.setdefault(c, {'nome': '', 'cadastrada_em': _agora(), 'por': por})
                e.update(removida=True, removida_em=_agora(), removida_por=str(quem or '')); mexeu = True
        if not mexeu: return False
        return _gravar_json(_indice(base) / ARQ_EMPRESAS, {'versao': 1, 'atualizado_em': _agora(), 'empresas': novo}, 'empresas')
    except Exception:
        return False


def reativar_empresa(base, cnpj, computador=''):
    """O administrador cadastrou de novo uma empresa removida: volta a valer em todos os computadores."""
    try:
        c = _digitos(cnpj); atual = ler_empresas(base) or {}
        if not (atual.get(c) or {}).get('removida'): return False
        atual[c].update(removida=False, reativada_em=_agora()); atual[c].pop('removida_em', None); atual[c].pop('removida_por', None)
        return _gravar_json(_indice(base) / ARQ_EMPRESAS, {'versao': 1, 'atualizado_em': _agora(), 'empresas': atual}, 'empresas')
    except Exception:
        return False


# ------------------------------------------------------------------ auditorias
def _chave_auditoria(e):
    return (str(e.get('timestamp') or ''), _digitos(e.get('cnpj')), str(e.get('family') or ''), tuple(sorted(str(x) for x in (e.get('source_files') or []))))


def mesclar_auditorias(*listas):
    """União de listas de entradas de histórico (sem repetir), da mais nova para a mais antiga, limitada a MAX_AUDITORIAS por lista final."""
    vistos = {}
    for lista in listas:
        for e in lista or []:
            if isinstance(e, dict): vistos.setdefault(_chave_auditoria(e), e)
    return sorted(vistos.values(), key=lambda e: str(e.get('timestamp') or ''), reverse=True)[:MAX_AUDITORIAS]


def ler_auditorias(base):
    """Todas as entradas de histórico guardadas no servidor (todas as empresas)."""
    pasta = _indice(base) / PASTA_AUDITORIAS; saida = []
    try:
        for nome in os.listdir(repo._longo(pasta)):
            if nome.endswith('.json') and not nome.startswith('.'):
                d = _ler_json(pasta / nome)
                if isinstance(d, list): saida += [e for e in d if isinstance(e, dict)]
    except OSError:
        pass
    return saida


def publicar_auditorias(base, entradas):
    """Grava no servidor as entradas (uma lista por empresa, mesclada com a que já existe). Devolve quantas entradas novas foram para o servidor."""
    novas = 0
    try:
        por_cnpj = {}
        for e in entradas or []:
            c = _digitos(e.get('cnpj'))
            if len(c) == 14: por_cnpj.setdefault(c, []).append(e)
        for c, lista in por_cnpj.items():
            caminho = _indice(base) / PASTA_AUDITORIAS / f'{c}.json'
            atual = _ler_json(caminho); atual = atual if isinstance(atual, list) else []
            antes = {_chave_auditoria(e) for e in atual}
            juntas = mesclar_auditorias(atual, lista)
            depois = {_chave_auditoria(e) for e in juntas}
            if depois - antes or len(juntas) != len(atual):
                if _gravar_json(caminho, juntas, 'aud'): novas += len(depois - antes)
    except Exception:
        pass
    return novas


def _copiar_sem_sobrescrever(origem, destino):
    """Copia o arquivo se o destino não existe. Devolve True se copiou."""
    try:
        destino = Path(destino)
        if os.path.exists(repo._longo(destino)): return False
        os.makedirs(repo._longo(destino.parent), exist_ok=True)
        parcial = Path(str(destino) + '.tmp'); shutil.copyfile(repo._longo(origem), repo._longo(parcial)); os.replace(repo._longo(parcial), repo._longo(destino))
        return True
    except OSError:
        return False


def subir_excels(base, pasta_empresa, periodo_inicio, arquivos):
    """Copia os Excel do SAT usados numa auditoria para `<Repositório>\\<empresa>\\<Ano>\\<Mês>\\Auditoria\\` (sem sobrescrever). Devolve quantos subiram."""
    m = re.match(r'(\d{4})-(\d{2})', str(periodo_inicio or ''))
    ano, mes = (m.group(1), m.group(2)) if m else ('Sem data', '00')
    destino = repo._pasta_repo(base) / pasta_empresa / ano / mes / 'Auditoria'; n = 0
    for a in arquivos or []:
        if a and os.path.exists(str(a)) and _copiar_sem_sobrescrever(a, destino / Path(a).name): n += 1
    return n


def trazer_excels(base, pasta_local):
    """Traz para `pasta_local` (SAT_AUDITORIA deste computador) os Excel das auditorias guardados no servidor que ainda não existem aqui. Devolve quantos vieram."""
    n = 0; raiz = repo._pasta_repo(base)
    try:
        for emp in os.listdir(repo._longo(raiz)):
            if emp.startswith('.') or not repo.cnpj_no_nome(emp): continue
            for r, _d, nomes in os.walk(repo._longo(raiz / emp)):
                if os.path.basename(r) != 'Auditoria': continue
                for nome in nomes:
                    if nome.startswith('.') or nome.endswith('.tmp'): continue
                    if list(Path(pasta_local).rglob(nome)) if Path(pasta_local).exists() else []: continue
                    if _copiar_sem_sobrescrever(os.path.join(r, nome), Path(pasta_local) / 'servidor' / nome): n += 1
    except OSError:
        pass
    return n
