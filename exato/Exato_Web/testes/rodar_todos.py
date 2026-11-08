"""Roda todos os testes do Exato Web (cada um em um processo separado)."""
import subprocess, sys
from pathlib import Path
aqui = Path(__file__).resolve().parent; falhas = []
for t in sorted(aqui.glob('test_web_*.py')):
    r = subprocess.run([sys.executable, str(t)], capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or [''])[-1]; ok = r.returncode == 0
    print(('OK     ' if ok else 'FALHOU ') + t.name + ('' if ok else '\n' + (r.stderr or r.stdout)[-800:]))
    if not ok: falhas.append(t.name)
print(f'\n{len(list(aqui.glob("test_web_*.py"))) - len(falhas)}/{len(list(aqui.glob("test_web_*.py")))} testes passaram'); sys.exit(1 if falhas else 0)
