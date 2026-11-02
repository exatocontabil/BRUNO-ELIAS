from pathlib import Path
import os, tempfile, importlib.util, ast, hashlib
from decimal import Decimal
from datetime import datetime, timedelta
from pypdf import PdfReader

BASE=Path(__file__).resolve().parents[1]
os.environ['EXATO_CF_DEV']='1'
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v117_reg_')
spec=importlib.util.spec_from_file_location('v117',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V117'

# NF-e scheduler regression preserved.
cnpj='23187104000152'; now=datetime.now()
config={'nfe_sync_control':{cnpj:{'last_actor':'2','next_actor':'1','last_cstat':'117','cooldown_until':(now+timedelta(hours=11)).isoformat(timespec='seconds'),'cooldown_hours':12}}}
remaining,control=mod.nfe_cooldown_remaining(config,cnpj,now=now); assert 39500 <= remaining <= 40000; assert control['next_actor']=='1'
assert mod.nfe_can_chain_actor({'ok':True,'last_info':{'cstat':'137'}})
assert not mod.nfe_can_chain_actor({'ok':True,'last_info':{'cstat':'117'}})
print('V117_NFE_REGRESSION_OK')

# Multi-type audit engine + audit PDF regression.
def make_sub(fam, sat_n, xml_n, sat_total, xml_total, start_num):
    rows=[]; matched=[]
    for i in range(min(sat_n,xml_n)):
        n=str(start_num+i); val=(Decimal(sat_total)/Decimal(sat_n)).quantize(Decimal('0.01'))
        row={'status':'Conforme','numero':n,'data':'2026-08-05','modelo':mod.SUPPORTED_FAMILIES[fam],'valor_sat':val,'valor_xml':val,'observacao':'Dados conferem.','serie':'1','direction':'saida'}
        rows.append(row); matched.append(({'numero':n,'valor':val},{'numero':n,'valor':val}))
    xml_only=[]
    if xml_n>sat_n:
        xml_only=[{'numero':str(start_num+sat_n),'data':'2026-08-31','modelo':mod.SUPPORTED_FAMILIES[fam],'valor':Decimal(xml_total)-sum((r['valor_xml'] for r in rows),Decimal('0.00'))}]
    res={'family':fam,'family_label':mod.SUPPORTED_FAMILIES[fam],'period_start':'2026-08-01','period_end':'2026-08-31','sat_count':sat_n,'xml_count':xml_n,'sat_total':Decimal(sat_total),'xml_total':Decimal(xml_total),'matched_sat_total':sum((r['valor_sat'] for r in rows),Decimal('0.00')),'matched_xml_total':sum((r['valor_xml'] for r in rows),Decimal('0.00')),'count_difference':sat_n-xml_n,'matched':matched,'sat_only':[],'xml_only':xml_only,'number_differences':[],'date_differences':[],'value_differences':[],'value_difference':Decimal('0.00'),'missing_sat_value':Decimal('0.00'),'xml_only_value':sum((x['valor'] for x in xml_only),Decimal('0.00')),'sat_rows':[],'audit_rows':rows,'source_files':[fam+'.xlsx']}
    res['ai_analysis']=mod.analyze_audit_result(res,'Empresa','2026-08-01','2026-08-31'); return res
nfe=make_sub('nfe',53,54,'52236.00','53389.00',857); nfce=make_sub('nfce',6,7,'1712.00','1712.01',368)
combined=mod._combine_audit_results({'nfe':nfe,'nfce':nfce},['nfe','nfce'],['nfe.xlsx','nfce.xlsx'],'2026-08-01','2026-08-31')
assert combined['ai_analysis']['status']=='atencao'
with tempfile.TemporaryDirectory(prefix='v117_audit_') as td:
    out=Path(td)/'audit.pdf'; mod.generate_audit_pdf(combined,out,'Empresa Teste','23187104000152','2026-08-01','2026-08-31',['nfe.xlsx','nfce.xlsx'])
    text='\n'.join((p.extract_text() or '') for p in PdfReader(str(out)).pages); assert 'AUDITORIA FISCAL' in text and 'NF-e' in text and 'NFC-e' in text and 'ATENÇÃO' in text
print('V117_AUDIT_REGRESSION_OK')

# Exato IA question engine regression.
rows=[{'numero':'1005','data':'2026-08-03','valor_sat':Decimal('636.00'),'valor_xml':Decimal('636.00'),'status':'Conforme','differences':[]},{'numero':'1009','data':'2026-08-05','valor_sat':Decimal('991.00'),'valor_xml':Decimal('981.00'),'status':'Divergência','differences':[{'kind':'valor','detail':'SAT R$ 991,00 × XML R$ 981,00 (-R$ 10,00)'}]},{'numero':'1010','data':'2026-08-05','valor_sat':Decimal('313.50'),'valor_xml':None,'status':'XML não localizado','differences':[]}]
result={'audit_rows':rows,'family':'nfce','period_start':'2026-08-01','period_end':'2026-08-31','matched_sat_total':Decimal('2141.00'),'matched_xml_total':Decimal('2131.00'),'value_difference':Decimal('10.00'),'value_differences':[{'difference':Decimal('10.00')}],'number_differences':[],'date_differences':[],'xml_only':[]}
for q,needle in [('Qual nota está sem XML?','nota 1010'),('Quais são as divergências?','nota 1009'),('Qual o período?','01/08/2026 até 31/08/2026')]:
    answer=mod.exato_ia_answer_question(q,result,'Empresa Teste',[]); assert needle in answer,(q,answer)
print('V117_IA_QA_REGRESSION_OK')

# Protected-core comparison against V116: all 12 non-report protected cores remain identical.
old_path=Path('/mnt/data/work_v117/Exato_Central_Fiscal_V116/exato_central_fiscal.py'); new_path=BASE/'exato_central_fiscal.py'
protected=['_audit_build_rows','_audit_compare_pair','_audit_fallback_key','_audit_key','_audit_xml_rows','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','test_sef_nfe_webservice','generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','generate_documents_pdf']
def fh(path,name):
    txt=Path(path).read_text(encoding='utf-8'); tree=ast.parse(txt)
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name:
            return hashlib.sha256(ast.get_source_segment(txt,n).encode()).hexdigest()
unchanged=[]; changed=[]
for name in protected:
    (unchanged if fh(old_path,name)==fh(new_path,name) else changed).append(name)
assert 'generate_documents_pdf' in changed and len(changed)==1, (unchanged,changed)
assert len(unchanged)==12
print('V117_PROTECTED_COMPARE_12_OF_13_OK')
