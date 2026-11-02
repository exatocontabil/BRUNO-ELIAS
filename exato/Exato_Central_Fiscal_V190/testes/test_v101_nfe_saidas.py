from datetime import datetime, timedelta
from pathlib import Path
import os, tempfile, importlib.util

BASE = Path(__file__).resolve().parents[1]

def load_app():
    td = tempfile.TemporaryDirectory()
    os.environ['EXATO_DATA_DIR'] = td.name
    spec = importlib.util.spec_from_file_location('exato_v101', BASE / 'exato_central_fiscal.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, td

mod, td = load_app()
try:
    cnpj='23187104000152'
    now=datetime.now()

    # Legacy stale cooldown from older versions must not block the opposite actor
    # when the last response was a normal/non-117 status.
    config={'nfe_sync_control': {
        cnpj: {
            'last_actor':'2', 'next_actor':'1', 'last_cstat':'137',
            'cooldown_until':(now+timedelta(hours=11)).isoformat(timespec='seconds'),
            'cooldown_hours':12,
        }
    }}
    remaining, _ = mod.nfe_cooldown_remaining(config, cnpj, now=now)
    assert remaining == 0, remaining

    # A real cStat=117 wait remains protected.
    config={'nfe_sync_control': {
        cnpj: {
            'last_actor':'2', 'next_actor':'1', 'last_cstat':'117',
            'cooldown_until':(now+timedelta(hours=11)).isoformat(timespec='seconds'),
            'cooldown_hours':12,
        }
    }}
    remaining, control = mod.nfe_cooldown_remaining(config, cnpj, now=now)
    assert 39500 <= remaining <= 40000, remaining
    assert control['next_actor']=='1'

    # Normal successful/empty responses can chain to the opposite actor in the same search.
    assert mod.nfe_can_chain_actor({'ok':True,'last_info':{'cstat':'137'}})
    assert mod.nfe_can_chain_actor({'ok':True,'last_info':{'cstat':'138'}})
    assert not mod.nfe_can_chain_actor({'ok':True,'last_info':{'cstat':'117'}})
    assert not mod.nfe_can_chain_actor({'ok':False,'last_info':{'cstat':'657'}})

    # Persisting a normal actor result must set the opposite actor as next and clear cooldown.
    config={}
    saved=mod.record_nfe_actor_result(config, cnpj, '2', '137', 'nenhum documento adicional disponível')
    assert saved['last_actor']=='2'
    assert saved['next_actor']=='1'
    assert saved['last_cstat']=='137'
    assert saved['cooldown_until']==''
    assert int(saved['cooldown_hours'])==0

    # Persisting 117 must establish the safety wait.
    config={}
    saved=mod.record_nfe_actor_result(config, cnpj, '2', '117', 'nenhum DF-e localizado para distribuição')
    assert saved['last_actor']=='2'
    assert saved['next_actor']=='1'
    assert saved['last_cstat']=='117'
    assert saved['cooldown_until']
    assert int(saved['cooldown_hours'])==mod.NFE_SYNC_COOLDOWN_HOURS

    print('V101_NFE_SAIDA_SCHEDULER_OK')
finally:
    td.cleanup()
