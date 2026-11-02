from pathlib import Path
import ast, hashlib, importlib.util
BASE=Path(__file__).resolve().parents[1]
src=BASE/'exato_central_fiscal.py'; text=src.read_text(encoding='utf-8')
spec=importlib.util.spec_from_file_location('v110_palette',src)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION=='V110'
assert mod.BG=='#F8FAFC'
assert mod.DARK=='#0F172A'
assert mod.HEADER_BG=='#0F172A'
assert mod.RED=='#DC2626'
assert mod.GREEN=='#16A34A'
assert mod.ORANGE=='#D97706'
assert mod.BLUE=='#64748B'
assert mod.PURPLE=='#64748B'
assert mod.NFE_ACCENT==mod.RED and mod.NFCE_ACCENT==mod.RED and mod.CTE_ACCENT==mod.RED
# Deprecated decorative colors may remain inside frozen fiscal-renderer code only; no new UI palette should use them.
ui_text=text
for _name in ['generate_fiscal_representation_pdf','generate_documents_pdf']:
    import ast as _ast
    _tree=_ast.parse(ui_text)
    _node=next((n for n in _ast.walk(_tree) if isinstance(n,(_ast.FunctionDef,_ast.AsyncFunctionDef)) and n.name==_name),None)
    if _node:
        _src=_ast.get_source_segment(ui_text,_node) or ''
        ui_text=ui_text.replace(_src,'')
assert '#1D4ED8' not in ui_text and '#7C3AED' not in ui_text and '#EA580C' not in ui_text

def fhash(path,name):
    t=path.read_text(encoding='utf-8'); tree=ast.parse(t)
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name:
            return hashlib.sha256(ast.get_source_segment(t,n).encode()).hexdigest()
    raise KeyError(name)
protected=['_audit_build_rows','_audit_compare_pair','_audit_fallback_key','_audit_key','_audit_xml_rows','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','test_sef_nfe_webservice','generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','generate_documents_pdf']
prev=Path('/mnt/data/work_v110/base/Exato_Central_Fiscal_V109/exato_central_fiscal.py')
for n in protected:
    assert fhash(prev,n)==fhash(src,n), n
print('V110_PALETTE_OK')
print('V110_PROTECTED_CORES_OK')
