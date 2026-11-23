"""Exato Web: peças do instalador único que podem ser testadas fora do Windows (o teste de instalar e desinstalar de verdade roda no GitHub Actions)."""
import os, re, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'instalador' / 'arquivos')); sys.path.insert(0, str(RAIZ / 'instalador'))
import supervisor as sv
import montar_instalador as mi

# ---- supervisor: religa quando cai, para quando sai normal, espera mais se cair sempre logo
class Proc:
    def __init__(self, codigo): self.codigo = codigo
    def wait(self): return self.codigo
def rodar(codigos, tempos=None):
    fila = list(codigos); esperas = []; t = [0.0]; passos = list(tempos or [0.0] * (len(codigos) * 2 + 2))
    def agora(): t[0] += passos.pop(0) if passos else 0; return t[0]
    def abrir(): return Proc(fila.pop(0))
    r = sv.executar(['x'], '.', esperar=esperas.append, agora=agora, abrir=abrir); return r, esperas, fila
r, esp, resto = rodar([3, 1, 0]); assert r == 0 and esp == [3, 3] and resto == []          # reinício (3) e queda (1): religa em 3 s; saída normal para
r, esp, _ = rodar([0]); assert r == 0 and esp == []
r, esp, _ = rodar([1] * 7 + [0]); assert r == 0 and esp[:4] == [3, 3, 3, 3] and 30 in esp, esp          # caindo toda hora logo ao ligar: passa a esperar 30 s
# ---- pasta de dados: variável > dados.txt > padrão do usuário
d = Path(tempfile.mkdtemp()); (sv.RAIZ).mkdir(exist_ok=True)
os.environ.pop('EXATO_WEB_DADOS', None); original = sv.RAIZ
sv.RAIZ = d; (d / 'dados.txt').write_text('\ufeff"D:\\Dados do Exato"\r\nsobra', encoding='utf-8'); assert str(sv.pasta_dados()).replace('\\', '/').endswith('Dados do Exato') and 'D:' in str(sv.pasta_dados())
(d / 'dados.txt').unlink(); assert sv.pasta_dados() == Path.home() / 'ExatoWebDados'
os.environ['EXATO_WEB_DADOS'] = '/tmp/x'; assert sv.pasta_dados() == Path('/tmp/x'); os.environ.pop('EXATO_WEB_DADOS'); sv.RAIZ = original
assert sv.processo_vivo(os.getpid()) and not sv.processo_vivo(99999999) and not sv.processo_vivo('abc') and not sv.processo_vivo(-1) and not sv.site_responde(1)

# ---- pasta do instalador (sem Python): o que entra e o que não entra
stage = Path(tempfile.mkdtemp()) / 'app'; mi.preparar_app(stage, '20260101.7')
assert (stage / 'web' / 'app.py').exists() and (stage / 'nucleo' / 'exato_central_fiscal.py').exists() and (stage / 'requirements.txt').exists() and (stage / 'supervisor.py').exists()
assert all((stage / n).exists() for n in ('iniciar.pyw', 'abrir.pyw', 'parar.pyw')) and (stage / 'VERSAO.txt').read_text(encoding='utf-8').strip() == 'Exato Web 20260101.7'
assert not list(stage.glob('*.bat')) and not list(stage.glob('*.ps1')) and not list(stage.rglob('__pycache__')) and not (stage / 'dados.txt').exists()          # sem scripts de linha de comando; dados.txt é criado pela instalação
# ---- roteiro do instalador (Inno Setup)
iss = (RAIZ / 'instalador' / 'exato_web.iss').read_text(encoding='utf-8')
for trecho in ('PrivilegesRequired=lowest', 'BrazilianPortuguese.isl', 'CreateInputDirPage', 'dados.txt', 'parar.pyw', 'iniciar.pyw', 'abrir.pyw', 'uninsdeletevalue', 'PrepareToInstall', "DestDir: \"{app}\\python\"", 'GetSpaceOnDisk'): assert trecho in iss, trecho
visivel = '\n'.join(l for l in iss.splitlines() if re.match(r'\s*(WelcomeLabel|MsgBox|Description:|Name: "(iniciar|atalho)|    \'|\s+\'Esc|.*GroupDescription)', l) or 'MsgBox(' in l or 'CreateInputDirPage' in l)
assert not re.search(r'PowerShell|Python|\.bat|\bSMTP\b|pythonw|Caddy', re.sub(r'\{app\}\\[A-Za-z]+\\[A-Za-z.]+', '', visivel), re.I), visivel          # nada técnico nas telas do instalador
# ---- fluxo de montagem e teste no Windows
wf = (RAIZ.parent.parent / '.github' / 'workflows' / 'exato-web-instalador.yml').read_text(encoding='utf-8')
assert 'windows-latest' in wf and 'montar_instalador.py' in wf and 'testar_instalador.ps1' in wf and 'upload-artifact' in wf and 'workflow_dispatch' in wf
ps = (RAIZ / 'instalador' / 'testar_instalador.ps1').read_text(encoding='ascii'); assert '/VERYSILENT' in ps and '/DADOS=' in ps and 'configurar' in ps and 'unins' in ps and 'ficar' in ps
print('Exato Web (instalador): OK')
