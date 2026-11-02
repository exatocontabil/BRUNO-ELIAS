from __future__ import annotations
import os, sys, tempfile
from pathlib import Path
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v137_recovery_')
os.environ['EXATO_CF_DEV']='1'
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import exato_central_fiscal as mod

assert mod.APP_VERSION=='V137'
mod.init_database()
admin=mod.db_auth_get_user(mod.AUTH_BOOTSTRAP_EMAIL)
assert admin and admin['role']=='admin' and admin['status']=='active' and admin['must_set_password']==1
mod.db_auth_set_password(admin['id'],'SenhaAdmin123')
admin_login=mod.db_auth_login(admin['email'],'SenhaAdmin123')
assert admin_login['password_configured'] is True
user=mod.db_auth_register_user('Maria Recuperacao','maria.recovery@example.com','SenhaMaria123')
mod.db_auth_set_status(user['id'],'active',admin_login)
assert mod.db_auth_request_password_reset('maria.recovery@example.com') is True
requests=mod.db_auth_list_reset_requests(True)
assert len(requests)==1 and requests[0]['user_email']=='maria.recovery@example.com' and requests[0]['status']=='pending'
# Repeated requests should not create duplicate pending tickets.
assert mod.db_auth_request_password_reset('maria.recovery@example.com') is True
assert len(mod.db_auth_list_reset_requests(True))==1
# Administrator can resolve the request after resetting the user's password.
mod.db_auth_set_password(user['id'],'SenhaNova123')
assert mod.db_auth_resolve_reset_request(requests[0]['id'],admin_login,'resolved') is True
assert mod.db_auth_pending_reset_count()==0
assert mod.db_auth_list_reset_requests(True)==[]
logged=mod.db_auth_login('maria.recovery@example.com','SenhaNova123')
assert logged['email']=='maria.recovery@example.com'
# Unknown/inactive emails never reveal account existence through the core result.
assert mod.db_auth_request_password_reset('nao.existe@example.com') is False
mod.db_auth_set_status(user['id'],'blocked',admin_login)
assert mod.db_auth_request_password_reset('maria.recovery@example.com') is False
print('V137 password recovery core: OK')
