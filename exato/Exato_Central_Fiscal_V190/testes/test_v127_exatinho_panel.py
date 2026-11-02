"""V127 — regression test for Exatinho panel expansion / clipping prevention."""
import exato_central_fiscal as mod

app = mod.App()
app.geometry('1366x800+0+0')
app.deiconify()
app.update()

base = app.sidebar.winfo_width()
app._ia_event_context = {
    'status': 'PENDING_REVIEW',
    'screen': 'documents',
    'documents': 13,
    'company': 'ELYON CASA DA PISCINAS LTDA',
}
app._exatinho_open_panel(first=False)
app.update()
expanded = app.sidebar.winfo_width()
panel_width = app.ia_sidebar_interaction.winfo_width()
panel_req_width = app.ia_sidebar_interaction.winfo_reqwidth()

assert base == app._sidebar_base_width == 214, (base, app._sidebar_base_width)
assert expanded == app._sidebar_exatinho_width == 282, (expanded, app._sidebar_exatinho_width)
assert panel_width > 0
assert panel_req_width > 0

app._exatinho_close_panel()
app.update()
restored = app.sidebar.winfo_width()
assert restored == 214, restored
app.destroy()
print('V127_EXATINHO_PANEL_OK')
