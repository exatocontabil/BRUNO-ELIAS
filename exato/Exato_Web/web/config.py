"""Configuração do Exato Web (servidor). Tudo que muda de um servidor para outro vem de variáveis de ambiente.

EXATO_WEB_DADOS      pasta dos dados do site (banco, usuários, cofre dos certificados, registros). Padrão: <usuário>/ExatoWebDados
EXATO_WEB_HTTPS      "1" (padrão em produção) = cookies só por HTTPS; "0" só para teste no próprio servidor
EXATO_WEB_EXIGIR_2FA "1" (padrão) = todo usuário precisa do código do aplicativo autenticador para entrar
EXATO_CORE_DIR       pasta com os módulos do Exato (padrão: a pasta `nucleo` do pacote; no desenvolvimento, a versão mais nova do programa)
"""
import os, re, secrets, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DADOS = Path(os.environ.get('EXATO_WEB_DADOS') or (Path.home() / 'ExatoWebDados'))
DADOS.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('EXATO_DATA_DIR', str(DADOS / 'nucleo'))          # o código do Exato guarda o banco aqui (antes de importá-lo)
HTTPS = os.environ.get('EXATO_WEB_HTTPS', '1') != '0'
EXIGIR_2FA = os.environ.get('EXATO_WEB_EXIGIR_2FA', '1') != '0'
SESSAO_HORAS = 10
TENTATIVAS_LOGIN = 5
BLOQUEIO_MINUTOS = 15


def pasta_nucleo():
    """Onde estão os módulos do Exato (exato_central_fiscal.py etc.)."""
    cand = []
    if os.environ.get('EXATO_CORE_DIR'): cand.append(Path(os.environ['EXATO_CORE_DIR']))
    cand.append(RAIZ / 'nucleo')
    versoes = sorted((RAIZ.parent).glob('Exato_Central_Fiscal_V*/programa'), key=lambda p: int(re.sub(r'\D', '', p.parent.name) or 0))
    cand += list(reversed(versoes))
    for p in cand:
        if (p / 'exato_central_fiscal.py').exists(): return p
    raise RuntimeError('Não encontrei os módulos do Exato. Defina EXATO_CORE_DIR.')


def chave_sessao():
    """Chave que assina os cookies de sessão; criada uma vez e guardada na pasta de dados (só o servidor lê)."""
    arq = DADOS / 'segredo_sessao.key'
    if not arq.exists():
        arq.write_bytes(secrets.token_bytes(32))
        try: os.chmod(arq, 0o600)
        except Exception: pass
    return arq.read_bytes()
