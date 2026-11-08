"""Ponto único de acesso ao código do Exato (banco, situação da busca, relatórios...). Os núcleos fiscais protegidos não são tocados."""
import sys
from . import config

_mod = {}


def core():
    """Módulo `exato_central_fiscal` (sem abrir nenhuma janela). Importa uma única vez, depois de a pasta de dados estar definida."""
    if 'core' not in _mod:
        p = config.pasta_nucleo()
        for x in (p, p / 'third_party'):
            if str(x) not in sys.path: sys.path.insert(0, str(x))
        import exato_central_fiscal as m
        _mod['core'] = m
        m.init_database()
    return _mod['core']


def modulo(nome):
    core(); return __import__(nome)
