from pathlib import Path
import os, tempfile, importlib.util
from decimal import Decimal

BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v103_multi_') as td:
    os.environ['EXATO_DATA_DIR']=td
    os.environ['EXATO_CF_DEV']='1'
    spec=importlib.util.spec_from_file_location('exato_v103_multi',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

    def sub(fam, value, number):
        row={
            'status':'Conforme','numero':number,'data':'2026-08-05','modelo':mod.SUPPORTED_FAMILIES[fam],
            'valor_sat':Decimal(value),'valor_xml':Decimal(value),'observacao':'Dados conferem.','chave':'','serie':'1','direction':'saida'
        }
        return {
            'family':fam,'family_label':mod.SUPPORTED_FAMILIES[fam],
            'period_start':'2026-08-01','period_end':'2026-08-31',
            'sat_count':1,'xml_count':1,'sat_total':Decimal(value),'xml_total':Decimal(value),
            'matched_sat_total':Decimal(value),'matched_xml_total':Decimal(value),'count_difference':0,
            'matched':[({'numero':number,'valor':Decimal(value)}, {'numero':number,'valor':Decimal(value)})],
            'sat_only':[],'xml_only':[],'number_differences':[],'date_differences':[],'value_differences':[],
            'value_difference':Decimal('0.00'),'missing_sat_value':Decimal('0.00'),'xml_only_value':Decimal('0.00'),
            'sat_rows':[],'audit_rows':[row],
            'ai_analysis':None,'source_files':[f'{fam}.xlsx']
        }

    nfe=sub('nfe','100.00','100')
    nfce=sub('nfce','200.00','200')
    nfe['ai_analysis']=mod.analyze_audit_result(nfe,'Empresa','2026-08-01','2026-08-31')
    nfce['ai_analysis']=mod.analyze_audit_result(nfce,'Empresa','2026-08-01','2026-08-31')
    combined=mod._combine_audit_results({'nfe':nfe,'nfce':nfce},['nfe','nfce'],['nfe.xlsx','nfce.xlsx'],'2026-08-01','2026-08-31')
    assert combined['family']=='multi'
    assert combined['selected_families']==['nfe','nfce']
    assert combined['family_label']=='NF-e + NFC-e'
    assert combined['sat_count']==2 and combined['xml_count']==2
    assert combined['matched_sat_total']==Decimal('300.00')
    assert len(combined['audit_rows'])==2
    assert set(combined['subaudits'])=={'nfe','nfce'}
    assert combined['ai_analysis']['status']=='conforme'

    answer_nfe=mod.exato_ia_answer_question('Como ficou a NF-e?',combined,'Empresa',[])
    answer_nfce=mod.exato_ia_answer_question('E a NFC-e?',combined,'Empresa',[])
    assert 'NF-e' in answer_nfe or 'nota' in answer_nfe.casefold()
    assert 'NFC-e' in answer_nfce or 'nota' in answer_nfce.casefold()

    # UI selection: one click = single type; second click = consolidated selection.
    app=mod.App(); app.withdraw(); app._show_audit(); app.update_idletasks()
    app._audit_set_family('nfe'); assert app._audit_selected_families()==['nfe']; assert app.audit_family_var.get()=='nfe'
    app._audit_set_family('nfce'); assert app._audit_selected_families()==['nfe','nfce']; assert app.audit_family_var.get()=='multi'
    assert 'NF-e + NFC-e' in app.audit_context.cget('text') or 'NF-e + NFC-e' in app.audit_family_hint.cget('text')
    app._audit_set_family('nfe'); assert app._audit_selected_families()==['nfce']
    app._audit_set_family('nfce'); assert app._audit_selected_families()==[]
    app.destroy()

os.environ.pop('EXATO_CF_DEV',None)
print('V103_AUDIT_MULTITYPE_OK')
