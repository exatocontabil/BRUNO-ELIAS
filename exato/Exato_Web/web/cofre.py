"""Cofre dos certificados A1 (Exato Web). Sem Tkinter, sem banco.

O arquivo do certificado (.pfx/.p12) e a senha NUNCA ficam em claro no disco: cada certificado é guardado criptografado (AES-256-GCM) com uma chave mestra
que só o servidor consegue abrir (no Windows, protegida pelo DPAPI da conta que roda o site). Os dados que não são segredo (titular, CNPJ, validade) ficam em
um arquivo ao lado, para listar sem abrir o certificado.

Para consultar a SEFAZ o Exato precisa do certificado no repositório do Windows (é como as rotinas fiscais atuais o usam). `Cofre.usar()` coloca o certificado lá
só durante a consulta (sem permitir exportar a chave) e o retira em seguida, mesmo se houver erro."""
import base64, contextlib, hashlib, json, os, re, subprocess, sys, threading
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography import x509


class CofreErro(Exception):
    """Erro com texto pronto para mostrar ao usuário."""


def _digitos(x): return re.sub(r'\D', '', str(x or ''))


def _id_valido(chave):
    d = _digitos(chave)
    if str(chave) == 'escritorio': return 'escritorio'
    if len(d) == 14: return d
    raise CofreErro('Informe o CNPJ da empresa (14 dígitos) ou "escritório".')


# ------------------------------------------------------------------ chave mestra
def _dpapi(dados, proteger):
    """Protege/abre dados com o DPAPI do Windows (só a conta que roda o site consegue abrir)."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
    entrada = BLOB(len(dados), ctypes.cast(ctypes.create_string_buffer(dados, len(dados)), ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if proteger else ctypes.windll.crypt32.CryptUnprotectData
    args = (ctypes.byref(entrada), 'ExatoWeb' if proteger else None, None, None, None, 0, ctypes.byref(saida)) if proteger else (ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida))
    if not fn(*args): raise CofreErro('O Windows não liberou a chave do cofre (a conta que roda o site mudou?).')
    try: return ctypes.string_at(saida.pbData, saida.cbData)
    finally: ctypes.windll.kernel32.LocalFree(saida.pbData)


def carregar_chave_mestra(pasta):
    """Chave de 32 bytes do cofre. Criada na primeira vez. Windows: protegida pelo DPAPI. Outros sistemas (só desenvolvimento/teste): arquivo restrito."""
    pasta = Path(pasta); pasta.mkdir(parents=True, exist_ok=True)
    env = os.environ.get('EXATO_WEB_COFRE_CHAVE')
    if env: return hashlib.sha256(env.encode('utf-8')).digest()
    arq = pasta / 'chave.mestra'
    if arq.exists():
        bruto = arq.read_bytes()
        return _dpapi(bruto, False) if sys.platform == 'win32' else bruto
    chave = os.urandom(32)
    arq.write_bytes(_dpapi(chave, True) if sys.platform == 'win32' else chave)
    try: os.chmod(arq, 0o600)
    except Exception: pass
    return chave


# ------------------------------------------------------------------ certificado
def _cnpj_do_certificado(cert):
    cn = ''
    try: cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    except Exception: pass
    m = re.search(r'(\d{14})\b', cn)
    if m: return m.group(1)
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        for o in san:
            if isinstance(o, x509.OtherName):
                m = re.search(rb'(\d{14})', o.value)
                if m: return m.group(1).decode()
    except Exception: pass
    return ''


def ler_pfx(pfx, senha):
    """Abre o certificado A1 e devolve os dados públicos. Erros em linguagem simples."""
    try: chave, cert, _extra = pkcs12.load_key_and_certificates(pfx, (senha or '').encode('utf-8'))
    except Exception:
        raise CofreErro('Não foi possível abrir o certificado: a senha está errada ou o arquivo não é um certificado A1 (.pfx/.p12).')
    if cert is None or chave is None: raise CofreErro('O arquivo não contém a chave privada do certificado. Envie o arquivo A1 completo (.pfx/.p12).')
    fim = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after.replace(tzinfo=timezone.utc)
    try: nome = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    except Exception: nome = ''
    return {'titular': nome, 'titular_cnpj': _cnpj_do_certificado(cert), 'validade': fim.date().isoformat(), 'vencido': fim < datetime.now(timezone.utc),
            'thumbprint': hashlib.sha1(cert.public_bytes(__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.DER)).hexdigest().upper()}


# ------------------------------------------------------------------ importadores (repositório de certificados do Windows)
_PS_IMPORTAR = r'''$ErrorActionPreference='Stop'
$b=[Convert]::FromBase64String($env:EXATO_PFX); $s=$env:EXATO_PFX_SENHA
$f=[Security.Cryptography.X509Certificates.X509KeyStorageFlags]::UserKeySet -bor [Security.Cryptography.X509Certificates.X509KeyStorageFlags]::PersistKeySet
$c=New-Object Security.Cryptography.X509Certificates.X509Certificate2($b,$s,$f)
$st=New-Object Security.Cryptography.X509Certificates.X509Store('My','CurrentUser'); $st.Open('ReadWrite'); $st.Add($c); $st.Close()
Write-Output $c.Thumbprint'''
_PS_REMOVER = r'''$ErrorActionPreference='SilentlyContinue'
$st=New-Object Security.Cryptography.X509Certificates.X509Store('My','CurrentUser'); $st.Open('ReadWrite')
foreach($x in $st.Certificates.Find('FindByThumbprint',$env:EXATO_THUMB,$false)){
  try{ $k=[Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($x)
       if($k -is [Security.Cryptography.RSACryptoServiceProvider]){$k.PersistKeyInCsp=$false;$k.Clear()} elseif($k -is [Security.Cryptography.RSACng]){$k.Key.Delete()} }catch{}
  $st.Remove($x) }
$st.Close()'''


class ImportadorWindows:
    """Coloca o A1 no repositório do usuário do Windows que roda o site (chave não exportável pelo programa) e o retira depois."""
    def _ps(self, script, env_extra, timeout=60):
        env = dict(os.environ); env.update(env_extra)
        p = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script], capture_output=True, text=True, timeout=timeout, env=env, encoding='utf-8', errors='replace')
        return p.returncode, (p.stdout or '').strip(), (p.stderr or '').strip()

    def importar(self, pfx, senha):
        rc, out, err = self._ps(_PS_IMPORTAR, {'EXATO_PFX': base64.b64encode(pfx).decode('ascii'), 'EXATO_PFX_SENHA': senha})
        if rc != 0 or not out: raise CofreErro('O Windows não aceitou o certificado para a consulta. ' + (err.splitlines()[0][:160] if err else ''))
        return out.splitlines()[-1].strip().upper()

    def remover(self, thumbprint):
        try: self._ps(_PS_REMOVER, {'EXATO_THUMB': thumbprint})
        except Exception: pass


class ImportadorFalso:
    """Para testes e desenvolvimento fora do Windows: não instala nada, só registra o que aconteceu."""
    def __init__(self): self.eventos = []
    def importar(self, pfx, senha):
        info = ler_pfx(pfx, senha); self.eventos.append(('importar', info['thumbprint'])); return info['thumbprint']
    def remover(self, thumbprint): self.eventos.append(('remover', thumbprint))


# ------------------------------------------------------------------ cofre
class Cofre:
    def __init__(self, pasta, chave=None, importador=None):
        self.pasta = Path(pasta); self.pasta.mkdir(parents=True, exist_ok=True)
        chave = chave or carregar_chave_mestra(self.pasta); self._aes = AESGCM(chave); self._aes_txt = AESGCM(hashlib.sha256(chave + b'texto').digest())
        self.importador = importador or (ImportadorWindows() if sys.platform == 'win32' else ImportadorFalso())
        self._trava = threading.Lock(); self._em_uso = {}

    def _arq(self, chave, ext): return self.pasta / f'{_id_valido(chave)}.{ext}'

    def guardar(self, chave, pfx, senha, enviado_por=''):
        """Confere o certificado (senha, chave privada, validade) e o guarda criptografado. Devolve os dados públicos."""
        cid = _id_valido(chave); info = ler_pfx(pfx, senha)
        if info['vencido']: raise CofreErro(f"Este certificado venceu em {info['validade']}. Envie o certificado novo.")
        nonce = os.urandom(12); carga = json.dumps({'pfx': base64.b64encode(pfx).decode('ascii'), 'senha': senha}).encode('utf-8')
        cifrado = nonce + self._aes.encrypt(nonce, carga, cid.encode('ascii'))
        info.update({'id': cid, 'enviado_por': enviado_por, 'enviado_em': datetime.now().isoformat(timespec='seconds')})
        tmp = self._arq(cid, 'cof.tmp'); tmp.write_bytes(cifrado); os.replace(tmp, self._arq(cid, 'cof'))
        try: os.chmod(self._arq(cid, 'cof'), 0o600)
        except Exception: pass
        self._arq(cid, 'json').write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding='utf-8')
        return info

    def proteger_texto(self, texto):
        """Criptografa um texto curto (ex.: a senha do e-mail do Box-e) para guardar na configuração. Devolve texto seguro para gravar."""
        n = os.urandom(12); return base64.b64encode(n + self._aes_txt.encrypt(n, str(texto).encode('utf-8'), b'texto')).decode('ascii')

    def abrir_texto(self, protegido):
        try: b = base64.b64decode(protegido); return self._aes_txt.decrypt(b[:12], b[12:], b'texto').decode('utf-8')
        except Exception: return ''

    def info(self, chave):
        try: return json.loads(self._arq(chave, 'json').read_text(encoding='utf-8'))
        except Exception: return None

    def listar(self):
        out = []
        for p in sorted(self.pasta.glob('*.json')):
            try:
                i = json.loads(p.read_text(encoding='utf-8'))
                i['vencido'] = i.get('validade', '9999') < datetime.now().date().isoformat(); out.append(i)
            except Exception: pass
        return out

    def remover(self, chave):
        for ext in ('cof', 'json'):
            try: self._arq(chave, ext).unlink()
            except FileNotFoundError: pass

    def _abrir(self, chave):
        cid = _id_valido(chave)
        try: bruto = self._arq(cid, 'cof').read_bytes()
        except FileNotFoundError: raise CofreErro('Esta empresa não tem certificado A1 guardado no site.')
        try: d = json.loads(self._aes.decrypt(bruto[:12], bruto[12:], cid.encode('ascii')))
        except Exception: raise CofreErro('Não foi possível abrir o certificado guardado (a chave do cofre mudou?). Envie o certificado de novo.')
        return base64.b64decode(d['pfx']), d['senha']

    def material(self, chave):
        """(chave privada, certificado) do A1, carregados só na memória — para assinar documentos (ex.: eventos da NF-e) sem passar pelo Windows."""
        pfx, senha = self._abrir(chave)
        try:
            k, cert, _extra = pkcs12.load_key_and_certificates(pfx, senha.encode('utf-8'))
        except Exception:
            raise CofreErro('Não foi possível abrir o certificado guardado. Envie o certificado de novo.')
        return k, cert

    @contextlib.contextmanager
    def usar(self, chave):
        """Dá o certificado ao Windows só durante o bloco e devolve a impressão digital (thumbprint) que as rotinas fiscais usam."""
        info = self.info(chave)
        if info and info.get('validade', '9999') < datetime.now().date().isoformat(): raise CofreErro(f"O certificado guardado venceu em {info['validade']}. Envie o novo.")
        pfx, senha = self._abrir(chave); cid = _id_valido(chave); thumb = None
        with self._trava:
            try:
                thumb = self.importador.importar(pfx, senha); self._em_uso[thumb] = self._em_uso.get(thumb, 0) + 1
            except Exception:
                thumb = None; raise
        try: yield thumb
        finally:
            with self._trava:
                self._em_uso[thumb] = self._em_uso.get(thumb, 1) - 1
                if self._em_uso[thumb] <= 0:
                    self._em_uso.pop(thumb, None); self.importador.remover(thumb)
