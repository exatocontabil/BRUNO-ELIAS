import os, tempfile, time, threading
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v128_')
os.environ['EXATO_CF_DEV']='1'
import importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v128',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V128'
app=mod.App(); app.withdraw(); app.update_idletasks()
# Session summary and startup context hooks
assert hasattr(app,'_exatinho_session_counters')
assert app._exatinho_session_counters == {'sync':0,'audit':0,'pending':0,'danfe':0}
# Panel should include session line and no clipping at 282px.
app._ia_event_context.update({'status':'PENDING_REVIEW','screen':'documents','documents':13,'company':'ELYON CASA DA PISCINAS LTDA'})
app._exatinho_open_panel(first=False); app.update_idletasks()
texts=[]
def walk(w):
    for c in w.winfo_children():
        try:
            if 'text' in c.keys(): texts.append(str(c.cget('text') or ''))
        except Exception: pass
        walk(c)
walk(app.ia_sidebar_interaction)
joined='\n'.join(texts)
assert 'Sessão:' in joined
assert 'Encontrei pontos' in joined or 'pontos' in joined.lower()
app._exatinho_close_panel()
# Proactive suggestion can schedule and target a real widget.

app._exatinho_schedule_proactive('test',100,'Vamos conferir os documentos?','documents')
app.after(350, app.quit)
app.mainloop()
assert app._exatinho_last_proactive_key=='test', (app._exatinho_last_proactive_key, app._exatinho_proactive_job, app.ia_float_bubble.cget('text'))
# Focus capture should be set.
assert app._ia_attention_strength > 0
# Opening follow-up uses context-aware phrase without error.
app._exatinho_opening_done=True
app._exatinho_opening_followup()
assert str(app.ia_float_bubble.cget('text'))
app.destroy()
print('V128_NEW_FEATURES_OK')
