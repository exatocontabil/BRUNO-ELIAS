"""Cópia de segurança diária do Exato Web.

Uma cópia = um ZIP `ExatoWeb_backup_AAAAMMDD_HHMMSS.zip` na pasta de destino (outro disco, HD externo ou pasta de rede/NAS: é só um arquivo, não um banco em uso).
Entra: o banco (empresas, XMLs, usuários, histórico) e `web.db` por cópia CONSISTENTE do SQLite (funciona com o site ligado), o cofre de certificados, as auditorias e a
configuração. NÃO entra o que se refaz: cópias de XML (`Arquivos`), ZIPs (`exportacoes`), PDFs de relatórios (`relatorios`) e registros (`logs`).
Segurança: o ZIP só aparece com o nome final depois de conferido; as cópias antigas só são apagadas DEPOIS de uma nova boa; só apaga arquivos com o nome deste backup,
dentro da pasta de destino (nunca outra coisa); o destino não pode ficar dentro da pasta de dados. O cofre só abre no mesmo computador e usuário do Windows: guarde também os .pfx originais."""
import os, shutil, sqlite3, string, sys, tempfile, threading, zipfile
from datetime import datetime, timedelta
from pathlib import Path

from . import config

PREFIXO = 'ExatoWeb_backup_'
EXCLUIR = {'arquivos', 'exportacoes', 'relatorios', 'logs', '__pycache__'}          # pastas (no 1º nível dos dados) que se refazem sozinhas
MARGEM_BYTES = 200 * 1024 * 1024
_trava = threading.Lock()
andamento = {'rodando': False, 'etapa': '', 'inicio': None}


class BackupErro(Exception): pass


def cfg_de(cfg):
    c = cfg.setdefault('backup', {})
    for k, v in (('ativo', False), ('destino', ''), ('hora', '02:00'), ('manter', 7), ('ultimo', ''), ('ultimo_ok', ''), ('ultimo_estado', ''), ('ultimo_msg', ''), ('ultimo_tamanho', 0), ('ultimo_arquivo', '')): c.setdefault(k, v)
    return c


def _dentro(pasta, base):
    try: Path(pasta).resolve().relative_to(Path(base).resolve()); return True
    except Exception: return False


def validar_destino(destino, dados=None):
    """Devolve (pasta_resolvida, aviso). Levanta BackupErro (em português) se não serve."""
    dados = Path(dados or config.DADOS); texto = str(destino or '').strip().strip('"')
    if not texto: raise BackupErro('Informe a pasta onde as cópias serão guardadas (por exemplo E:\\CopiaExato).')
    p = Path(texto)
    if not p.is_absolute(): raise BackupErro('Use o caminho completo da pasta (por exemplo E:\\CopiaExato ou \\\\SERVIDOR\\Copias).')
    if _dentro(p, dados): raise BackupErro('A pasta das cópias não pode ficar dentro da pasta onde o Exato guarda os dados. Escolha outro disco ou outra pasta.')
    try: p.mkdir(parents=True, exist_ok=True)
    except OSError: raise BackupErro('Não consegui abrir essa pasta. Confira se o disco ou a pasta de rede está ligado e se você tem permissão de gravar.')
    try:
        t = p / '.teste_exato_backup'; t.write_text('ok'); t.unlink()
    except OSError: raise BackupErro('Não consigo gravar nessa pasta. Confira a permissão ou escolha outra.')
    aviso = ''
    try:
        if os.path.splitdrive(str(p.resolve()))[0].upper() == os.path.splitdrive(str(dados.resolve()))[0].upper() and os.path.splitdrive(str(p.resolve()))[0]:
            aviso = 'Esta pasta está no MESMO disco dos dados do site. Se o disco estragar, perde-se tudo junto. Prefira outro disco, um HD externo ou o NAS.'
    except Exception: pass
    return p, aviso


def arquivos_a_copiar(dados, destino=None):
    """[(caminho, nome_no_zip)] do que entra no backup (sem pastas que se refazem, sem arquivos temporários do SQLite e sem o próprio destino)."""
    dados = Path(dados); saida = []
    for raiz, pastas, nomes in os.walk(dados):
        rel = Path(raiz).relative_to(dados)
        pastas[:] = [d for d in pastas if not (rel == Path('.') and d.lower() in EXCLUIR) and not (destino and _dentro(Path(raiz) / d, destino))]
        for n in nomes:
            if n.lower().endswith(('-wal', '-shm', '-journal', '.tmp', '.pid', '.parcial')) or n == '.teste_exato_backup': continue
            saida.append((Path(raiz) / n, (rel / n).as_posix()))
    return saida


def _eh_sqlite(p): return p.suffix.lower() in ('.db', '.sqlite', '.sqlite3')


def _copia_sqlite(origem, destino):
    """Cópia consistente (API de backup do SQLite) e conferida; funciona com o banco em uso."""
    src = sqlite3.connect(f'file:{origem}?mode=ro', uri=True, timeout=60); dst = sqlite3.connect(str(destino))
    try:
        src.backup(dst); r = dst.execute('PRAGMA quick_check').fetchone()
        if not r or r[0] != 'ok': raise BackupErro(f'Um arquivo de dados do Exato ({Path(origem).name}) está com problema ({(r or ["?"])[0]}). A cópia foi cancelada para não guardar um arquivo de dados estragado.')
    finally:
        dst.close(); src.close()


def listar(destino):
    """Cópias que existem na pasta de destino (mais novas primeiro): [{nome, tamanho, quando}]."""
    out = []
    try:
        for p in Path(destino).glob(PREFIXO + '*.zip'):
            st = p.stat(); out.append({'nome': p.name, 'tamanho': st.st_size, 'quando': datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')})
    except OSError: return []
    return sorted(out, key=lambda x: x['nome'], reverse=True)


def _limpar_antigas(destino, manter):
    """Só depois de uma cópia nova boa: apaga as mais antigas deste backup além de `manter` (mínimo 2). Nunca toca em outro arquivo."""
    manter = max(2, int(manter or 7)); apagadas = []
    for item in listar(destino)[manter:]:
        try: (Path(destino) / item['nome']).unlink(); apagadas.append(item['nome'])
        except OSError: pass
    return apagadas


def mensagem_erro(exc):
    if isinstance(exc, BackupErro): return str(exc)
    if isinstance(exc, OSError) and getattr(exc, 'errno', None) == 28: return 'O disco de destino ficou sem espaço. Libere espaço ou escolha outro destino.'
    if isinstance(exc, PermissionError): return 'Sem permissão para gravar na pasta de destino.'
    if isinstance(exc, (FileNotFoundError, OSError)): return 'A pasta de destino não está acessível (disco desligado ou pasta de rede fora do ar?).'
    return 'A cópia não foi concluída por um problema inesperado. O detalhe foi guardado no registro.'


def executar(cfg, salvar, dados=None, agora=None, log_erro=None):
    """Faz uma cópia agora. Devolve {'ok','arquivo','tamanho','msg'}. Nunca levanta erro; o resultado fica em cfg['backup'] (e `salvar()` grava)."""
    c = cfg_de(cfg); dados = Path(dados or config.DADOS); agora = agora or datetime.now()
    if not _trava.acquire(blocking=False): return {'ok': False, 'msg': 'Já existe uma cópia em andamento.'}
    andamento.update(rodando=True, etapa='Preparando', inicio=agora.isoformat(timespec='seconds'))
    parcial = None; tmp = None
    try:
        destino, _aviso = validar_destino(c.get('destino'), dados)
        itens = arquivos_a_copiar(dados, destino); total = sum(p.stat().st_size for p, _ in itens if p.exists())
        livre = shutil.disk_usage(str(destino)).free
        if livre < total * 1.1 + MARGEM_BYTES: raise BackupErro(f'O destino não tem espaço suficiente (livre {livre / 1024 ** 3:.1f} GB; precisa de cerca de {(total * 1.1 + MARGEM_BYTES) / 1024 ** 3:.1f} GB).')
        nome = f"{PREFIXO}{agora.strftime('%Y%m%d_%H%M%S')}.zip"
        while (destino / nome).exists(): agora += timedelta(seconds=1); nome = f"{PREFIXO}{agora.strftime('%Y%m%d_%H%M%S')}.zip"
        parcial = destino / (nome + '.parcial'); tmp = Path(tempfile.mkdtemp(prefix='.tmp_backup_', dir=str(destino)))          # temporários no DESTINO, não no C:
        with zipfile.ZipFile(parcial, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
            for i, (p, rel) in enumerate(itens, 1):
                andamento['etapa'] = f'Copiando {i} de {len(itens)}'
                if not p.exists(): continue
                if _eh_sqlite(p): copia = tmp / f'{i}.db'; _copia_sqlite(p, copia); z.write(copia, rel); copia.unlink()
                else: z.write(p, rel)
            z.writestr('LEIA-ME.txt', 'Cópia de segurança do Exato Web feita em ' + agora.strftime('%d/%m/%Y %H:%M') + '.\r\nPara restaurar abra o Exato, entre em Cópia de segurança e clique em Restaurar (ou, se o Exato não abrir, use o programa \"Restaurar cópia de segurança\").\r\n'
                       'Os certificados guardados só abrem neste computador e com este usuário do Windows: guarde também os arquivos originais dos certificados.\r\n')
        andamento['etapa'] = 'Conferindo a cópia'
        with zipfile.ZipFile(parcial) as z:
            ruim = z.testzip()
            if ruim: raise BackupErro(f'A conferência da cópia falhou no arquivo {ruim}. Nada foi apagado.')
        final = destino / nome; os.replace(parcial, final); parcial = None
        apagadas = _limpar_antigas(destino, c.get('manter'))
        c.update(ultimo=agora.isoformat(timespec='seconds'), ultimo_ok=agora.isoformat(timespec='seconds'), ultimo_estado='ok', ultimo_arquivo=nome, ultimo_tamanho=final.stat().st_size,
                 ultimo_msg=f'Cópia feita ({final.stat().st_size / 1024 ** 2:.0f} MB).' + (f' {len(apagadas)} cópia(s) antiga(s) removida(s).' if apagadas else ''))
        res = {'ok': True, 'arquivo': nome, 'tamanho': final.stat().st_size, 'msg': c['ultimo_msg']}
    except Exception as exc:
        if not isinstance(exc, BackupErro) and log_erro:
            try: log_erro('Web: cópia de segurança', exc)
            except Exception: pass
        msg = mensagem_erro(exc)
        c.update(ultimo=agora.isoformat(timespec='seconds'), ultimo_estado='erro', ultimo_msg=msg); res = {'ok': False, 'msg': msg}
    finally:
        for caminho in (parcial,):
            try:
                if caminho and Path(caminho).exists(): Path(caminho).unlink()
            except OSError: pass
        if tmp:
            for f in Path(tmp).glob('*'):
                try: f.unlink()
                except OSError: pass
            try: Path(tmp).rmdir()
            except OSError: pass
        andamento.update(rodando=False, etapa='')
        _trava.release()
        try: salvar()
        except Exception: pass
    return res


def devida(cfg, agora=None):
    """True se está ligado, já passou da hora de hoje e ainda não foi feita hoje (se falhou, tenta de novo depois de 1 hora)."""
    c = cfg_de(cfg); agora = agora or datetime.now()
    if not c.get('ativo') or not str(c.get('destino') or '').strip() or andamento['rodando']: return False
    try: h, m = [int(x) for x in str(c.get('hora') or '02:00').split(':')[:2]]
    except Exception: h, m = 2, 0
    if agora < agora.replace(hour=h, minute=m, second=0, microsecond=0): return False
    try: ultimo_ok = datetime.fromisoformat(c.get('ultimo_ok')) if c.get('ultimo_ok') else None
    except Exception: ultimo_ok = None
    if ultimo_ok and ultimo_ok.date() == agora.date(): return False
    try: tentativa = datetime.fromisoformat(c.get('ultimo')) if c.get('ultimo') else None
    except Exception: tentativa = None
    if tentativa and tentativa.date() == agora.date() and c.get('ultimo_estado') == 'erro' and agora - tentativa < timedelta(hours=1): return False
    return True


def aviso(cfg, agora=None):
    """Texto curto para a tela de Situação (ou ''): backup não configurado ou parado há mais de 2 dias."""
    c = cfg_de(cfg); agora = agora or datetime.now()
    if not c.get('ativo') or not str(c.get('destino') or '').strip(): return 'A cópia de segurança diária ainda não está ligada. Configure em Cópia de segurança.'
    try: ok = datetime.fromisoformat(c['ultimo_ok']) if c.get('ultimo_ok') else None
    except Exception: ok = None
    if ok is None or agora - ok > timedelta(days=2): return 'A última cópia de segurança bem-sucedida foi há mais de 2 dias' + ('' if ok else ' (ou nunca foi feita)') + '. ' + (c.get('ultimo_msg') or 'Veja em Cópia de segurança.')
    return ''


def _discos():
    """Letras de disco que existem (Windows: sem consultar discos de rede desligados, que travariam). Fora do Windows (testes): '/'."""
    if sys.platform != 'win32': return ['/']
    try:
        import ctypes
        mascara = ctypes.windll.kernel32.GetLogicalDrives()
        return [f'{l}:\\' for i, l in enumerate(string.ascii_uppercase) if mascara & (1 << i) and l not in 'AB']
    except Exception: return ['C:\\']


def listar_pastas(caminho='', zips=False):
    """Para o botão "Procurar": as PASTAS (nunca arquivos) de um caminho do servidor. Sem caminho: os discos. Devolve {caminho, pai, pastas:[{nome, caminho}]}."""
    texto = str(caminho or '').strip().strip('"')
    if not texto: return {'caminho': '', 'pai': None, 'pastas': [{'nome': d, 'caminho': d} for d in _discos()]}
    p = Path(texto)
    if not p.is_absolute(): raise BackupErro('Use o caminho completo da pasta.')
    if not p.is_dir(): raise BackupErro('Essa pasta não existe ou não está acessível.')
    pastas = []
    try:
        for e in os.scandir(p):
            try:
                if e.is_dir(follow_symlinks=False) and not e.name.startswith('$') and e.name != 'System Volume Information': pastas.append({'nome': e.name, 'caminho': str(Path(e.path))})
            except OSError: continue
    except OSError: raise BackupErro('Não consegui ler essa pasta (sem permissão?).')
    pastas.sort(key=lambda x: x['nome'].lower())
    pai = str(p.parent) if p.parent != p else ''
    saida = {'caminho': str(p), 'pai': pai, 'pastas': pastas[:500], 'cortado': len(pastas) > 500}
    if zips:          # tela Importar: também mostra os arquivos .zip (cópias do programa instalado)
        arq = []
        try:
            for e in os.scandir(p):
                if e.is_file() and e.name.lower().endswith('.zip'): arq.append({'nome': e.name, 'caminho': str(Path(e.path)), 'mb': round(e.stat().st_size / 1048576)})
        except OSError: pass
        saida['arquivos'] = sorted(arq, key=lambda x: x['nome'].lower())[:200]
    return saida
