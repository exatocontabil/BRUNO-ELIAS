"""Ponto único de acesso ao código do Exato (banco, situação da busca, relatórios...). Os núcleos fiscais protegidos não são tocados."""
import sys
from . import config

_mod = {}


def limpar_conta_modelo(m):
    """Apaga a conta-modelo do programa instalado (e-mail do autor, SEM senha nenhuma), se uma versão anterior do site a criou. Nunca apaga conta com senha."""
    try:
        c = m._auth_connect()
        try: c.execute("DELETE FROM users WHERE COALESCE(password_hash,'')='' AND lower(email)=lower(?)", (m.AUTH_BOOTSTRAP_EMAIL,)); c.commit()
        finally: c.close()
    except Exception: pass


def core():
    """Módulo `exato_central_fiscal` (sem abrir nenhuma janela). Importa uma única vez, depois de a pasta de dados estar definida."""
    if 'core' not in _mod:
        p = config.pasta_nucleo()
        for x in (p, p / 'third_party'):
            if str(x) not in sys.path: sys.path.insert(0, str(x))
        import exato_central_fiscal as m
        _mod['core'] = m
        m.db_auth_ensure_bootstrap_admin = lambda: None          # produto: o programa instalado cria sozinho uma conta-modelo com o e-mail do autor; o site NÃO a cria (o 1º administrador é criado na primeira abertura)
        m.init_database()
        limpar_conta_modelo(m)
    return _mod['core']


def modulo(nome):
    core(); return __import__(nome)
