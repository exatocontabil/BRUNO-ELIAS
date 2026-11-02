import ast, hashlib, shutil, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NAMES=['_audit_build_rows','_audit_compare_pair','_audit_fallback_key','_audit_key','_audit_xml_rows','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','test_sef_nfe_webservice','generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','generate_documents_pdf']
def hashes(path):
    tree=ast.parse(path.read_text(encoding='utf-8')); found={}
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in NAMES:
            found[node.name]=hashlib.sha256(ast.dump(node,annotate_fields=True,include_attributes=False).encode()).hexdigest()
    return found
base_file=ROOT/'..'/'Exato_Central_Fiscal_V140'/'exato_central_fiscal.py'
# The V140 source is supplied next to the V141 folder in the assembled test package when run from the release workspace.
if not base_file.exists():
    raise SystemExit('V140 reference source not present beside V141; run the release regression script before packaging.')
a,b=hashes(base_file),hashes(ROOT/'exato_central_fiscal.py')
assert all(a.get(n)==b.get(n) for n in NAMES), {n:(a.get(n),b.get(n)) for n in NAMES if a.get(n)!=b.get(n)}
asset_old=base_file.parent/'assets'; asset_new=ROOT/'assets'
old_names=sorted(p.name for p in asset_old.iterdir() if p.is_file()); new_names=sorted(p.name for p in asset_new.iterdir() if p.is_file())
assert old_names==new_names
assert all(hashlib.sha256((asset_old/n).read_bytes()).digest()==hashlib.sha256((asset_new/n).read_bytes()).digest() for n in old_names)
print('V141 protection: 13/13 nuclei SAME; 31/31 assets SAME')
