import os, shutil, sqlite3, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(code, data_dir, extra_env=None):
    env=os.environ.copy(); env['EXATO_DATA_DIR']=str(data_dir); env['PYTHONPATH']=str(ROOT)
    if extra_env: env.update(extra_env)
    return subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True)

def main():
    work=Path(tempfile.mkdtemp(prefix='exato_v139_auth_test_'))
    try:
        code="import exato_central_fiscal as m; m.init_database(); u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL); m.db_auth_set_password(u['id'],'TesteSenha123'); print(m.db_auth_login(u['email'],'TesteSenha123')['email']); n=m.db_auth_register_user('Usuário Teste','usuario.teste@example.com','SenhaTeste123'); print(n['status']); print(m.db_auth_login(n['email'],'SenhaTeste123')['email'])"
        p=run(code,work)
        assert p.returncode==0, p.stderr
        assert 'brunoalbano.elias8@gmail.com' in p.stdout
        assert 'active' in p.stdout
        p2=run("import exato_central_fiscal as m; m.init_database(); print(m.db_auth_login(m.AUTH_BOOTSTRAP_EMAIL,'TesteSenha123')['email']); print(m.db_auth_login('usuario.teste@example.com','SenhaTeste123')['email'])",work)
        assert p2.returncode==0, p2.stderr
        db=work/'usuarios.db'
        assert db.exists()
        con=sqlite3.connect(db); rows=con.execute("select email,status from users order by id").fetchall(); con.close()
        assert all(status=='active' for _,status in rows)
        p3=run("import exato_central_fiscal as m; m.init_database(); b=m.create_data_backup('auth_test'); import zipfile; z=zipfile.ZipFile(b); print(sorted(z.namelist()))",work)
        assert p3.returncode==0, p3.stderr
        assert 'usuarios.db' in p3.stdout
        print('V139 auth tests: OK')
    finally:
        shutil.rmtree(work,ignore_errors=True)
if __name__=='__main__': main()
