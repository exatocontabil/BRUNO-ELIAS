"""Restaurar uma cópia de segurança pela tela.

Como é feito sem risco: a tela só registra um PEDIDO (`restaurar.json` na pasta de dados) e o Exato reinicia. Na abertura seguinte, ANTES de abrir qualquer arquivo de dados,
`aplicar_se_pedido` abre a cópia numa pasta de preparo, confere (arquivos e integridade dos bancos) e só então troca: o que existe hoje (empresas e notas, usuários, certificados,
auditorias) vai para uma pasta `_antes_da_restauracao_AAAAMMDD_HHMMSS` DENTRO da pasta de dados, e o conteúdo da cópia entra no lugar. Se algo falhar, nada muda.
Nunca apaga nada. O que se refaz sozinho (cópias de XML, ZIPs, PDFs, registros) não é tocado."""
import json, os, shutil, sqlite3, zipfile
from datetime import datetime
from pathlib import Path

from .backup import PREFIXO

PEDIDO = 'restaurar.json'; RESULTADO = 'restaurar_resultado.json'; PREPARO = '_restauracao_preparo'


class RestauracaoErro(Exception): pass


def _seguro(nome):
    p = Path(str(nome).replace('\\', '/'))
    return not p.is_absolute() and '..' not in p.parts and bool(p.parts) and ':' not in str(nome)


def conferir_zip(caminho):
    """Abre a cópia e confere: nome do backup, estrutura (tem o banco principal), caminhos seguros. Devolve (itens_de_topo, bytes_descompactados)."""
    caminho = Path(caminho)
    if not caminho.is_file() or not caminho.name.startswith(PREFIXO) or caminho.suffix.lower() != '.zip': raise RestauracaoErro('Esse arquivo não é uma cópia de segurança do Exato.')
    try: z = zipfile.ZipFile(caminho)
    except zipfile.BadZipFile: raise RestauracaoErro('O arquivo da cópia está danificado.')
    with z:
        nomes = [i for i in z.infolist() if not i.is_dir()]
        if any(not _seguro(i.filename) for i in nomes): raise RestauracaoErro('A cópia tem caminhos inválidos e não será usada.')
        topo = sorted({Path(i.filename.replace('\\', '/')).parts[0] for i in nomes if i.filename != 'LEIA-ME.txt'})
        if 'nucleo' not in topo: raise RestauracaoErro('Essa cópia não tem os dados do Exato (empresas e notas).')
        return topo, sum(i.file_size for i in nomes)


def pedir(dados, caminho_zip, por=''):
    """Registra o pedido (a troca acontece na próxima abertura do Exato). Levanta RestauracaoErro em português."""
    topo, tamanho = conferir_zip(caminho_zip)
    try: livre = shutil.disk_usage(str(dados)).free
    except OSError: livre = None
    if livre is not None and livre < tamanho * 1.15 + 200 * 1024 * 1024: raise RestauracaoErro(f'Não há espaço no disco dos dados para restaurar (livre {livre / 1024 ** 3:.1f} GB; precisa de cerca de {(tamanho * 1.15 + 200 * 1024 * 1024) / 1024 ** 3:.1f} GB).')
    Path(dados, PEDIDO).write_text(json.dumps({'zip': str(caminho_zip), 'pedido_em': datetime.now().isoformat(timespec='seconds'), 'por': por}, ensure_ascii=False), encoding='utf-8')


def pedido_pendente(dados):
    try: return json.loads(Path(dados, PEDIDO).read_text(encoding='utf-8'))
    except Exception: return None


def ultimo_resultado(dados):
    try: return json.loads(Path(dados, RESULTADO).read_text(encoding='utf-8'))
    except Exception: return None


def _verificar_bancos(pasta):
    for p in Path(pasta).rglob('*'):
        if p.is_file() and p.suffix.lower() in ('.db', '.sqlite', '.sqlite3'):
            con = sqlite3.connect(str(p))
            try:
                r = con.execute('PRAGMA quick_check').fetchone()
                if not r or r[0] != 'ok': raise RestauracaoErro(f'Um arquivo de dados da cópia ({p.name}) está com problema. A restauração foi cancelada e nada foi mudado.')
            except sqlite3.DatabaseError: raise RestauracaoErro(f'Um arquivo de dados da cópia ({p.name}) está danificado. A restauração foi cancelada e nada foi mudado.')
            finally: con.close()


def aplicar_se_pedido(dados, agora=None):
    """Chamada na abertura, antes de abrir os dados. Devolve o resultado (dict) ou None se não havia pedido. Nunca levanta erro."""
    dados = Path(dados); ped = pedido_pendente(dados)
    if not ped: return None
    agora = agora or datetime.now(); preparo = dados / PREPARO; aside = None; movidos = []; entrou = []
    def gravar(res):
        res['quando'] = agora.isoformat(timespec='seconds')
        try: (dados / RESULTADO).write_text(json.dumps(res, ensure_ascii=False), encoding='utf-8')
        except OSError: pass
        try: (dados / PEDIDO).unlink()
        except OSError: pass
        return res
    try:
        zip_ = Path(ped.get('zip') or ''); topo, _tam = conferir_zip(zip_)
        shutil.rmtree(preparo, ignore_errors=True); preparo.mkdir()
        with zipfile.ZipFile(zip_) as z:
            for i in z.infolist():
                if i.is_dir() or i.filename == 'LEIA-ME.txt': continue
                destino = preparo / Path(i.filename.replace('\\', '/')); destino.parent.mkdir(parents=True, exist_ok=True)
                with z.open(i) as src, open(destino, 'wb') as dst: shutil.copyfileobj(src, dst, 1024 * 1024)
        _verificar_bancos(preparo)
        aside = dados / ('_antes_da_restauracao_' + agora.strftime('%Y%m%d_%H%M%S')); aside.mkdir()
        for nome in topo:          # 1) o que existe hoje vai de lado (com os arquivos de apoio do SQLite)   2) a cópia entra no lugar
            for n in (nome, nome + '-wal', nome + '-shm', nome + '-journal'):
                atual = dados / n
                if atual.exists(): os.replace(atual, aside / n); movidos.append(n)
        for nome in topo: os.replace(preparo / nome, dados / nome); entrou.append(nome)
        shutil.rmtree(preparo, ignore_errors=True)
        return gravar({'ok': True, 'arquivo': zip_.name, 'guardado_em': aside.name, 'msg': f'Cópia {zip_.name} restaurada. Os dados de antes ficaram guardados em {aside.name} (dentro da pasta de dados).'})
    except Exception as exc:
        for nome in entrou:          # desfaz: tira o que entrou e devolve o que estava
            try:
                alvo = dados / nome
                if alvo.is_dir(): shutil.rmtree(alvo, ignore_errors=True)
                elif alvo.exists(): alvo.unlink()
            except OSError: pass
        for nome in movidos:
            try: os.replace(aside / nome, dados / nome)
            except OSError: pass
        shutil.rmtree(preparo, ignore_errors=True)
        try:
            if aside and not any(aside.iterdir()): aside.rmdir()
        except OSError: pass
        msg = str(exc) if isinstance(exc, RestauracaoErro) else 'A restauração não foi concluída por um problema inesperado. Nada foi mudado.'
        return gravar({'ok': False, 'arquivo': Path(ped.get('zip') or '').name, 'msg': msg})

