from __future__ import annotations
import os, sys, tempfile, importlib.util
from pathlib import Path

DATA=tempfile.mkdtemp(prefix='exato_v137_upgrade_')
os.environ['EXATO_DATA_DIR']=DATA
os.environ['EXATO_CF_DEV']='1'

v135_root=Path('/mnt/data/work_v137/Exato_Central_Fiscal_V135_original/Exato_Central_Fiscal_V135')
v137_root=Path('/mnt/data/work_v137/Exato_Central_Fiscal_V137')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec); assert spec.loader
    sys.modules[name]=mod; spec.loader.exec_module(mod); return mod

v135=load('exato_v135_upgrade',v135_root/'exato_central_fiscal.py')
v135.init_database()
admin=v135.db_auth_get_user(v135.AUTH_BOOTSTRAP_EMAIL)
v135.db_auth_set_password(admin['id'],'SenhaAdmin123')
assert v135.db_auth_login(admin['email'],'SenhaAdmin123')['email']==v135.AUTH_BOOTSTRAP_EMAIL

v137=load('exato_v137_upgrade',v137_root/'exato_central_fiscal.py')
v137.init_database()
admin2=v137.db_auth_get_user(v137.AUTH_BOOTSTRAP_EMAIL)
assert admin2 and admin2['must_set_password']==0
logged=v137.db_auth_login(admin2['email'],'SenhaAdmin123')
assert logged['email']==v137.AUTH_BOOTSTRAP_EMAIL
assert logged['role']=='admin'
print('V137 upgrade persistence: OK')
