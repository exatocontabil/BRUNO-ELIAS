from __future__ import annotations
import os,sys,tempfile
from pathlib import Path
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v137_recovery_ui_')
os.environ['EXATO_CF_DEV']='1'
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import exato_central_fiscal as mod
mod.messagebox.showinfo=lambda *a,**k: None
mod.messagebox.showwarning=lambda *a,**k: None
mod.messagebox.showerror=lambda *a,**k: (_ for _ in ()).throw(AssertionError(f'error: {a}'))
mod.messagebox.askyesno=lambda *a,**k: True

def all_widgets(root):
    out=[]
    for child in root.winfo_children():
        out.append(child)
        out.extend(all_widgets(child))
    return out

mod.init_database()
login=mod.LoginWindow(); login.update_idletasks()
texts=[getattr(w,'cget')('text') for w in all_widgets(login) if hasattr(w,'cget') and 'text' in w.keys()]
assert 'ESQUECI MINHA SENHA' in texts
login.destroy()
admin=mod.db_auth_get_user(mod.AUTH_BOOTSTRAP_EMAIL); mod.db_auth_set_password(admin['id'],'SenhaAdmin123'); user=mod.db_auth_login(admin['email'],'SenhaAdmin123')
app=mod.App(current_user=user); app.update_idletasks(); app._show_users(); app.update_idletasks()
assert hasattr(app,'user_reset_requests_btn')
new=mod.db_auth_register_user('Joao Recuperacao','joao.recovery@example.com','SenhaJoao123'); mod.db_auth_set_status(new['id'],'active',user)
assert mod.db_auth_request_password_reset(new['email']) is True
app._refresh_users(); app.update_idletasks()
assert '(1)' in app.user_reset_requests_btn.cget('text')
assert app.user_summary_labels['reset'].cget('text')=='1'
app.destroy()
print('V137 password recovery UI: OK')
