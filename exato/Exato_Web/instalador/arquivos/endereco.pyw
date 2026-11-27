"""Prepara o endereço seguro do escritório (roda com permissão de administrador, chamado pelo instalador): endereco.pyw <pasta do Exato Web> <pasta dos dados> <endereço>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import endereco

if __name__ == '__main__':
    app, dados, nome = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    try: ok, msg = endereco.configurar(app / 'app', dados, nome)
    except Exception as e: ok, msg = False, f'Não consegui preparar o endereço seguro: {type(e).__name__}'
    try:
        (dados / 'logs').mkdir(parents=True, exist_ok=True)
        with open(dados / 'logs' / 'endereco.log', 'a', encoding='utf-8') as f: f.write(('OK  ' if ok else 'ERRO') + f' {nome}: {msg}\n')
    except OSError: pass
    sys.exit(0 if ok else 1)
