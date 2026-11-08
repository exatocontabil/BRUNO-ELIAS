"""Segurança do Exato Web: sessão assinada, proteção contra pedidos forjados (CSRF), limite de tentativas de login e verificação em duas etapas (TOTP).
Sem dependências além da biblioteca padrão e `cryptography`."""
import base64, hashlib, hmac, json, os, secrets, sqlite3, struct, threading, time
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import config


# ------------------------------------------------------------------ cookies assinados
def _b64(b): return base64.urlsafe_b64encode(b).decode('ascii').rstrip('=')
def _unb64(s): return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def assinar(dados, validade_s):
    carga = dict(dados); carga['exp'] = int(time.time() + validade_s)
    corpo = _b64(json.dumps(carga, separators=(',', ':')).encode('utf-8'))
    return corpo + '.' + _b64(hmac.new(config.chave_sessao(), corpo.encode('ascii'), hashlib.sha256).digest())


def verificar(token):
    """Dados do cookie se a assinatura e a validade estão corretas; senão None."""
    try:
        corpo, mac = str(token).split('.', 1)
        esperado = _b64(hmac.new(config.chave_sessao(), corpo.encode('ascii'), hashlib.sha256).digest())
        if not hmac.compare_digest(mac, esperado): return None
        d = json.loads(_unb64(corpo))
        return d if d.get('exp', 0) >= time.time() else None
    except Exception:
        return None


# ------------------------------------------------------------------ limite de tentativas
class LimiteLogin:
    def __init__(self, tentativas=None, minutos=None):
        self.max = tentativas or config.TENTATIVAS_LOGIN; self.bloqueio = (minutos or config.BLOQUEIO_MINUTOS) * 60
        self._f = {}; self._trava = threading.Lock()

    def _chaves(self, ip, email): return (('ip', ip), ('email', str(email or '').strip().lower()))

    def bloqueado(self, ip, email):
        """Segundos que faltam para liberar (0 = liberado)."""
        agora = time.time(); falta = 0
        with self._trava:
            for k in self._chaves(ip, email):
                n, ate = self._f.get(k, (0, 0))
                if ate > agora: falta = max(falta, int(ate - agora) + 1)
        return falta

    def falhou(self, ip, email):
        agora = time.time()
        with self._trava:
            for k in self._chaves(ip, email):
                n, ate = self._f.get(k, (0, 0))
                n = 1 if ate and ate <= agora else n + 1          # bloqueio acabou: recomeça a contar
                self._f[k] = (n, agora + self.bloqueio if n >= self.max else 0)

    def acertou(self, ip, email):
        with self._trava:
            for k in self._chaves(ip, email): self._f.pop(k, None)


# ------------------------------------------------------------------ TOTP (RFC 6238) — aplicativo autenticador
def novo_segredo():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii')


def _hotp(segredo, contador, digitos=6):
    chave = base64.b32decode(segredo.replace(' ', '').upper() + '=' * (-len(segredo.replace(' ', '')) % 8))
    h = hmac.new(chave, struct.pack('>Q', contador), hashlib.sha1).digest(); o = h[-1] & 15
    return str((struct.unpack('>I', h[o:o + 4])[0] & 0x7fffffff) % (10 ** digitos)).zfill(digitos)


def codigo_totp(segredo, agora=None): return _hotp(segredo, int((agora or time.time()) // 30))


def passo_valido(segredo, codigo, agora=None, janela=1):
    """Número do passo de 30 s em que o código vale (aceita 1 passo antes/depois por diferença de relógio) ou None."""
    codigo = ''.join(ch for ch in str(codigo or '') if ch.isdigit())
    if len(codigo) != 6: return None
    base = int((agora or time.time()) // 30)
    for p in range(base - janela, base + janela + 1):
        if hmac.compare_digest(_hotp(segredo, p), codigo): return p
    return None


def uri_totp(segredo, email, emissor='Exato Web'):
    from urllib.parse import quote
    return f'otpauth://totp/{quote(emissor)}:{quote(email)}?secret={segredo}&issuer={quote(emissor)}&digits=6&period=30'


class Totp:
    """Segredos de verificação em duas etapas por usuário, guardados criptografados em web.db."""
    def __init__(self, caminho, chave):
        self.caminho = Path(caminho); self._aes = AESGCM(hashlib.sha256(chave + b'totp').digest())
        c = self._con(); c.execute("CREATE TABLE IF NOT EXISTS totp(user_id INTEGER PRIMARY KEY, segredo BLOB NOT NULL, ativo INTEGER NOT NULL DEFAULT 0, ultimo_passo INTEGER NOT NULL DEFAULT 0)"); c.commit(); c.close()

    def _con(self): return sqlite3.connect(self.caminho, timeout=15)

    def _cif(self, s, uid): n = os.urandom(12); return n + self._aes.encrypt(n, s.encode('ascii'), str(uid).encode())
    def _dec(self, b, uid): return self._aes.decrypt(b[:12], b[12:], str(uid).encode()).decode('ascii')

    def preparar(self, uid):
        """Cria (ou devolve o ainda não confirmado) segredo para o usuário configurar no aplicativo."""
        c = self._con(); r = c.execute("SELECT segredo, ativo FROM totp WHERE user_id=?", (uid,)).fetchone()
        if r and r[1]: c.close(); return None          # já ativo
        seg = self._dec(r[0], uid) if r else novo_segredo()
        if not r: c.execute("INSERT INTO totp(user_id, segredo, ativo) VALUES(?,?,0)", (uid, self._cif(seg, uid))); c.commit()
        c.close(); return seg

    def ativo(self, uid):
        c = self._con(); r = c.execute("SELECT ativo FROM totp WHERE user_id=?", (uid,)).fetchone(); c.close(); return bool(r and r[0])

    def confirmar(self, uid, codigo, agora=None):
        """Ativa a verificação se o código está certo. True/False."""
        c = self._con(); r = c.execute("SELECT segredo, ultimo_passo FROM totp WHERE user_id=?", (uid,)).fetchone()
        if not r: c.close(); return False
        p = passo_valido(self._dec(r[0], uid), codigo, agora)
        if p is None: c.close(); return False
        c.execute("UPDATE totp SET ativo=1, ultimo_passo=? WHERE user_id=?", (p, uid)); c.commit(); c.close(); return True

    def conferir(self, uid, codigo, agora=None):
        """Confere o código de quem já tem a verificação ativa. Um mesmo código não vale duas vezes."""
        c = self._con(); r = c.execute("SELECT segredo, ultimo_passo FROM totp WHERE user_id=? AND ativo=1", (uid,)).fetchone()
        if not r: c.close(); return False
        p = passo_valido(self._dec(r[0], uid), codigo, agora)
        if p is None or p <= r[1]: c.close(); return False
        c.execute("UPDATE totp SET ultimo_passo=? WHERE user_id=?", (p, uid)); c.commit(); c.close(); return True

    def desativar(self, uid):
        c = self._con(); c.execute("DELETE FROM totp WHERE user_id=?", (uid,)); c.commit(); c.close()


class Sessoes:
    """Sessões válidas guardadas no servidor (web.db): sair do site ou trocar a senha derruba a sessão na hora, mesmo que alguém tenha copiado o cookie."""
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        c = self._con(); c.execute("CREATE TABLE IF NOT EXISTS sessoes(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expira REAL NOT NULL)"); c.commit(); c.close()

    def _con(self): return sqlite3.connect(self.caminho, timeout=15)

    def criar(self, uid, validade_s):
        sid = secrets.token_urlsafe(24); c = self._con()
        c.execute("DELETE FROM sessoes WHERE expira < ?", (time.time(),)); c.execute("INSERT INTO sessoes(id, user_id, expira) VALUES(?,?,?)", (sid, uid, time.time() + validade_s)); c.commit(); c.close(); return sid

    def usuario(self, sid):
        c = self._con(); r = c.execute("SELECT user_id FROM sessoes WHERE id=? AND expira>=?", (str(sid or ''), time.time())).fetchone(); c.close(); return r[0] if r else None

    def revogar(self, sid):
        c = self._con(); c.execute("DELETE FROM sessoes WHERE id=?", (str(sid or ''),)); c.commit(); c.close()

    def revogar_usuario(self, uid):
        c = self._con(); c.execute("DELETE FROM sessoes WHERE user_id=?", (uid,)); c.commit(); c.close()
