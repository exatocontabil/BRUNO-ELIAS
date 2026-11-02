V105 — CONTEXTO DOCUMENTOS → AUDITORIA

- Auditoria aberta a partir de Documentos Fiscais herda empresa/CNPJ e o mesmo período.
- Tipos NF-e/NFC-e presentes no período são pré-selecionados.
- XMLs já armazenados continuam sendo a fonte local da conciliação.
- Excel SAT de uma auditoria automática anterior do mesmo CNPJ/período é reutilizado quando disponível; arquivos manuais continuam sob escolha explícita.
- pypdf foi controlado localmente em third_party para geração multi-tipo sem instalação manual.

V105 preserva os núcleos protegidos e o fluxo de PDF validado.
