"""Exato Web: o importador do Windows nunca retira um certificado que já estava instalado no usuário (regressão: sumia do CERTMGR.MSC)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web import cofre

class Falso(cofre.ImportadorWindows):
    def __init__(self, saida): super().__init__(); self.saida = saida; self.removidos = []
    def _ps(self, script, env_extra, timeout=60):
        if script is cofre._PS_REMOVER: self.removidos.append(env_extra['EXATO_THUMB']); return 0, '', ''
        return 0, self.saida, ''

# já estava instalado: usa e NÃO remove
im = Falso('abc123\nJA_INSTALADO'); t = im.importar(b'x', 's'); assert t == 'ABC123'; im.remover(t); assert im.removidos == [], im.removidos
# o site é que instalou: remove ao terminar
im = Falso('abc123'); t = im.importar(b'x', 's'); im.remover(t); assert im.removidos == ['ABC123'], im.removidos
# estava instalado numa vez e depois não (a pessoa tirou): volta a valer a regra normal
im = Falso('abc123\nJA_INSTALADO'); im.importar(b'x', 's'); im.saida = 'abc123'; t = im.importar(b'x', 's'); im.remover(t); assert im.removidos == ['ABC123']
# o script confere a existência antes de adicionar e só persiste a chave quando vai adicionar
assert 'JA_INSTALADO' in cofre._PS_IMPORTAR and 'EphemeralKeySet' in cofre._PS_IMPORTAR and cofre._PS_IMPORTAR.index('JA_INSTALADO') < cofre._PS_IMPORTAR.index('PersistKeySet')
print('Exato Web (cofre no Windows): OK')
