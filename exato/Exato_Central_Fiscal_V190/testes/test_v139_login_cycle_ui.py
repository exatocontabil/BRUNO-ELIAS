import os, sys, tempfile, shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
data_dir=tempfile.mkdtemp(prefix='exato_v139_login_cycle_')
os.environ['EXATO_DATA_DIR']=data_dir
sys.path.insert(0,str(ROOT))
import exato_central_fiscal as m

try:
    m.init_database()
    u=m.db_auth_get_user(m.AUTH_BOOTSTRAP_EMAIL)
    m.db_auth_set_password(u['id'],'SenhaAdmin123')

    login1=m.LoginWindow()
    login1.email.delete(0,'end'); login1.email.insert(0,m.AUTH_BOOTSTRAP_EMAIL)
    login1.password.insert(0,'SenhaAdmin123')
    login1._login()
    assert login1.authenticated_user['email']==m.AUTH_BOOTSTRAP_EMAIL

    login2=m.LoginWindow()
    login2.email.delete(0,'end'); login2.email.insert(0,m.AUTH_BOOTSTRAP_EMAIL)
    login2.password.insert(0,'SenhaAdmin123')
    login2._login()
    assert login2.authenticated_user['email']==m.AUTH_BOOTSTRAP_EMAIL
    print('V139 login logout/relogin UI: OK')
finally:
    try: login1.destroy()
    except Exception: pass
    try: login2.destroy()
    except Exception: pass
    shutil.rmtree(data_dir,ignore_errors=True)
