"""Monta o instalador único do Exato Web (Exato_Web_Instalador_<versão>.exe) no Windows.

O instalador leva: o site, os módulos do Exato e um Python PRÓPRIO (copiado do Python 3.12 completo que está instalado na máquina que monta, já com as dependências
do site e o Tk que o Exato usa). Quem instala não precisa de Python nem de mais nada. Roda na máquina de montagem (GitHub Actions, no Windows):

    python -m pip install -r requirements.txt
    python instalador/montar_instalador.py            ->  dist/Exato_Web_Instalador_<versão>.exe

Opções: --sem-python (monta só a pasta do site, para testar fora do Windows) e --sem-compilar (para antes do Inno Setup)."""
import argparse, os, shutil, subprocess, sys, tempfile
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent; RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))
import montar_web

IGNORAR_DA_RAIZ_DO_PYTHON = {'Doc', 'Tools', 'include', 'libs', 'Scripts', 'share', 'NEWS.txt'}
IGNORAR_EM_LIB = {'test', 'idlelib', 'turtledemo', 'lib2to3'}


def versao():
    return os.environ.get('EXATO_VERSAO') or f'{date.today():%Y%m%d}'


def _ignorar_pycache(_dir, nomes): return {n for n in nomes if n == '__pycache__' or n.endswith('.pyc')}


def preparar_app(destino, v=None):
    """Pasta `app` do instalador: o site (web), os módulos do Exato (nucleo), a lista de peças e os programinhas de ligar/parar. Sem os .bat/.ps1 de linha de comando."""
    destino = Path(destino); v = v or versao()
    if destino.exists(): shutil.rmtree(destino)
    destino.mkdir(parents=True)
    shutil.copytree(RAIZ / 'web', destino / 'web', ignore=_ignorar_pycache)
    shutil.copytree(montar_web.versao_mais_nova(), destino / 'nucleo', ignore=_ignorar_pycache)
    shutil.copy2(RAIZ / 'requirements.txt', destino / 'requirements.txt')
    for p in (AQUI / 'arquivos').iterdir():
        if p.is_file(): shutil.copy2(p, destino / p.name)
    (destino / 'VERSAO.txt').write_text(f'Exato Web {v}\r\n', encoding='utf-8')
    return destino


def copiar_python(destino):
    """Copia o Python completo da máquina de montagem (com Tk e as dependências do site) para dentro do instalador."""
    base = Path(sys.base_prefix); destino = Path(destino)
    if destino.exists(): shutil.rmtree(destino)
    def ignorar(dir_, nomes):
        out = _ignorar_pycache(dir_, nomes); rel = Path(dir_).resolve().relative_to(base.resolve())
        if rel == Path('.'): out |= IGNORAR_DA_RAIZ_DO_PYTHON & set(nomes)
        if rel == Path('Lib'): out |= IGNORAR_EM_LIB & set(nomes)
        return out
    shutil.copytree(base, destino, ignore=ignorar)
    for exe in ('python.exe', 'pythonw.exe'):
        if not (destino / exe).exists(): raise SystemExit(f'O Python copiado não tem {exe}. Monte numa máquina Windows com o Python 3.12 completo instalado.')
    return destino


def conferir_python(py, app):
    """Roda o Python copiado: ele precisa abrir o site e o Tk. Falha cedo, antes de gerar o instalador."""
    env = dict(os.environ, EXATO_WEB_DADOS=tempfile.mkdtemp(prefix='exato_conf_'), EXATO_WEB_HTTPS='0')
    r = subprocess.run([str(py / 'python.exe'), '-c', 'import tkinter, fastapi, uvicorn, jinja2, multipart, cryptography, httpx, reportlab, PIL, segno; import web.app; print("ok")'], cwd=str(app), env=env, capture_output=True, text=True)
    if r.returncode != 0 or 'ok' not in r.stdout: raise SystemExit('O Python copiado não consegue abrir o Exato:\n' + (r.stderr or r.stdout)[-1500:])


def gerar_icone(destino):
    from PIL import Image
    png = Image.open(RAIZ / 'web' / 'static' / 'logo.png').convert('RGBA'); lado = max(png.size)
    tela = Image.new('RGBA', (lado, lado), (0, 0, 0, 0)); tela.paste(png, ((lado - png.width) // 2, (lado - png.height) // 2))
    tela.save(destino, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def achar_iscc():
    for c in (os.environ.get('ISCC'), r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe', r'C:\Program Files\Inno Setup 6\ISCC.exe'):
        if c and Path(c).exists(): return c
    return shutil.which('ISCC') or shutil.which('iscc')


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--sem-python', action='store_true'); ap.add_argument('--sem-compilar', action='store_true'); ap.add_argument('--saida', default=str(RAIZ / 'dist')); ap.add_argument('--stage', default=str(RAIZ / 'stage'))
    a = ap.parse_args(argv); v = versao(); stage = Path(a.stage)
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir(parents=True); app = preparar_app(stage / 'app', v); gerar_icone(stage / 'exato.ico')
    if not a.sem_python:
        py = copiar_python(stage / 'python'); conferir_python(py, app)
    if a.sem_compilar: print('Pasta preparada em', stage); return 0
    iscc = achar_iscc()
    if not iscc: raise SystemExit('Inno Setup não encontrado (instale com "choco install innosetup" ou defina ISCC).')
    Path(a.saida).mkdir(parents=True, exist_ok=True)
    r = subprocess.run([iscc, f'/DVersao={v}', f'/DOrigem={stage}', f'/DSaida={a.saida}', str(AQUI / 'exato_web.iss')])
    if r.returncode != 0: raise SystemExit('O Inno Setup não conseguiu montar o instalador.')
    exes = sorted(Path(a.saida).glob('Exato_Web_Instalador_*.exe')); print('Instalador:', exes[-1] if exes else '(não encontrado)'); return 0


if __name__ == '__main__': sys.exit(main())
