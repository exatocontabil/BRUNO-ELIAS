# Exato Central Fiscal V116

Base: V115.

## Objetivo
Refinar o Relatório de Documentos Fiscais após a análise do PDF gerado pela V115, priorizando composição, legibilidade, aproveitamento de espaço e segurança de enquadramento.

## Melhorias do PDF
- distribuição das linhas das tabelas baseada na altura real do conteúdo;
- redução de textos do EXATO IA para evitar cards excessivamente densos;
- composição do EXATO IA — ENTRADA com conteúdo mais curto e melhor equilíbrio entre texto, tabela e mascote;
- composição do EXATO IA — SAÍDA preservada na última página da seção, com texto reduzido;
- mensagens dos cards mantidas dentro das próprias áreas, sem overflow;
- pontos de atenção sem repetição automática de texto idêntico;
- paginação física permanece coerente;
- cenário equivalente ao relatório analisado permanece em 6 páginas.

## Preservação
A camada fiscal permanece preservada. Não houve alteração em Auditoria SAT × XML, captura NF-e/NFC-e/CT-e, fluxos Emitente/Destinatário, geração de DANFE/DACTE ou salvamento organizado de documentos.

A única função protegida alterada nesta versão é `generate_documents_pdf`, exclusivamente para composição e paginação do relatório.
