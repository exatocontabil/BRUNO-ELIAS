"""Acessos guardados por empresa (usuário/senha do portal da NFS-e e a sessão do portal).

A senha só é guardada se o usuário pedir. Nunca vai em texto aberto: no Windows é criptografada com a proteção do
próprio Windows (DPAPI) e só abre neste computador, com o mesmo usuário do Windows. O arquivo não entra nos backups.
Fora do Windows (testes) usa uma chave local do computador, só para o programa funcionar.
"""
import base64
import ctypes
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_ENTROPY = b'Exato Central Fiscal - acessos'


class _Blob(ctypes.Structure):
    _fields_ = [('cbData', ctypes.c_uint32), ('pbData', ctypes.POINTER(ctypes.c_char))]


def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _dpapi(data, protect):
    crypt32 = ctypes.windll.crypt32; kernel32 = ctypes.windll.kernel32
    src, keep1 = _blob(data); ent, keep2 = _blob(_ENTROPY); out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    args = (ctypes.byref(src), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out)) if protect else (ctypes.byref(src), None, ctypes.byref(ent), None, None, 0, ctypes.byref(out))
    if not fn(*args):
        raise ValueError('não foi possível proteger/abrir o dado')
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def _local_key(folder):
    path = Path(folder) / '.chave_local'
    if not path.exists():
        path.write_bytes(os.urandom(32))
    return path.read_bytes()


def _stream_xor(data, key):
    out = bytearray(); counter = 0
    while len(out) < len(data):
        out += hmac.new(key, counter.to_bytes(8, 'big'), hashlib.sha256).digest(); counter += 1
    return bytes(a ^ b for a, b in zip(data, out))


class AcessosStore:
    def __init__(self, folder):
        self.folder = Path(folder); self.path = self.folder / 'nfse_acessos.json'

    # ---- proteção
    def protect(self, text):
        raw = str(text or '').encode('utf-8')
        if sys.platform == 'win32':
            return 'dpapi:' + base64.b64encode(_dpapi(raw, True)).decode('ascii')
        self.folder.mkdir(parents=True, exist_ok=True)
        return 'local:' + base64.b64encode(_stream_xor(raw, _local_key(self.folder))).decode('ascii')

    def unprotect(self, token):
        token = str(token or '')
        try:
            if token.startswith('dpapi:') and sys.platform == 'win32':
                return _dpapi(base64.b64decode(token[6:]), False).decode('utf-8')
            if token.startswith('local:'):
                return _stream_xor(base64.b64decode(token[6:]), _local_key(self.folder)).decode('utf-8')
        except Exception:
            return ''
        return ''

    # ---- arquivo
    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self, data):
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8'); tmp.replace(self.path)

    @staticmethod
    def _key(cnpj):
        return ''.join(ch for ch in str(cnpj or '') if ch.isdigit())

    # ---- uso
    def save_login(self, cnpj, user, password):
        data = self._load(); k = self._key(cnpj)
        entry = data.get(k, {}); entry.update({'usuario': str(user or ''), 'senha': self.protect(password), 'atualizado': datetime.now().isoformat(timespec='seconds')})
        data[k] = entry; self._save(data)

    def get_login(self, cnpj):
        """(usuário, senha) guardados; ('', '') se não houver."""
        entry = self._load().get(self._key(cnpj)) or {}
        return entry.get('usuario', ''), self.unprotect(entry.get('senha', '')) if entry.get('senha') else ''

    def has_password(self, cnpj):
        return bool((self._load().get(self._key(cnpj)) or {}).get('senha'))

    def save_session(self, cnpj, session_json):
        data = self._load(); k = self._key(cnpj)
        entry = data.get(k, {}); entry['sessao'] = self.protect(session_json); entry['sessao_em'] = datetime.now().isoformat(timespec='seconds')
        data[k] = entry; self._save(data)

    def get_session(self, cnpj):
        entry = self._load().get(self._key(cnpj)) or {}
        return self.unprotect(entry.get('sessao', '')) if entry.get('sessao') else ''

    def forget_session(self, cnpj):
        data = self._load(); entry = data.get(self._key(cnpj))
        if entry and 'sessao' in entry:
            entry.pop('sessao', None); entry.pop('sessao_em', None); self._save(data)

    def forget(self, cnpj):
        """Esquece a senha e a sessão desta empresa (mantém só o usuário de acesso)."""
        data = self._load(); k = self._key(cnpj); entry = data.get(k)
        if entry:
            for f in ('senha', 'sessao', 'sessao_em'):
                entry.pop(f, None)
            data[k] = entry; self._save(data)
