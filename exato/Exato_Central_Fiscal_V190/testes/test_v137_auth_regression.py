from __future__ import annotations
import os, sys, tempfile
from pathlib import Path
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v137_auth_')
os.environ['EXATO_CF_DEV']='1'
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import exato_central_fiscal as mod
mod.init_database()
admin=mod.db_auth_get_user(mod.AUTH_BOOTSTRAP_EMAIL)
assert admin and admin['name']=='Bruno Elias' and admin['role']=='admin' and admin['status']=='active' and admin['must_set_password']==1
assert mod._auth_validate_email('bruno@example.com') and not mod._auth_validate_email('bruno@')
assert mod.db_auth_set_password(admin['id'],'SenhaAdmin123')
logged=mod.db_auth_login(mod.AUTH_BOOTSTRAP_EMAIL,'SenhaAdmin123')
assert logged['role_label']=='Administrador'
new=mod.db_auth_register_user('Maria Teste','maria@example.com','SenhaMaria123')
assert new['status']=='pending' and mod.db_auth_activity(1)[0]['action']=='CADASTRO_SOLICITADO'
try: mod.db_auth_login('maria@example.com','SenhaMaria123')
except ValueError as exc: assert 'aguardando' in str(exc).lower()
else: raise AssertionError('pending user could login')
assert mod.db_auth_set_status(new['id'],'active',logged)
assert mod.db_auth_login('maria@example.com','SenhaMaria123')['email']=='maria@example.com'
assert mod.db_auth_set_status(new['id'],'blocked',logged)
try: mod.db_auth_login('maria@example.com','SenhaMaria123')
except ValueError as exc: assert 'bloqueado' in str(exc).lower()
else: raise AssertionError('blocked user could login')
try: mod.db_auth_set_status(logged['id'],'blocked',logged)
except ValueError as exc: assert 'própria' in str(exc).lower()
else: raise AssertionError('current admin could block self')
print('V137 auth core: OK')
