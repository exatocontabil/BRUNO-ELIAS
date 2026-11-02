from pathlib import Path
import importlib.util, tempfile, ast, hashlib, os, sys
from decimal import Decimal
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('exato_v112', BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V112'

# New live IA interaction hooks.
for token in ["<Motion>", "_ia_float_on_mouse_move", "_ia_float_idle_phrase", "look_left", "look_right"]:
    assert token in (BASE/'exato_central_fiscal.py').read_text(encoding='utf-8')

# Transparent look variants are valid RGBA assets.
from PIL import Image
for name in ['exato_ia_look_left.png','exato_ia_look_center.png','exato_ia_look_right.png']:
    im=Image.open(BASE/'assets'/name).convert('RGBA')
    assert im.size==(1201,1309), name
    assert im.getchannel('A').getextrema()[0]==0, name

# Multi-type PDF regression fixture.
def make_sub(fam, sat_n, xml_n, sat_total, xml_total, start_num):
    rows=[]; matched=[]
    for i in range(min(sat_n,xml_n)):
        n=str(start_num+i); val=(Decimal(sat_total)/Decimal(sat_n)).quantize(Decimal('0.01'))
        row={'status':'Conforme','numero':n,'data':'2026-08-05','modelo':mod.SUPPORTED_FAMILIES[fam], 'valor_sat':val,'valor_xml':val,'observacao':'Dados conferem.','serie':'1','direction':'saida'}
        rows.append(row); matched.append(({'numero':n,'valor':val},{'numero':n,'valor':val}))
    xml_only=[]
    if xml_n>sat_n:
        xml_only=[{'numero':str(start_num+sat_n),'data':'2026-08-31','modelo':mod.SUPPORTED_FAMILIES[fam],'valor':Decimal(xml_total)-sum((r['valor_xml'] for r in rows),Decimal('0.00'))}]
    res={'family':fam,'family_label':mod.SUPPORTED_FAMILIES[fam],'period_start':'2026-08-01','period_end':'2026-08-31',
         'sat_count':sat_n,'xml_count':xml_n,'sat_total':Decimal(sat_total),'xml_total':Decimal(xml_total),'matched_sat_total':sum((r['valor_sat'] for r in rows),Decimal('0.00')),'matched_xml_total':sum((r['valor_xml'] for r in rows),Decimal('0.00')),'count_difference':sat_n-xml_n,
         'matched':matched,'sat_only':[],'xml_only':xml_only,'number_differences':[],'date_differences':[],'value_differences':[],'value_difference':Decimal('0.00'),'missing_sat_value':Decimal('0.00'),'xml_only_value':sum((x['valor'] for x in xml_only),Decimal('0.00')),'sat_rows':[],'audit_rows':rows,'source_files':[fam+'.xlsx']}
    res['ai_analysis']=mod.analyze_audit_result(res,'Empresa','2026-08-01','2026-08-31')
    return res
nfe=make_sub('nfe',53,54,'52236.00','53389.00',857)
nfce=make_sub('nfce',6,7,'1712.00','1712.01',367)
combined=mod._combine_audit_results({'nfe':nfe,'nfce':nfce},['nfe','nfce'],['nfe.xlsx','nfce.xlsx'],'2026-08-01','2026-08-31')
assert combined['ai_analysis']['status']=='atencao'
with tempfile.TemporaryDirectory(prefix='v112_') as td:
    out=Path(td)/'audit.pdf'
    mod.generate_audit_pdf(combined,out,'Elyon Casa da Piscina LTDA','49894842000123','2026-08-01','2026-08-31',['nfe.xlsx','nfce.xlsx'])
    sys.path.insert(0,str(BASE/'third_party'))
    from pypdf import PdfReader
    reader=PdfReader(str(out)); assert len(reader.pages)>=3
    text='\n'.join((p.extract_text() or '') for p in reader.pages)
    assert 'Auditoria Fiscal Consolidada' in text and 'NF-e' in text and 'NFC-e' in text
    assert 'ATENÇÃO' in text and 'SEM CORRESP.' in text
    # No speech-bubble text should be baked into the multi-type cover.
    assert 'Aqui tem informação que gera resultado!' not in (reader.pages[0].extract_text() or '')
    preview=Path('/mnt/data/work_v112/preview/V112_Auditoria_Preview.pdf'); preview.write_bytes(out.read_bytes())

# Protected core hashes from V111.
old=Path('/mnt/data/work_v111/Exato_Central_Fiscal_V111/exato_central_fiscal.py')
protected=['_audit_build_rows','_audit_compare_pair','_audit_fallback_key','_audit_key','_audit_xml_rows','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','test_sef_nfe_webservice','generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','generate_documents_pdf']
def func_hash(path,name):
    txt=path.read_text(encoding='utf-8'); tree=ast.parse(txt)
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name:
            return hashlib.sha256(ast.get_source_segment(txt,n).encode()).hexdigest()
    raise KeyError(name)
for n in protected:
    assert func_hash(old,n)==func_hash(BASE/'exato_central_fiscal.py',n), n
print('V112_NEW_INTERACTIONS_OK')
print('V112_AUDIT_PDF_OK')
print('V112_PROTECTED_CORES_OK')
