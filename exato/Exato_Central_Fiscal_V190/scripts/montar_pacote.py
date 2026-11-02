"""Monta o ZIP que vai para o usuário: só o que ele precisa (INICIAR.bat, LEIA-ME.txt, VERSAO.txt, programa/, ferramentas/, ajuda/).

Testes, histórico, referências, prévias e documentação de desenvolvimento ficam só no repositório.
Uso: python scripts/montar_pacote.py [pasta de saída]
"""
import sys, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
INCLUIR = ('INICIAR.bat', 'LEIA-ME.txt', 'VERSAO.txt', 'programa', 'ferramentas', 'ajuda')


def montar(destino):
    destino = Path(destino); destino.mkdir(parents=True, exist_ok=True)
    zip_path = destino / f'{ROOT.name}.zip'
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for nome in INCLUIR:
            alvo = ROOT / nome
            arquivos = [alvo] if alvo.is_file() else sorted(p for p in alvo.rglob('*') if p.is_file())
            for p in arquivos:
                if '__pycache__' in p.parts or p.suffix == '.pyc':
                    continue
                z.write(p, f'{ROOT.name}/{p.relative_to(ROOT).as_posix()}')
    return zip_path


if __name__ == '__main__':
    print(montar(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent))
