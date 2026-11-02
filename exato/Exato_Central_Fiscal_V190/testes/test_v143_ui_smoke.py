import os, sys, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v143_ui_')
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as m
m.init_database()
u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL)
m.db_auth_set_password(u['id'],'SenhaUI#2026')
user=m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'SenhaUI#2026')
app=m.App(current_user=user)
try:
    app.update_idletasks(); app.update()
    assert m.APP_VERSION=='V143'
    app._show_companies(); app.update_idletasks(); app.update()
    assert tuple(app.company_tree['columns']) == ('name','cnpj','docs','last','update','search')
    combos=[]
    def collect(w):
        for child in w.winfo_children():
            try:
                if child.winfo_class()=='TCombobox':
                    combos.append(child)
            except Exception:
                pass
            try:
                collect(child)
            except Exception:
                pass
    collect(app.companies_frame)
    assert combos and tuple(combos[0]['values']) == ('Todas','Atualizadas','Atenção','Desatualizadas')
    texts=[]
    def collect_texts(w):
        for child in w.winfo_children():
            try: texts.append(child.cget('text'))
            except Exception: pass
            try: collect_texts(child)
            except Exception: pass
    collect_texts(app.companies_frame)
    joined=' '.join(str(t) for t in texts)
    assert 'Atualizada — busca nos últimos 24h' in joined
    assert 'Atenção — última busca entre 24h e 72h' in joined
    assert 'Desatualizada — mais de 72h sem busca ou nunca buscada' in joined
finally:
    app.destroy(); shutil.rmtree(os.environ['EXATO_DATA_DIR'],ignore_errors=True)
print('V143 UI smoke: OK')
