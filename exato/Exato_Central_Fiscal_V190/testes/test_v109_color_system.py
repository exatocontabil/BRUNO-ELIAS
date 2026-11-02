from pathlib import Path
import ast, hashlib, importlib.util, re
BASE=Path(__file__).resolve().parents[1]
src=(BASE/'exato_central_fiscal.py').read_text(encoding='utf-8')
# Load module with no real data side effects.
spec=importlib.util.spec_from_file_location('v109_palette',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V109'
assert mod.NFE_ACCENT==mod.RED and mod.NFCE_ACCENT==mod.RED and mod.CTE_ACCENT==mod.RED
assert mod.BLUE=='#344054'
assert mod.PURPLE=='#475467'
assert mod.ORANGE=='#A15C00'
# Audit IA surface is intentionally neutral in the UI.
# Ensure the old decorative blue/purple type constants are no longer present in the main palette.
for old in ['NFE_ACCENT = "#2563EB"','NFCE_ACCENT = "#7C3AED"','CTE_ACCENT = "#EA580C"']:
    assert old not in src
# Protect all known validated functions from V108 changes.
def fhash(path,name):
    txt=path.read_text(encoding='utf-8'); tree=ast.parse(txt)
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name:
            return hashlib.sha256(ast.get_source_segment(txt,n).encode()).hexdigest()
    raise KeyError(name)
protected=['_audit_build_rows','_audit_compare_pair','_audit_fallback_key','_audit_key','_audit_xml_rows','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','test_sef_nfe_webservice','generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','generate_documents_pdf']
prev=Path('/mnt/data/work_v108/Exato_Central_Fiscal_V108/exato_central_fiscal.py')
for n in protected:
    assert fhash(prev,n)==fhash(BASE/'exato_central_fiscal.py',n), n
print('V109_COLOR_SYSTEM_OK')
print('V109_PROTECTED_CORES_OK')
