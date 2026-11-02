from pathlib import Path
import os, tempfile, importlib.util, ast, hashlib
from decimal import Decimal
from datetime import datetime, timedelta
BASE=Path('/mnt/data/work_v114/Exato_Central_Fiscal_V113')
os.environ['EXATO_CF_DEV']='1'
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v114_reg_')
spec=importlib.util.spec_from_file_location('v114', BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V114'

# NF-e scheduler regression
cnpj='23187104000152'; now=datetime.now()
config={'nfe_sync_control':{cnpj:{'last_actor':'2','next_actor':'1','last_cstat':'137','cooldown_until':(now+timedelta(hours=11)).isoformat(timespec='seconds'),'cooldown_hours':12}}}
remaining,_=mod.nfe_cooldown_remaining(config,cnpj,now=now); assert remaining==0
config={'nfe_sync_control':{cnpj:{'last_actor':'2','next_actor':'1','last_cstat':'117','cooldown_until':(now+timedelta(hours=11)).isoformat(timespec='seconds'),'cooldown_hours':12}}}
remaining,control=mod.nfe_cooldown_remaining(config,cnpj,now=now); assert 39500 <= remaining <= 40000; assert control['next_actor']=='1'
assert mod.nfe_can_chain_actor({'ok':True,'last_info':{'cstat':'137'}})
assert mod.nfe_can_chain_actor({'ok':True,'last_info':{'cstat':'138'}})
assert not mod.nfe_can_chain_actor({'ok':True,'last_info':{'cstat':'117'}})
config={}; saved=mod.record_nfe_actor_result(config,cnpj,'2','137','nenhum documento adicional disponível'); assert saved['next_actor']=='1' and saved['cooldown_until']==''
config={}; saved=mod.record_nfe_actor_result(config,cnpj,'2','117','nenhum DF-e localizado para distribuição'); assert saved['cooldown_until'] and int(saved['cooldown_hours'])==mod.NFE_SYNC_COOLDOWN_HOURS
print('V114_NFE_SCHEDULER_OK')

# Audit multi-type + PDF regression from V107/V109 fixtures

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
    res['ai_analysis']=mod.analyze_audit_result(res,'Empresa','2026-08-01','2026-08-31')
    return res
nfe=make_sub('nfe',53,54,'52236.00','53389.00',857); nfce=make_sub('nfce',6,7,'1712.00','1712.01',368)
assert nfe['ai_analysis']['status']=='atencao'; assert nfce['ai_analysis']['status']=='atencao'
combined=mod._combine_audit_results({'nfe':nfe,'nfce':nfce},['nfe','nfce'],['nfe.xlsx','nfce.xlsx'],'2026-08-01','2026-08-31')
assert combined['ai_analysis']['status']=='atencao'
with tempfile.TemporaryDirectory(prefix='v114_pdf_') as td:
    out=Path(td)/'multi.pdf'; mod.generate_audit_pdf(combined,out,'Empresa Teste','23187104000152','2026-08-01','2026-08-31',['nfe.xlsx','nfce.xlsx'])
    from pypdf import PdfReader
    r=PdfReader(str(out)); assert len(r.pages)>=3
    txt='\n'.join((p.extract_text() or '') for p in r.pages); assert 'AUDITORIA FISCAL' in txt and 'NF-e' in txt and 'NFC-e' in txt and 'ATENÇÃO' in txt
print('V114_AUDIT_MULTI_PDF_OK')

# IA audit question engine regression
ROWS=[
{'numero':'1005','data':'2026-08-03','valor_sat':Decimal('636.00'),'valor_xml':Decimal('636.00'),'status':'Conforme','differences':[]},
{'numero':'1006','data':'2026-08-03','valor_sat':Decimal('514.00'),'valor_xml':Decimal('514.00'),'status':'Conforme','differences':[]},
{'numero':'1009','data':'2026-08-05','valor_sat':Decimal('991.00'),'valor_xml':Decimal('981.00'),'status':'Divergência','differences':[{'kind':'valor','detail':'SAT R$ 991,00 × XML R$ 981,00 (-R$ 10,00)'}]},
{'numero':'1010','data':'2026-08-05','valor_sat':Decimal('313.50'),'valor_xml':None,'status':'XML não localizado','differences':[]},]
RESULT={'audit_rows':ROWS,'family':'nfce','period_start':'2026-08-01','period_end':'2026-08-31','matched_sat_total':Decimal('2141.00'),'matched_xml_total':Decimal('2131.00'),'value_difference':Decimal('10.00'),'value_differences':[{'difference':Decimal('10.00')}],'number_differences':[],'date_differences':[],'xml_only':[]}
history=[]
for q,e in [('Qual nota está sem XML?','nota 1010'),('Quais são as divergências?','nota 1009'),('Qual a maior diferença?','nota 1009'),('Qual o período?','01/08/2026 até 31/08/2026'),('Compare SAT e XML','R$ 2.141,00')]:
    a=mod.exato_ia_answer_question(q,RESULT,'Empresa Teste',history); assert e in a,(q,a); history.append({'question':q,'answer':a})
print('V114_EXATO_IA_ENGINE_OK')

# Structural protection vs V113 archive
old=Path('/mnt/data/work_compare_v113/Exato_Central_Fiscal_V113/exato_central_fiscal.py')
new=BASE/'exato_central_fiscal.py'
protected=['_audit_build_rows','_audit_compare_pair','_audit_fallback_key','_audit_key','_audit_xml_rows','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','test_sef_nfe_webservice','generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','generate_documents_pdf']
def fh(path,name):
    txt=Path(path).read_text(encoding='utf-8'); tree=ast.parse(txt)
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name:
            return hashlib.sha256(ast.get_source_segment(txt,n).encode()).hexdigest()
for name in protected: assert fh(old,name)==fh(new,name), name
print('V114_PROTECTED_CORES_13_13_OK')
