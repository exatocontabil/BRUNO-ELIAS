"""Capturas de tela das telas principais (V182) para o teste no Windows do GitHub: claro e escuro, 1366x650.

Uso: python scripts/capturas_windows.py <pasta de saída>
Gera PNGs (um por tela e tema) e um resumo `capturas.txt` com erros de abertura de tela. Serve para ver, a cada envio, o que só aparece no Windows
(rolagem, cores, texto sobreposto). Não falha o teste por causa da imagem; falha só se uma tela não abrir.
"""
import os, sys, tempfile, time, traceback
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
saida = Path(sys.argv[1] if len(sys.argv) > 1 else 'capturas'); saida.mkdir(parents=True, exist_ok=True)
os.environ['EXATO_DATA_DIR'] = tempfile.mkdtemp(prefix='exato_cap_'); os.environ['EXATO_UI_SYNC'] = '1'
sys.path[:0] = [str(RAIZ / 'programa'), str(RAIZ / 'programa' / 'third_party'), str(RAIZ / 'testes')]
tema = (sys.argv[2] if len(sys.argv) > 2 else 'claro')
import exato_central_fiscal as m
m.exato_ui.set_mode(tema)
from PIL import ImageGrab
import test_v182_auditoria_cancelada as T          # banco com notas para as telas não saírem vazias
m.init_database(); u = m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'], 'S#2026aaa'); user = m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL, 'S#2026aaa')
m.enumerate_windows_certificates = lambda *a, **k: ([], '')
app = m.App(current_user=user); app.geometry('1366x650+20+20')
erros = []
def foto(nome):
    for _ in range(25): app.update_idletasks(); app.update(); time.sleep(.05)
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + app.winfo_width(), y + app.winfo_height())).save(saida / f'{nome}_{tema}.png')
telas = [('inicio', '_show_dashboard'), ('buscar_xml', '_show_webservice_test'), ('nfse', '_show_nfse'), ('documentos', '_show_documents'), ('auditoria', '_show_audit'),
         ('empresas', '_show_companies'), ('repositorio', '_show_repo'), ('relatorios', '_show_reports'), ('historico', '_show_history'), ('pendencias', '_show_pending')]
try:
    for nome, fn in telas:
        try:
            getattr(app, fn)(); foto(nome)
            try: app.workspace_canvas.yview_moveto(1.0); foto(nome + '_fim')          # rola até o fim e tira outra: mostra rastro/sobreposição
            except Exception: pass
        except Exception:
            erros.append(f'{nome}: {traceback.format_exc(limit=3)}')
finally:
    try: app.destroy()
    except Exception: pass
(saida / f'capturas_{tema}.txt').write_text('\n'.join(erros) or 'Todas as telas abriram.', encoding='utf-8')
print('\n'.join(erros) or 'Todas as telas abriram.')
sys.exit(1 if erros else 0)
