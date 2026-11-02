from pathlib import Path
import os, tempfile, importlib.util
from decimal import Decimal
BASE=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='exato_v103_pdf_') as td:
    os.environ['EXATO_DATA_DIR']=td
    spec=importlib.util.spec_from_file_location('exato_v103_pdf',BASE/'exato_central_fiscal.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    def mk(fam,num,val):
        r={'status':'Conforme','numero':num,'data':'2026-08-05','modelo':mod.SUPPORTED_FAMILIES[fam],'valor_sat':Decimal(val),'valor_xml':Decimal(val),'observacao':'Dados conferem.','chave':'','serie':'1','direction':'saida'}
        return {'family':fam,'family_label':mod.SUPPORTED_FAMILIES[fam],'period_start':'2026-08-01','period_end':'2026-08-31','sat_count':1,'xml_count':1,'sat_total':Decimal(val),'xml_total':Decimal(val),'matched_sat_total':Decimal(val),'matched_xml_total':Decimal(val),'count_difference':0,'matched':[], 'sat_only':[], 'xml_only':[], 'number_differences':[], 'date_differences':[], 'value_differences':[], 'value_difference':Decimal('0.00'),'missing_sat_value':Decimal('0.00'),'xml_only_value':Decimal('0.00'),'sat_rows':[],'audit_rows':[r],'source_files':[fam+'.xlsx']}
    a=mk('nfe','100','100.00'); b=mk('nfce','200','200.00')
    a['ai_analysis']=mod.analyze_audit_result(a,'Empresa','2026-08-01','2026-08-31'); b['ai_analysis']=mod.analyze_audit_result(b,'Empresa','2026-08-01','2026-08-31')
    c=mod._combine_audit_results({'nfe':a,'nfce':b},['nfe','nfce'],['nfe.xlsx','nfce.xlsx'],'2026-08-01','2026-08-31')
    out=Path(td)/'audit_multi.pdf'
    mod.generate_audit_pdf(c,out,'Empresa','12345678000199','2026-08-01','2026-08-31',['nfe.xlsx','nfce.xlsx'])
    assert out.exists() and out.stat().st_size>1000
print('V103_MULTI_PDF_OK')
