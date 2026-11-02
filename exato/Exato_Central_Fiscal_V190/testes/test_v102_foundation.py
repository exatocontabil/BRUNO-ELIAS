from pathlib import Path
import ast, hashlib, tempfile, os, importlib.util, sqlite3

BASE=Path(__file__).resolve().parents[1]
V101=BASE.parent/'Exato_Central_Fiscal_V101/exato_central_fiscal.py'
CURRENT=BASE/'exato_central_fiscal.py'


def sha_func(path,name):
    text=path.read_text(encoding='utf-8')
    tree=ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node,ast.FunctionDef) and node.name==name:
            return hashlib.sha256(ast.get_source_segment(text,node).encode()).hexdigest()
    raise AssertionError(name)

protected=['_audit_build_rows','_audit_compare_pair','_audit_fallback_key','_audit_key','_audit_xml_rows','choose_nfe_actor','mark_nfe_sync_cycle','sync_documents_automatically','test_sef_nfe_webservice']
for name in protected:
    assert sha_func(V101,name)==sha_func(CURRENT,name),name

pdf_preserved=['generate_fiscal_representation_pdf','open_document_fiscal_representation','save_documents_organized','generate_documents_pdf']
for name in pdf_preserved:
    assert sha_func(V101,name)==sha_func(CURRENT,name),name

with tempfile.TemporaryDirectory(prefix='exato_v102_') as td:
    os.environ['EXATO_DATA_DIR']=td
    spec=importlib.util.spec_from_file_location('exato_v102',CURRENT)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    Path(td).mkdir(parents=True,exist_ok=True)
    mod.init_database()
    con=sqlite3.connect(mod.DB_PATH)
    names={row[1] for row in con.execute("PRAGMA index_list('documents')").fetchall()}
    for idx in ('idx_documents_access_key','idx_documents_number','idx_documents_company_scope','idx_documents_company_key'):
        assert idx in names,idx
    con.close()

src=CURRENT.read_text(encoding='utf-8')
for item in ("APP_VERSION = \"V102\"","<Control-k>","<Control-b>","<Control-Shift-a>","CENTRO DE PROCESSAMENTO","selectmode='extended'","COPIAR CHAVE(S)","Espaço livre"):
    assert item in src,item

print('V102_FOUNDATION_OK')
