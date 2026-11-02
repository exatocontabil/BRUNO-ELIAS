"""Espaço em disco e limpeza SEGURA dos arquivos do Exato Central Fiscal (V183). Sem Tkinter.

Regra do usuário: tudo que envolve limpeza é SÓ do Exato Central Fiscal; nunca se apaga outro tipo de arquivo. Por isso:
- só se entra em pastas DENTRO da pasta de dados do Exato (`raiz`), resolvidas e conferidas; atalho, link ou junção que aponte para fora nunca é seguido nem apagado;
- só existe uma LISTA BRANCA de alvos (nome/extensão do Exato): diagnóstico da busca, restos de backup, backups automáticos antigos e PDFs guardados (refazíveis);
- nunca se toca em XML, banco, usuários, configuração, `SAT_AUDITORIA`, pastas dos clientes, Repositório do servidor, nem em pastas de outros programas;
- apaga arquivo por arquivo (nunca `rmtree`) e só remove pastas que ficaram vazias.
"""
from __future__ import annotations
import os, re, shutil, time
from pathlib import Path

GB = 1024 ** 3; MB = 1024 ** 2
LIMITE_BAIXO = 2 * GB            # abaixo disto: aviso
LIMITE_BAIXO_PCT = 0.05          # ... ou abaixo de 5% do disco
LIMITE_CRITICO = 300 * MB        # abaixo disto: pausa busca, cópia e backup
DIAG_MANTER_EXECUCOES = 3
DIAG_MAX_BYTES = 300 * MB
DIAG_IDADE_DIAS = 7
BACKUPS_AUTOMATICOS_MANTER = 2
PDF_IDADE_DIAS = 60

_RE_BACKUP_TEMP = re.compile(r'^\.(central_fiscal|usuarios)_backup_.*\.db$')
_RE_BACKUP_AUTO = re.compile(r'^Exato_Backup_.*_(automatico|antes_da_atualizacao|antes_reparo_v145)\.zip$')          # os que o Exato cria sozinho; 'manual' e 'antes_restauracao' nunca entram


def _eh_link(p):
    """Atalho/link simbólico ou junção do Windows: nunca seguir nem apagar."""
    try:
        if os.path.islink(p): return True
        if hasattr(os.path, 'isjunction') and os.path.isjunction(p): return True
    except OSError:
        return True
    return False


def dentro_de(raiz, alvo):
    """True se `alvo` (já resolvido) está dentro de `raiz` (resolvida)."""
    try:
        Path(alvo).resolve().relative_to(Path(raiz).resolve()); return True
    except (ValueError, OSError):
        return False


def _arquivos(pasta, raiz, casar=None):
    """[(caminho, tamanho, mtime)] dos arquivos comuns sob `pasta`, sem seguir links e só dentro de `raiz`."""
    saida = []
    if not os.path.isdir(pasta) or _eh_link(pasta) or not dentro_de(raiz, pasta): return saida
    for atual, dirs, nomes in os.walk(pasta, followlinks=False):
        dirs[:] = [d for d in dirs if not _eh_link(os.path.join(atual, d)) and dentro_de(raiz, os.path.join(atual, d))]
        for n in nomes:
            p = os.path.join(atual, n)
            if _eh_link(p) or not dentro_de(raiz, p) or (casar and not casar(n)): continue
            try:
                st = os.stat(p); saida.append((p, st.st_size, st.st_mtime))
            except OSError:
                pass
    return saida


def _apagar(arquivos, raiz, erros=None, parar=None, ritmo=0.0):
    """Apaga só arquivos comuns que estão dentro de `raiz`. Devolve (quantos, bytes).
    V184: `parar()` interrompe na hora (ex.: começou uma busca) e `ritmo` faz uma pausa curta a cada 25 arquivos (não pesa o disco)."""
    n = b = 0
    for p, tam, _m in arquivos:
        if parar and parar(): break
        if _eh_link(p) or not dentro_de(raiz, p): continue
        try:
            os.unlink(p); n += 1; b += tam
            if ritmo and n % 25 == 0: time.sleep(ritmo)
        except OSError as exc:
            if erros is not None: erros.append(f'{os.path.basename(p)}: {exc}')
    return n, b


def _remover_pastas_vazias(pasta, raiz):
    """Remove (sem rmtree) as pastas vazias sob `pasta`, de baixo para cima; a própria `pasta` fica se for um alvo fixo."""
    if not os.path.isdir(pasta) or _eh_link(pasta) or not dentro_de(raiz, pasta): return
    for atual, dirs, _n in os.walk(pasta, topdown=False, followlinks=False):
        if _eh_link(atual) or not dentro_de(raiz, atual) or os.path.abspath(atual) == os.path.abspath(pasta): continue
        try: os.rmdir(atual)
        except OSError: pass


# ------------------------------------------------------------------ espaço
def espaco_livre(caminho):
    """(livre, total) em bytes do disco onde está `caminho`; (None, None) se não der para saber."""
    try:
        u = shutil.disk_usage(str(caminho)); return u.free, u.total
    except OSError:
        return None, None


def nivel_espaco(livre, total):
    """'ok' | 'baixo' (aviso) | 'critico' (pausar busca, cópia e backup) | 'desconhecido'."""
    if livre is None or not total: return 'desconhecido'
    if livre < LIMITE_CRITICO: return 'critico'
    if livre < LIMITE_BAIXO or livre / total < LIMITE_BAIXO_PCT: return 'baixo'
    return 'ok'


def texto_tamanho(b):
    b = float(b or 0)
    if b >= GB: return f'{b / GB:.1f} GB'.replace('.', ',')
    if b >= MB: return f'{b / MB:.0f} MB'
    return f'{b / 1024:.0f} KB'


def tamanho_pasta(pasta, raiz=None):
    return sum(t for _p, t, _m in _arquivos(pasta, raiz or pasta))


# ------------------------------------------------------------------ alvos (lista branca)
def _alvos(raiz):
    raiz = Path(raiz)
    diag = raiz / 'Trabalho' / 'DIAGNOSTICO_WEBSERVICE'; bk = raiz / 'Backups'; pdf = raiz / 'Representacoes_Fiscais'
    return {
        'diagnostico': {'titulo': 'Diagnóstico das buscas', 'pasta': diag, 'casar': None,
                        'explica': 'Cópia das respostas da SEFAZ guardada a cada busca, só para análise de problemas. Pode apagar: não faz falta no dia a dia.'},
        'backups_temp': {'titulo': 'Restos de backup que falhou', 'pasta': bk, 'casar': lambda n: bool(_RE_BACKUP_TEMP.match(n)),
                         'explica': 'Arquivos temporários de um backup que não terminou (disco cheio ou fechamento no meio). Podem ser apagados.'},
        'backups_antigos': {'titulo': 'Backups antigos feitos pelo Exato', 'pasta': bk, 'casar': lambda n: bool(_RE_BACKUP_AUTO.match(n)),
                            'explica': f'Cópias de segurança que o Exato faz sozinho (a cada versão nova etc.). Ficam os {BACKUPS_AUTOMATICOS_MANTER} mais novos; os mais antigos podem ser apagados (o servidor também guarda cópias). Backups feitos por você não são tocados.'},
        'pdfs': {'titulo': 'PDFs guardados (DANFE/DANFSe)', 'pasta': pdf, 'casar': lambda n: n.lower().endswith('.pdf'),
                 'explica': 'PDFs que o Exato gerou para abrir as notas. São refeitos quando você pedir de novo.'},
    }


def listar(raiz):
    """[{'id','titulo','explica','pasta','arquivos','bytes','apagavel_bytes','apagavel_arquivos'}] do que a limpeza pode apagar HOJE (só lista branca)."""
    saida = []; raiz = Path(raiz)
    for ident, a in _alvos(raiz).items():
        arqs = _arquivos(a['pasta'], raiz, a['casar'])
        apagar = _selecionar(ident, arqs)
        saida.append({'id': ident, 'titulo': a['titulo'], 'explica': a['explica'], 'pasta': str(a['pasta']), 'arquivos': len(arqs), 'bytes': sum(t for _p, t, _m in arqs),
                      'apagavel_arquivos': len(apagar), 'apagavel_bytes': sum(t for _p, t, _m in apagar)})
    return saida


def _selecionar(ident, arqs, agora=None):
    """Quais arquivos de cada alvo podem ir embora agora (o resto fica)."""
    agora = agora or time.time()
    if ident in ('diagnostico', 'backups_temp'): return list(arqs)
    if ident == 'backups_antigos':
        ordem = sorted(arqs, key=lambda x: x[2], reverse=True); return ordem[BACKUPS_AUTOMATICOS_MANTER:]
    if ident == 'pdfs': return list(arqs)
    return []


def limpar(raiz, ids, erros=None):
    """Apaga o que for da lista branca nos alvos pedidos. Devolve {'arquivos','bytes','por_alvo': {id: (n, bytes)}}. Nunca levanta erro."""
    raiz = Path(raiz); res = {'arquivos': 0, 'bytes': 0, 'por_alvo': {}}; alvos = _alvos(raiz)
    for ident in ids or []:
        a = alvos.get(ident)
        if not a: continue
        arqs = _arquivos(a['pasta'], raiz, a['casar']); n, b = _apagar(_selecionar(ident, arqs), raiz, erros)
        if ident in ('diagnostico', 'pdfs'): _remover_pastas_vazias(a['pasta'], raiz)
        res['por_alvo'][ident] = (n, b); res['arquivos'] += n; res['bytes'] += b
    return res


def limpar_automatico(raiz, agora=None, parar=None, ritmo=0.0):
    """Limpeza que o Exato faz sozinho (na abertura e de tempos em tempos), só na lista branca:
    - diagnóstico: execuções com mais de DIAG_IDADE_DIAS dias, o que passar das DIAG_MANTER_EXECUCOES mais novas e o que passar de DIAG_MAX_BYTES;
    - restos de backup; backups automáticos além dos mais novos; PDFs não refeitos há PDF_IDADE_DIAS dias.
    Devolve [(descrição, quantos, bytes)] do que apagou (para o exato.log)."""
    raiz = Path(raiz); agora = agora or time.time(); feitos = []; alvos = _alvos(raiz)
    # diagnóstico por execução (pasta = uma busca)
    pasta = alvos['diagnostico']['pasta']
    execs = []
    try:
        for d in os.scandir(pasta):
            if d.is_dir(follow_symlinks=False) and not _eh_link(d.path) and dentro_de(raiz, d.path):
                arqs = _arquivos(d.path, raiz)
                execs.append((d.path, sum(t for _p, t, _m in arqs), max([m for _p, _t, m in arqs] or [d.stat().st_mtime])))          # idade = do arquivo mais novo da execução
    except OSError:
        execs = []
    execs.sort(key=lambda x: x[2], reverse=True)
    soma = 0; apagar_exec = []
    for i, (caminho, tam, mtime) in enumerate(execs):
        soma += tam; velha = agora - mtime > DIAG_IDADE_DIAS * 86400
        if i >= DIAG_MANTER_EXECUCOES or velha or soma > DIAG_MAX_BYTES: apagar_exec.append(caminho)
    n = b = 0
    for caminho in apagar_exec:
        nn, bb = _apagar(_arquivos(caminho, raiz), raiz, None, parar, ritmo); n += nn; b += bb
        _remover_pastas_vazias(caminho, raiz)
        try: os.rmdir(caminho)
        except OSError: pass
    if n: feitos.append(('diagnóstico antigo das buscas', n, b))
    for ident in ('backups_temp', 'backups_antigos'):
        a = alvos[ident]; nn, bb = _apagar(_selecionar(ident, _arquivos(a['pasta'], raiz, a['casar'])), raiz, None, parar, ritmo)
        if nn: feitos.append((a['titulo'].lower(), nn, bb))
    a = alvos['pdfs']; velhos = [x for x in _arquivos(a['pasta'], raiz, a['casar']) if agora - x[2] > PDF_IDADE_DIAS * 86400]
    nn, bb = _apagar(velhos, raiz, None, parar, ritmo)
    if nn: feitos.append(('PDFs guardados antigos', nn, bb)); _remover_pastas_vazias(a['pasta'], raiz)
    return feitos


# ------------------------------------------------------------------ resumo de uso
def resumo_uso(raiz):
    """[(nome, bytes, nota)] do que o Exato ocupa em `raiz` (para a tela Espaço usado)."""
    raiz = Path(raiz); itens = []
    def tam(p): return tamanho_pasta(p, raiz) if os.path.isdir(p) else (os.path.getsize(p) if os.path.isfile(p) else 0)
    banco = sum(tam(raiz / n) for n in ('central_fiscal.db', 'central_fiscal.db-wal', 'central_fiscal.db-shm'))
    itens.append(('Banco de notas', banco, 'Não apague: guarda todas as notas e o cadastro.'))
    itens.append(('Trabalho (diagnóstico e auditorias)', tam(raiz / 'Trabalho'), 'O diagnóstico das buscas pode ser limpo; SAT_AUDITORIA fica.'))
    itens.append(('Backups locais', tam(raiz / 'Backups'), 'Ficam só os mais novos; os mais antigos podem ser limpos.'))
    itens.append(('PDFs guardados', tam(raiz / 'Representacoes_Fiscais'), 'Refeitos quando você pedir.'))
    itens.append(('Registro de erros', tam(raiz / 'Logs'), 'Pequeno; ajuda o suporte.'))
    return itens
