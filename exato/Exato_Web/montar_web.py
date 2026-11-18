"""Monta o pacote do Exato Web para levar ao servidor: o site + uma cópia dos módulos do Exato (pasta `nucleo`) da versão mais nova do programa.

  python montar_web.py            ->  Exato_Web_AAAAMMDD.zip ao lado desta pasta
"""
import re, shutil, sys, zipfile
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SOBRAS = {'__pycache__', '.pytest_cache'}


def versao_mais_nova():
    cand = sorted(AQUI.parent.glob('Exato_Central_Fiscal_V*/programa'), key=lambda p: int(re.sub(r'\D', '', p.parent.name) or 0))
    if not cand: sys.exit('Não encontrei a pasta do programa (Exato_Central_Fiscal_Vxxx/programa).')
    return cand[-1]


def montar():
    nucleo = versao_mais_nova(); saida = AQUI.parent / f'Exato_Web_{date.today():%Y%m%d}{sys.argv[1] if len(sys.argv) > 1 else ""}.zip'
    with zipfile.ZipFile(saida, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, destino in ((AQUI / 'web', 'Exato_Web/web'), (AQUI / 'docs', 'Exato_Web/docs'), (nucleo, 'Exato_Web/nucleo')):
            for p in sorted(base.rglob('*')):
                if p.is_file() and not (set(p.parts) & SOBRAS) and p.suffix != '.pyc': z.write(p, f'{destino}/{p.relative_to(base).as_posix()}')
        for nome in ('README.md', 'requirements.txt', 'INICIAR_SERVIDOR.bat', 'INSTALAR_DEPENDENCIAS.bat', 'INSTALAR_INICIO_AUTOMATICO.bat', 'INSTALAR_INICIO_AUTOMATICO.ps1', 'PARAR_SITE.bat', 'LIGAR_SITE.bat', 'VER_REGISTRO_DO_SITE.bat', 'REMOVER_INICIO_AUTOMATICO.bat', 'INSTALAR_ENDERECO_COMERCIAL.bat', 'INSTALAR_ENDERECO_COMERCIAL.ps1', 'INSTALAR_CERTIFICADO_NESTE_PC.bat', 'INSTALAR_CERTIFICADO_NESTE_PC.ps1', 'MOVER_DADOS_PARA_OUTRO_DISCO.bat', 'MOVER_DADOS_PARA_OUTRO_DISCO.ps1'): z.write(AQUI / nome, f'Exato_Web/{nome}')
    print(f'Pacote: {saida} (núcleo: {nucleo.parent.name})'); return saida


if __name__ == '__main__': montar()
