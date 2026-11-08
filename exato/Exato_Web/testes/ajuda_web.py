"""Ajudas dos testes do Exato Web (sem efeitos ao importar)."""
import datetime
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


def gerar_a1(cnpj, senha, dias=365, nome='EMPRESA TESTE LTDA'):
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nm = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f'{nome}:{cnpj}')]); agora = datetime.datetime.now(datetime.timezone.utc)
    cert = x509.CertificateBuilder().subject_name(nm).issuer_name(nm).public_key(chave.public_key()).serial_number(x509.random_serial_number()).not_valid_before(agora - datetime.timedelta(days=max(10, 2 - dias))).not_valid_after(agora + datetime.timedelta(days=dias)).sign(chave, hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(b'x', chave, cert, None, serialization.BestAvailableEncryption(senha.encode()))
