"""Executa a suíte atual de testes (uma lista curada, sem os testes históricos de versões antigas).

Uso: python testes/run_suite.py     (no Linux/CI: xvfb-run -a python testes/run_suite.py)
"""
import os, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
SUITE = [l.strip() for l in (HERE / 'SUITE_ATUAL.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]
PULAR = [x.strip() for x in os.environ.get('EXATO_PULAR', '').split(',') if x.strip()]          # ex.: EXATO_PULAR=nfse_portal (navegador de verdade, só no Linux/CI)
failed = []
for name in SUITE:
    if any(x in name for x in PULAR):
        print(f'PULOU  {name}'); continue
    t = time.time()
    r = subprocess.run([sys.executable, str(HERE / name)], capture_output=True, text=True, timeout=900, env={**os.environ, 'EXATO_UI_SYNC': '1'})   # listas da tela entram de uma vez nos testes (no programa entram em fatias)
    ok = r.returncode == 0
    print(f"{'OK    ' if ok else 'FALHOU'} {name} ({time.time() - t:.1f}s)")
    if not ok:
        failed.append(name)
        print((r.stdout + r.stderr)[-1500:])
print(f"\n{len(SUITE) - len(failed)}/{len(SUITE)} testes passaram")
sys.exit(1 if failed else 0)
