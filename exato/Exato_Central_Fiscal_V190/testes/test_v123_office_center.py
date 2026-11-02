import os, tempfile, importlib.util
from pathlib import Path
os.environ['EXATO_DATA_DIR']=tempfile.mkdtemp(prefix='exato_v123_center_')
os.environ['EXATO_CF_DEV']='1'
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v123center',BASE/'exato_central_fiscal.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
app=mod.App(); app.withdraw(); app.update_idletasks()
app._show_dashboard(); app.update_idletasks(); app.update()
assert set(app.dash_ops_labels)=={'nfe','nfce','cte','next'}
assert app.dash_ops_state.cget('text') in ('Pronto','Pronto • 0 pendência(s)')
app._show_documents(); app.update_idletasks(); app.update()
assert hasattr(app,'doc_batch_rep_btn') and hasattr(app,'doc_select_all_btn')
# Synthetic row only to validate selection/batch UI state, without touching fiscal data.
row={'doc_type':'NF-e','number':'123','family':'nfe','cnpj':'49894842000123','company_name':'TESTE','direction':'Saída','issued_at':'2026-08-01','value':'100.00','status':'Autorizado','xml':b'<xml/>'}
app._doc_row_map={'doc_test':row}; app.doc_tree.insert('', 'end', iid='doc_test', values=('NF-e','123','TESTE','Saída','01/08/2026','R$ 100,00','Autorizado'))
app.doc_tree.selection_set('doc_test'); app._on_document_selection(); app.update_idletasks();
assert str(app.doc_batch_rep_btn.cget('state'))=='normal'
app._clear_document_selection(); assert str(app.doc_batch_rep_btn.cget('state'))=='disabled'
app._show_history(); app.update_idletasks(); app.update(); assert hasattr(app,'history_detail') and hasattr(app,'history_filter_cb')
app._show_pending(); app.update_idletasks(); app.update(); assert set(app.pending_summary_labels)=={'capture','audit','total'}
app.destroy()
print('V123_OFFICE_CENTER_OK')
