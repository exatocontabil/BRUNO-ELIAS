"""Busca compartilhada entre os computadores do escritório (V178). Sem Tkinter.

Objetivo: nenhum computador busca de novo o que outro já buscou. Depois de cada busca que termina bem, o Exato publica no servidor, ao lado do índice do
Repositório (`<pasta>\\Repositório\\.indice\\busca.json`), até onde cada empresa/fluxo foi buscado (ponto de continuação, "NSU") e até que dia (cobertura).
Ao buscar, o ponto de partida é o MAIS ADIANTADO entre o deste computador e o do servidor. As notas em si estão no Repositório (XMLs): "Trazer do servidor"
lê esses arquivos para o banco deste computador, sem baixar nada da SEFAZ.

O arquivo é gravado por troca atômica (nunca fica pela metade) e só cresce: quem publica junta com o que já estava (vale o maior). Repetir um pedaço de busca é
inofensivo (as notas não duplicam), então o conflito de dois computadores publicando ao mesmo tempo se resolve sozinho no próximo ciclo.
"""
from __future__ import annotations
import json, os, re, socket, time
from datetime import date, datetime
from pathlib import Path

import exato_repositorio as repo

ARQ = 'busca.json'
VERSAO = 1
TIPO_FAMILIA = {'NF-e': 'nfe', 'NFC-e': 'nfce', 'CT-e': 'cte', 'NFS-e': 'nfse'}


def caminho(base):
    return repo._pasta_repo(base) / repo.PASTA_INDICE / ARQ


def _vazio():
    return {'versao': VERSAO, 'nsu': {}, 'cobertura': {}}


def ler(base):
    """O arquivo compartilhado (dicionário) ou None se o servidor não responde / ainda não existe."""
    try:
        if not repo.pasta_acessivel(base, 4): return None
        with open(repo._longo(caminho(base)), 'r', encoding='utf-8') as f:
            dados = json.load(f)
        if isinstance(dados, dict) and isinstance(dados.get('nsu'), dict):
            dados.setdefault('cobertura', {}); return dados
    except (OSError, ValueError):
        pass
    return None


def _data(texto):
    try: return datetime.strptime(str(texto or '')[:10], '%Y-%m-%d').date()
    except ValueError: return None


def publicar(base, estados, coberturas, computador=''):
    """Junta com o que já está no servidor (vale o maior). `estados`: {chave 'cnpj:fluxo': nsu}; `coberturas`: {cnpj: {família: 'AAAA-MM-DD'}}.
    Devolve True se gravou alguma novidade. Nunca levanta erro."""
    try:
        if repo.BLOQUEADO or not repo.pasta_acessivel(base, 4): return False
        atual = ler(base) or _vazio(); agora = datetime.now().isoformat(timespec='seconds'); por = repo.nome_seguro(computador or socket.gethostname(), 30); mexeu = False
        for chave, nsu in (estados or {}).items():
            try: n = int(nsu)
            except (TypeError, ValueError): continue
            if n > 0 and n > int((atual['nsu'].get(chave) or {}).get('nsu') or 0):
                atual['nsu'][chave] = {'nsu': n, 'em': agora, 'por': por}; mexeu = True
        for cnpj, fams in (coberturas or {}).items():
            for fam, ate in (fams or {}).items():
                d = _data(ate)
                if d is None: continue
                velho = _data(((atual['cobertura'].get(cnpj) or {}).get(fam) or {}).get('ate'))
                if velho is None or d > velho:
                    atual['cobertura'].setdefault(cnpj, {})[fam] = {'ate': d.isoformat(), 'em': agora, 'por': por}; mexeu = True
        if not mexeu: return False
        atual['atualizado_em'] = agora
        destino = caminho(base); os.makedirs(repo._longo(destino.parent), exist_ok=True)
        tmp = destino.with_name(f'.busca.{por}.{os.getpid()}.tmp')
        with open(repo._longo(tmp), 'w', encoding='utf-8') as f:
            json.dump(atual, f, ensure_ascii=False); f.flush()
            try: os.fsync(f.fileno())
            except Exception: pass
        for tentativa in range(4):
            try:
                os.replace(repo._longo(tmp), repo._longo(destino)); return True
            except OSError:
                if tentativa == 3:
                    try: os.remove(repo._longo(tmp))
                    except OSError: pass
                    return False
                time.sleep(0.4 * (tentativa + 1))
    except Exception:
        return False
    return False


def nsu_compartilhado(dados, chave):
    try: return int(((dados or {}).get('nsu') or {}).get(chave, {}).get('nsu') or 0)
    except (TypeError, ValueError): return 0


def cobertura_compartilhada(dados, cnpj, familia):
    """Até que dia (date) algum computador já buscou aquele tipo da empresa; None se ninguém publicou."""
    return _data((((dados or {}).get('cobertura') or {}).get(re.sub(r'\D', '', str(cnpj or ''))) or {}).get(familia, {}).get('ate'))


def adotar(dados, estado_local, chave, folga=100):
    """Ponto de partida para `chave`: o MAIOR entre o local e o do servidor (menos a folga). Devolve (nsu, origem) com origem 'local' | 'servidor'.
    O do servidor só vale quando passa do local por mais que a folga (senão o local já está praticamente igual)."""
    local = int(estado_local or 0); comp = nsu_compartilhado(dados, chave)
    if comp - folga > local: return max(comp - folga, 0), 'servidor'
    return local, 'local'


# ------------------------------------------------------------------ trazer do Repositório para o banco deste computador
def _familia_da_pasta(nome_tipo):
    nome = str(nome_tipo or ''); evento = nome.startswith('Eventos ')
    return TIPO_FAMILIA.get(nome.replace('Eventos ', '', 1)), evento


def arquivos(base, cnpj_filtro=None, ignorar=()):
    """Percorre o Repositório e devolve (cnpj, família, é_evento, caminho) de cada XML (sem tocar nos arquivos)."""
    pasta_repo = repo._pasta_repo(base)
    try: empresas = sorted(os.listdir(repo._longo(pasta_repo)))
    except OSError: return
    for emp in empresas:
        cnpj = repo.cnpj_no_nome(emp)
        if emp.startswith('.') or not cnpj: continue
        if cnpj_filtro and re.sub(r'\D', '', str(cnpj_filtro)) != cnpj: continue
        if cnpj in ignorar: continue          # V182: empresa removida do cadastro não volta pelo servidor
        raiz = pasta_repo / emp
        for ano in repo._varrer_pasta(raiz)[1]:
            for mes in repo._varrer_pasta(raiz / ano)[1]:
                for tipo in repo._varrer_pasta(raiz / ano / mes)[1]:
                    familia, evento = _familia_da_pasta(tipo)
                    if not familia: continue
                    pilha = [raiz / ano / mes / tipo]
                    while pilha:
                        atual = pilha.pop(); arqs, subs = repo._varrer_pasta(atual); pilha.extend(atual / s for s in subs)
                        for nome in sorted(arqs):
                            if nome.lower().endswith('.xml') and not nome.startswith('.'): yield cnpj, familia, evento, atual / nome


def _chave_do_nome(nome):
    m = re.search(r'(\d{44,50})', nome)
    return m.group(1) if m else ''


def importar(base, conhecidos, gravar_lote, cnpj_filtro=None, cancelar=None, progresso=None, lote=100, ignorar=()):
    """Lê do Repositório só os XMLs que o banco deste computador ainda não tem e entrega, em lotes curtos, a `gravar_lote(cnpj, família, [xml bytes])`.
    `conhecidos(cnpj) -> set de chaves` (o banco deste computador). Eventos só entram junto das notas importadas agora. Devolve
    {'lidos','importados','ja_tinha','erros'}."""
    res = {'lidos': 0, 'importados': 0, 'ja_tinha': 0, 'erros': 0}; lotes = {}; sabidos = {}; trazidas = {}
    def descarregar(chave):
        itens = lotes.pop(chave, [])
        if not itens: return
        try: gravar_lote(chave[0], chave[1], itens)
        except Exception: res['erros'] += len(itens)
        else: res['importados'] += len(itens)
        if progresso:
            try: progresso(dict(res))
            except Exception: pass
    eventos = []
    for cnpj, familia, evento, arq in arquivos(base, cnpj_filtro, ignorar):
        if cancelar and cancelar(): break
        res['lidos'] += 1
        if evento: eventos.append((cnpj, familia, arq)); continue
        if cnpj not in sabidos: sabidos[cnpj] = set(conhecidos(cnpj) or ())
        chave = _chave_do_nome(arq.name)
        if chave and chave in sabidos[cnpj]: res['ja_tinha'] += 1; continue
        try: xml = repo._ler(arq)
        except OSError: res['erros'] += 1; continue
        if not xml: continue
        k = (cnpj, familia); lotes.setdefault(k, []).append(xml); trazidas.setdefault(cnpj, set()).add(chave)
        if len(lotes[k]) >= lote: descarregar(k)
    for k in list(lotes): descarregar(k)
    for cnpj, familia, arq in eventos:            # eventos das notas que vieram agora
        if cancelar and cancelar(): break
        if _chave_do_nome(arq.name) not in trazidas.get(cnpj, ()): continue
        try: xml = repo._ler(arq)
        except OSError: res['erros'] += 1; continue
        k = (cnpj, familia); lotes.setdefault(k, []).append(xml)
        if len(lotes[k]) >= lote: descarregar(k)
    for k in list(lotes): descarregar(k)
    return res
