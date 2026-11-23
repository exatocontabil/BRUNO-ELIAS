"""Contas de usuário do Exato Web: criar pessoas, senha provisória, perfil, bloqueio, código do celular. Tudo pela tela Usuários (nada de comandos).

Usa as funções de usuário do programa (`core.db_auth_*`); aqui ficam só as regras do site: senha provisória (a pessoa é obrigada a trocar no primeiro acesso),
mínimo de 10 caracteres, nunca ficar sem administrador."""
import secrets

MIN_SENHA = 10
_MIN = 'abcdefghjkmnpqrstuvwxyz'; _MAI = 'ABCDEFGHJKLMNPQRSTUVWXYZ'; _NUM = '23456789'          # sem letras que se confundem (l, I, O, 0, 1)
PERFIS = {'admin': 'Administrador', 'user': 'Usuário'}


def senha_provisoria(tamanho=12):
    while True:
        s = ''.join(secrets.choice(_MIN + _MAI + _NUM) for _ in range(tamanho))
        if any(c in _MIN for c in s) and any(c in _MAI for c in s) and any(c in _NUM for c in s): return s


def validar_senha_nova(nova, atual='', email=''):
    """Levanta ValueError (em português) se a senha escolhida não serve."""
    nova = str(nova or '')
    if len(nova) < MIN_SENHA: raise ValueError(f'Use pelo menos {MIN_SENHA} caracteres.')
    if nova.isdigit() or nova.isalpha(): raise ValueError('Misture letras e números na senha.')
    if atual and nova == atual: raise ValueError('A nova senha precisa ser diferente da atual.')
    if email and nova.lower() == str(email).strip().lower(): raise ValueError('A senha não pode ser o seu e-mail.')


def _sql(core, sql, args=()):
    c = core._auth_connect()
    try: c.execute(sql, args); c.commit()
    finally: c.close()


def marcar_trocar_senha(core, uid, valor=True): _sql(core, 'UPDATE users SET must_set_password=? WHERE id=?', (1 if valor else 0, int(uid)))


def sem_senha(core):
    """Ids de contas sem senha nenhuma (a conta-modelo que o programa instalado cria sozinha): nunca aparecem na tela e não contam como administrador."""
    c = core._auth_connect()
    try: return {int(r[0]) for r in c.execute("SELECT id FROM users WHERE COALESCE(password_hash,'')=''").fetchall()}
    finally: c.close()


def admins_ativos(core):
    fantasmas = sem_senha(core)
    return [u for u in core.db_auth_list_users() if u.get('role') == 'admin' and u.get('status') == 'active' and int(u['id']) not in fantasmas]


def criar_usuario(core, nome, email, perfil='user'):
    """Cria a pessoa com senha provisória. Devolve (usuario, senha_provisoria). ValueError em português se não der."""
    if perfil not in PERFIS: raise ValueError('Escolha o perfil: Administrador ou Usuário.')
    senha = senha_provisoria(); u = core.db_auth_register_user(nome, email, senha)
    if perfil == 'admin': _sql(core, "UPDATE users SET role='admin' WHERE id=?", (u['id'],))
    marcar_trocar_senha(core, u['id']); return core.db_auth_get_user_by_id(u['id']), senha


def nova_provisoria(core, uid):
    senha = senha_provisoria(); core.db_auth_set_password(int(uid), senha); marcar_trocar_senha(core, uid); return senha


def mudar_perfil(core, uid, perfil):
    if perfil not in PERFIS: raise ValueError('Perfil inválido.')
    alvo = core.db_auth_get_user_by_id(uid)
    if not alvo: raise ValueError('Usuário não encontrado.')
    if alvo.get('role') == 'admin' and perfil == 'user' and alvo.get('status') == 'active' and not [a for a in admins_ativos(core) if int(a['id']) != int(uid)]:
        raise ValueError('O Exato precisa de pelo menos um administrador ativo. Torne outra pessoa administradora antes.')
    _sql(core, 'UPDATE users SET role=? WHERE id=?', (perfil, int(uid)))


def sem_usuarios(core):
    """True numa instalação nova: ainda não existe nenhuma pessoa com senha (é a hora de criar o primeiro administrador)."""
    con = core._auth_connect()
    try: return con.execute("SELECT COUNT(*) FROM users WHERE COALESCE(password_hash,'')<>''").fetchone()[0] == 0
    finally: con.close()


def eh_local(host, locais=None):
    """O pedido veio do próprio computador onde o Exato está instalado? (o primeiro administrador só pode ser criado dali)"""
    import socket
    host = str(host or '').strip().lower()
    if host in ('127.0.0.1', '::1', 'localhost'): return True
    if locais is None:
        locais = set()
        try:
            for r in socket.getaddrinfo(socket.gethostname(), None): locais.add(str(r[4][0]).lower())
        except OSError: pass
    return host in locais


def criar_primeiro_admin(core, nome, email, senha, repita):
    """Cria o primeiro administrador (só se ainda não há ninguém). ValueError em português se não der."""
    if not sem_usuarios(core): raise ValueError('O Exato já foi configurado. Entre com o seu e-mail e a sua senha.')
    if str(senha or '') != str(repita or ''): raise ValueError('A senha e a repetição são diferentes.')
    validar_senha_nova(senha, '', email)
    u = core.db_auth_register_user(nome, email, senha)
    _sql(core, "UPDATE users SET role='admin', must_set_password=0 WHERE id=?", (u['id'],)); return core.db_auth_get_user_by_id(u['id'])
