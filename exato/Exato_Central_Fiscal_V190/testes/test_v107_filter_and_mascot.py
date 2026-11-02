import os, importlib.util, tempfile
from pathlib import Path
from decimal import Decimal
BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_CF_DEV']='1'
with tempfile.TemporaryDirectory(prefix='exato_v107_filter_') as td:
    os.environ['EXATO_DATA_DIR']=td
    spec=importlib.util.spec_from_file_location('v107_filter', BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    result={
        'family':'multi','selected_families':['nfe','nfce'],
        'period_start':'2026-08-01','period_end':'2026-08-31',
        'sat_count':3,'xml_count':4,'sat_total':Decimal('300.00'),'xml_total':Decimal('450.00'),
        'matched_sat_total':Decimal('290.00'),'matched_xml_total':Decimal('290.00'),
        'audit_rows':[
            {'status':'Conforme','numero':'1','data':'2026-08-01','modelo':'NF-e','valor_sat':Decimal('100'),'valor_xml':Decimal('100'),'observacao':'ok'},
            {'status':'Divergência','numero':'2','data':'2026-08-02','modelo':'NF-e','valor_sat':Decimal('100'),'valor_xml':Decimal('90'),'observacao':'valor diferente'},
            {'status':'XML não localizado','numero':'3','data':'2026-08-03','modelo':'NFC-e','valor_sat':Decimal('100'),'valor_xml':None,'observacao':'sem xml'},
        ],
        'xml_only':[{'numero':'4','data':'2026-08-04','modelo':'NFC-e','valor':Decimal('150'),'chave':'','serie':'1'}],
        'subaudits':{}
    }
    result['display_rows']=mod._audit_display_rows(result)
    statuses=[r['display_status'] for r in result['display_rows']]
    assert statuses.count('Conforme')==1
    assert statuses.count('Divergência')==1
    assert statuses.count('Sem correspondência')==2
    app=mod.App(); app.withdraw(); app._show_audit(); app.update_idletasks()
    app.last_audit_result=result
    app.audit_filter_var.set('Divergência'); app.audit_type_filter_var.set('Todos'); app.audit_search_var.set(''); app.audit_page=0; app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==1
    app.audit_filter_var.set('Sem correspondência'); app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==2
    app.audit_filter_var.set('Atenção'); app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==0
    app.audit_filter_var.set('Todos'); app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==4
    # Mascot must use an RGBA transparent asset path.
    assert (BASE/'assets'/'exato_ia_transparente.png').exists()
    app._audit_refresh_mascot('atencao'); app.update_idletasks(); assert app.audit_mascot_img is not None
    app.destroy()
os.environ.pop('EXATO_DATA_DIR',None); os.environ.pop('EXATO_CF_DEV',None)
print('V107_FILTER_AND_MASCOT_OK')
