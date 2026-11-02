from pathlib import Path
import re

SRC=Path(__file__).resolve().parents[1]/'exato_central_fiscal.py'
TEXT=SRC.read_text(encoding='utf-8')
assert 'APP_VERSION = "V109"' in TEXT
assert 'def _show_audit_from_documents(self):' in TEXT
assert 'self.audit_from.set(capture_from)' in TEXT
assert 'self.audit_to.set(capture_to)' in TEXT
assert "self.audit_selected_families=list(available)" in TEXT
assert 'def _find_reusable_audit_source_files' in TEXT
assert 'def _import_sat_excel_files(self, paths=None):' in TEXT
assert 'third_party' in TEXT
assert (SRC.parent/'third_party'/'pypdf').exists()
print('V109_CONTEXT_OK')
