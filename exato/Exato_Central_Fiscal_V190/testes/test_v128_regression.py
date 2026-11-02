import os, tempfile, ast, hashlib, re, time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v128_reg_')
os.environ['EXATO_CF_DEV']='1'
import importlib.util
spec=importlib.util.spec_from_file_location('v128reg',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V128'
assert 'Código do Órgão diverge do órgão autorizador' in mod.nfe_cstat_user_message('657','Rejeição: Código do Órgão diverge do órgão autorizador')
assert 'Consumo Indevido' in mod.nfe_cstat_user_message('656','Rejeição: Consumo Indevido')
app=mod.App(); app.deiconify(); app.update_idletasks()
# Health UI builds.
app._show_maintenance(); app.update_idletasks(); assert hasattr(app,'maint_health_labels') and len(app.maint_health_labels)==5
# Panel clipping guard at expanded width.
app._ia_event_context.update({'status':'PENDING_REVIEW','screen':'documents','documents':13,'company':'ELYON CASA DA PISCINAS LTDA'})
app._exatinho_open_panel(first=False); app.update_idletasks(); assert app.sidebar.winfo_width()==282; assert app.ia_sidebar_interaction.winfo_width()>0
# Protected source hashes against V127.
prot=(BASE/'documentacao/V127_PROTECAO_NUCLEOS_SHA256.txt').read_text(encoding='utf-8')
expected=dict(re.findall(r'^(\w+)\s+([0-9a-f]{64})\s+SAME$',prot,re.M))
src=(BASE/'exato_central_fiscal.py').read_text(encoding='utf-8'); tree=ast.parse(src)
for name,h in expected.items():
    node=next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    assert hashlib.sha256(ast.get_source_segment(src,node).encode()).hexdigest()==h,name
assert len(expected)==13
app._exatinho_close_panel(); app.destroy()
print('V128_REGRESSION_OK')
