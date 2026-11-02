V100 — ORGANIZAÇÃO XML/PDF + INDICADORES DE ENTRADA/SAÍDA

Base: V099.
Autorização: continuidade explicitamente solicitada pelo usuário.

CORREÇÕES IMPLEMENTADAS
1. A estrutura de exportação permanece Empresa → Ano → Mês → Entrada/Saída → tipo documental.
2. O PDF fiscal individual permanece ao lado do XML correspondente.
3. Ao salvar com geração de PDFs ativada, cada pasta de Entrada/Saída + tipo também recebe um PDF consolidado contendo todos os XMLs já presentes naquela pasta, ordenados pelo renderizador fiscal.
4. Não são criadas pastas separadas de PDF no nível do mês.
5. Os cards de NF-e, NFC-e e CT-e mostram, em texto compacto, a quantidade de Entrada e Saída no período selecionado.
6. Os números principais dos cards passam a refletir o conjunto de documentos do período contextualizado na tela.

PRESERVAÇÃO
- Núcleo protegido de captura NF-e preservado.
- Núcleo protegido da Auditoria SAT × XML preservado.
- Abertura/geração de representação fiscal pela Auditoria preservada.

OBSERVAÇÃO
A regra de NF-e Emitente/Destinatário permanece intacta nesta versão; a V100 não altera o agendamento/cooldown do núcleo protegido. A identificação Entrada/Saída exibida nos cards usa os documentos efetivamente presentes no período.
