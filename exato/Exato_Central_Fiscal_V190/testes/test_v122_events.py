import os, tempfile, importlib.util
from pathlib import Path
import threading
import random

os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v122_events_')
os.environ['EXATO_CF_DEV']='1'
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v122events',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

assert mod.APP_VERSION=='V122'
assert 'Código do Órgão diverge do órgão autorizador' in mod.nfe_cstat_user_message('657','Rejeição: Código do Órgão diverge do órgão autorizador')
assert 'Consumo Indevido' in mod.nfe_cstat_user_message('656','Rejeição: Consumo Indevido')

class Dummy: pass
d=Dummy(); d._ia_event_lock=threading.Lock(); d._ia_event_queue=[]; d._ia_session_events=[]; d._ia_event_last_handled={}
d._ia_event_context={'screen':'','operation':'','company':'','family':'','documents':0,'new_documents':0,'status':'idle','last_error':'','last_cstat':'','last_result_at':0.0}
d._ia_live_rng=random.Random(4); d._ia_live_reaction_until=0; d._ia_live_motion_energy=1.0
calls=[]
d._ia_float_set_state=lambda *args,**kwargs:calls.append(args)
d._ia_behavior_transition=lambda *args,**kwargs:calls.append(('behavior',)+args)
for n in ('_ia_emit_event','_ia_process_event_queue','_ia_apply_event','_ia_event_phrase','_ia_last_significant_event','_ia_capture_focus'):
    setattr(Dummy,n,getattr(mod.App,n))

d._ia_emit_event('SYNC_SUCCESS',family='nfe',documents=71,new_documents=10)
d._ia_process_event_queue()
assert d._ia_event_context['documents']==71 and d._ia_event_context['new_documents']==10
assert any('documento' in str(c[1]).lower() for c in calls if isinstance(c,tuple) and len(c)>1 and c[0] != 'behavior')

d._ia_emit_event('SYNC_ERROR',family='nfe',cstat='657',error='teste')
d._ia_process_event_queue()
assert d._ia_event_context['last_cstat']=='657'
assert any('cStat 657' in str(c) for c in calls)

print('V122_EVENT_AND_CSTAT_TEST_OK')

# Session attention/focus regression.
d._ia_attention_target=None; d._ia_attention_strength=0.0
d._ia_capture_focus(120.0,220.0,0.95)
assert d._ia_attention_target==(120.0,220.0)
assert d._ia_attention_strength>0.9
print('V122_SESSION_ATTENTION_OK')

# Local diagnostic helper must not require a network request.
info=mod._nfe_runtime_diagnostic_summary('00000000000000')
assert info['last_cstat']=='—'
assert 'não executa' not in info.get('last_cstat_message','').lower()
print('V122_LOCAL_NFE_DIAGNOSTIC_OK')
