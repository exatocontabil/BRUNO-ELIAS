V120 — CENTRO OPERACIONAL

Base: V119

Foco autorizado:
- Centro Operacional no Dashboard, com visão ao vivo de processamento;
- Centro de Processamento já existente reforçado com estado operacional no Dashboard;
- Histórico de sincronizações com filtro, detalhes da operação e atalhos para abrir empresa/documentos;
- Ações em lote na tela Documentos Fiscais: selecionar todos, limpar seleção e gerar representações fiscais sem alterar os geradores protegidos;
- Pendências inteligentes com priorização de capturas e auditorias que merecem revisão;
- Exato IA conectado apenas às novas interações operacionais, sem alteração do motor comportamental protegido.

Preservação:
- Núcleos fiscais/auditoria/PDF protegidos permanecem sem alteração nesta versão.
- Nenhuma mudança de regra fiscal foi introduzida.

Validação executada:
- py_compile/compileall
- smoke test da interface
- navegação Dashboard / Documentos / Histórico / Pendências
- seleção múltipla e ações em lote
- comparação SHA-256 dos 13 núcleos protegidos
- inspeção do ZIP final
