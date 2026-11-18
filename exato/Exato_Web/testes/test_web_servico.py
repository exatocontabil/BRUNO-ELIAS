"""Exato Web: ligar sem janela preta (web/servico.py) e os scripts do Windows no pacote."""
import os, sys, tempfile, zipfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]; os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_srv_'); sys.path.insert(0, str(RAIZ))
from web import servico
pasta = Path(tempfile.mkdtemp()) / 'logs'; velho = sys.stdout, sys.stderr
arq = servico.preparar_saida(pasta); print('linha de teste'); sys.stdout.flush(); saida = sys.stdout; sys.stdout, sys.stderr = velho; saida.close()
assert arq.exists() and 'linha de teste' in arq.read_text(encoding='utf-8')          # tudo que iria para a tela vai para o arquivo
arq.write_bytes(b'x' * (5 * 1024 * 1024 + 10)); sys.stdout, sys.stderr = velho; servico.preparar_saida(pasta); sys.stdout.close(); sys.stdout, sys.stderr = velho
assert (pasta / 'servidor_saida.log.1').exists() and arq.stat().st_size == 0          # arquivo grande vira .1 e começa outro
for nome in ('INSTALAR_INICIO_AUTOMATICO.bat', 'INSTALAR_INICIO_AUTOMATICO.ps1', 'PARAR_SITE.bat', 'LIGAR_SITE.bat', 'VER_REGISTRO_DO_SITE.bat', 'REMOVER_INICIO_AUTOMATICO.bat'):
    t = (RAIZ / nome).read_text(encoding='utf-8'); assert t.strip(), nome
ps = (RAIZ / 'INSTALAR_INICIO_AUTOMATICO.ps1').read_text(encoding='utf-8')
assert 'AtStartup' in ps and 'RestartCount' in ps and "'-m web.servico'" in ps and 'pythonw.exe' in ps and "StartsWith('\\\\')" in ps          # liga com o Windows, reinicia se cair, escondido, trata pasta de rede
sys.path.insert(0, str(RAIZ)); import montar_web
print('Exato Web (inicio automatico): OK')
