from pathlib import Path
import os, tempfile, importlib.util, hashlib, ast, subprocess, sys
from decimal import Decimal

BASE=Path(__file__).resolve().parents[1]
SRC103=Path('/mnt/data/work_v110/base/Exato_Central_Fiscal_V109/exato_central_fiscal.py')
SRC=BASE/'exato_central_fiscal.py'

spec=importlib.util.spec_from_file_location('exato_v104',SRC)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V110'

# Multi-type result fixture.
def sub(fam, value, number):
    row={'status':'Conforme','numero':number,'data':'2026-08-05','modelo':mod.SUPPORTED_FAMILIES[fam],
         'valor_sat':Decimal(value),'valor_xml':Decimal(value),'observacao':'Dados conferem.','chave':'','serie':'1','direction':'saida'}
    return {'family':fam,'family_label':mod.SUPPORTED_FAMILIES[fam],'period_start':'2026-08-01','period_end':'2026-08-31',
            'sat_count':1,'xml_count':1,'sat_total':Decimal(value),'xml_total':Decimal(value),'matched_sat_total':Decimal(value),'matched_xml_total':Decimal(value),'count_difference':0,
            'matched':[({'numero':number,'valor':Decimal(value)}, {'numero':number,'valor':Decimal(value)})],'sat_only':[],'xml_only':[],
            'number_differences':[],'date_differences':[],'value_differences':[],'value_difference':Decimal('0.00'),'missing_sat_value':Decimal('0.00'),'xml_only_value':Decimal('0.00'),
            'sat_rows':[],'audit_rows':[row],'ai_analysis':None,'source_files':[f'{fam}.xlsx']}

nfe=sub('nfe','100.00','100'); nfce=sub('nfce','200.00','200')
for r in (nfe,nfce): r['ai_analysis']=mod.analyze_audit_result(r,'Empresa','2026-08-01','2026-08-31')
combined=mod._combine_audit_results({'nfe':nfe,'nfce':nfce},['nfe','nfce'],['nfe.xlsx','nfce.xlsx'],'2026-08-01','2026-08-31')
assert combined['family']=='multi' and combined['selected_families']==['nfe','nfce']

# Multi PDF has consolidated cover and independent sections.
with tempfile.TemporaryDirectory(prefix='v104_') as td:
    out=Path(td)/'multi.pdf'
    mod.generate_audit_pdf(combined,str(out),'Empresa Teste','23187104000152','2026-08-01','2026-08-31',['nfe.xlsx','nfce.xlsx'])
    assert out.exists() and out.stat().st_size>0
    from pypdf import PdfReader
    reader=PdfReader(str(out))
    assert len(reader.pages)>=3, len(reader.pages)
    text='\n'.join((p.extract_text() or '') for p in reader.pages)
    assert 'Auditoria Fiscal Consolidada' in text
    assert 'NF-e' in text and 'NFC-e' in text

# UI type filter semantics.
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='v104_ui_')
app=mod.App(); app.withdraw(); app._show_audit(); app.update_idletasks()
app.last_audit_result=combined
app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==2
app.audit_type_filter_var.set('NF-e'); app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==1 and app.audit_filtered_rows[0]['modelo']=='NF-e'
app.audit_type_filter_var.set('NFC-e'); app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==1 and app.audit_filtered_rows[0]['modelo']=='NFC-e'
app.audit_type_filter_var.set('Todos'); app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==2
# combine type + status + search remains independent.
app.audit_type_filter_var.set('NF-e'); app.audit_filter_var.set('Conforme'); app.audit_search_var.set('100'); app._audit_rebuild_table(); assert len(app.audit_filtered_rows)==1
app.destroy()

# Source-level protection: V103 protected cores must remain byte-for-byte equivalent.
protected=['_audit_build_rows','_audit_compare_pair','_audit_fallback_key','_audit_key','_audit_xml_rows','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','test_sef_nfe_webservice',
           'generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','generate_documents_pdf']
def func_hash(path,name):
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name:
            seg=ast.get_source_segment(Path(path).read_text(encoding='utf-8'),n)
            return hashlib.sha256(seg.encode('utf-8')).hexdigest()
    raise KeyError(name)
for name in protected:
    assert func_hash(SRC103,name)==func_hash(SRC,name), name
print('V110_AUDIT_MULTI_PDF_OK')
print('V110_AUDIT_TYPE_FILTER_OK')
print('V110_PROTECTED_CORES_OK')
