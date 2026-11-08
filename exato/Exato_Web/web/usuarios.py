"""Administração de usuários pelo servidor (linha de comando). O site em si não cria usuários: quem tem acesso ao servidor decide quem entra.

  python -m web.usuarios criar --email pessoa@escritorio.com.br --nome "Nome" [--admin]
  python -m web.usuarios senha --email pessoa@escritorio.com.br
  python -m web.usuarios zerar-2fa --email pessoa@escritorio.com.br     (se perder o celular)
  python -m web.usuarios listar
"""
import argparse, getpass, sys

from . import config, nucleo, seguranca
from .cofre import carregar_chave_mestra


def _senha():
    a = getpass.getpass('Senha (mínimo 10 caracteres): '); b = getpass.getpass('Repita a senha: ')
    if a != b: sys.exit('As senhas não conferem.')
    if len(a) < 10: sys.exit('Use pelo menos 10 caracteres.')
    return a


def main(argv=None):
    ap = argparse.ArgumentParser(prog='web.usuarios'); sp = ap.add_subparsers(dest='cmd', required=True)
    for n in ('criar', 'senha', 'zerar-2fa'):
        x = sp.add_parser(n); x.add_argument('--email', required=True)
        if n == 'criar': x.add_argument('--nome', required=True); x.add_argument('--admin', action='store_true')
    sp.add_parser('listar')
    a = ap.parse_args(argv); core = nucleo.core()
    if a.cmd == 'listar':
        for u in core.db_auth_list_users(): print(f"{u['email']:40} {u['name']:28} {u['role_label']:14} {u['status_label']}")
        return
    if a.cmd == 'criar':
        u = core.db_auth_register_user(a.nome, a.email, _senha())
        if a.admin:
            c = core._auth_connect(); c.execute("UPDATE users SET role='admin' WHERE id=?", (u['id'],)); c.commit(); c.close()
        print('Usuário criado. No primeiro acesso ele ativa a verificação em duas etapas.')
    elif a.cmd == 'senha':
        u = core.db_auth_get_user(a.email)
        if not u: sys.exit('Usuário não encontrado.')
        core.db_auth_set_password(u['id'], _senha()); print('Senha trocada.')
    elif a.cmd == 'zerar-2fa':
        u = core.db_auth_get_user(a.email)
        if not u: sys.exit('Usuário não encontrado.')
        seguranca.Totp(config.DADOS / 'web.db', carregar_chave_mestra(config.DADOS / 'cofre')).desativar(u['id']); print('Verificação zerada: no próximo acesso ele cadastra de novo.')


if __name__ == '__main__': main()
