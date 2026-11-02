from __future__ import annotations
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
required = [
    'logo_exato_v061.png', 'logo_exato_mark.png',
    'exato_ia_transparente.png', 'exato_ia_look_left.png',
    'exato_ia_look_center.png', 'exato_ia_look_right.png',
    'exato_ia_mascote_sheet.png', 'exato_ia_conforme_transparent.png',
]
for name in required:
    assert (ASSETS / name).is_file(), f'Missing visual asset: {name}'

# Hashes are the V135 reference values; the V137 package must preserve them.
expected = {
    'logo_exato_v061.png': '32e01d3dcf96a197',
    'logo_exato_mark.png': '31305ae3e649b537',
    'exato_ia_transparente.png': 'a697b3917dd33906',
    'exato_ia_look_left.png': 'fa9ef52b37df66c3',
    'exato_ia_look_center.png': 'ad9d444cf086a549',
    'exato_ia_look_right.png': '8116a070016f7170',
    'exato_ia_mascote_sheet.png': 'e07b04f20522fba2',
    'exato_ia_conforme_transparent.png': 'e9f0e4806f0e4a46',
}
for name, prefix in expected.items():
    h = hashlib.sha256((ASSETS / name).read_bytes()).hexdigest()[:16]
    assert h == prefix, f'Asset changed unexpectedly: {name}'

src = (ROOT / 'exato_central_fiscal.py').read_text(encoding='utf-8')
assert 'APP_VERSION = "V137"' in src
for marker in ['LOGO_PATH', 'MASCOT_EXATO_IA_PATH', '_exatinho_', 'EXATINHO']:
    assert marker in src, f'Visual/persona marker missing: {marker}'
assert 'ESQUECI MINHA SENHA' in src
print('V137 visual parity: OK')
