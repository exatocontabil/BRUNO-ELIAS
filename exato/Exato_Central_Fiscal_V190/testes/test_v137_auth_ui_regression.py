from __future__ import annotations
import os,sys,tempfile
from pathlib import Path
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v137_ui_')
os.environ['EXATO_CF_DEV']='1'
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import exato_central_fiscal as mod
mod.messagebox.showinfo=lambda *a,**k: None
mod.messagebox.showwarning=lambda *a,**k: None
mod.messagebox.showerror=lambda *a,**k: (_ for _ in ()).throw(AssertionError(f'error: {a}'))
mod.messagebox.askyesno=lambda *a,**k: True
mod.init_database()
login=mod.LoginWindow(); login.update_idletasks()
assert login.email.get()==mod.AUTH_BOOTSTRAP_EMAIL
login.destroy()
admin=mod.db_auth_get_user(mod.AUTH_BOOTSTRAP_EMAIL); mod.db_auth_set_password(admin['id'],'SenhaAdmin123'); user=mod.db_auth_login(admin['email'],'SenhaAdmin123')
app=mod.App(current_user=user); app.update_idletasks()
assert app.current_user['email']==admin['email']; assert 'Administrador' in app.header_identity.cget('text'); assert hasattr(app,'nav_users')
app._show_users(); app.update_idletasks(); assert hasattr(app,'users_tree') and len(app.users_tree.get_children())==1
new=mod.db_auth_register_user('Maria Teste','maria@example.com','SenhaMaria123'); app._refresh_users(); app.update_idletasks(); assert len(app.users_tree.get_children())==2
pending=[iid for iid in app.users_tree.get_children() if app.users_tree.item(iid,'values')[2]=='maria@example.com'][0]
app.users_tree.selection_set(pending); app.users_tree.focus(pending); app.event_generate('<<TreeviewSelect>>'); app.update_idletasks(); app._on_user_selection(); assert 'disabled' not in app.user_approve_btn.state()
mod.db_auth_set_status(new['id'],'active',user); assert mod.db_auth_login('maria@example.com','SenhaMaria123')['email']=='maria@example.com'
app.destroy(); print('V137 auth UI: OK')
