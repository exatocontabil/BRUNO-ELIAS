EXATO CENTRAL FISCAL — V092

FOCO DA VERSÃO
- Evolução do Exato IA para uma camada contextual e conversacional baseada em evidências reais da auditoria.
- Perguntas em linguagem natural sobre status, valores, quantidade, comparação SAT x XML, divergências, XMLs pendentes, período, tipo/modelo, concentração por data, maior/menor movimentação e notas específicas.
- Análise geral contextual, com leitura de padrões, concentração, impacto financeiro, pontos prioritários e sinais objetivos fora do padrão.
- Memória curta da conversa durante a auditoria para perguntas de continuidade, como “e ela?”.
- Respostas mais úteis para perguntas abertas, sem depender somente de palavras-chave simples.
- Envio pelo botão PERGUNTAR e pela tecla Enter.
- Interface mostra claramente “Você” e “Exato IA” após uma pergunta.
- Tratamento de exceções da interação sem interromper ou alterar a auditoria.

ARQUITETURA
- ExatoIAEngine é uma camada independente e somente de leitura sobre o resultado já produzido pela Auditoria.
- O motor fiscal não é reescrito pela camada de IA.
- Criatividade fica restrita à linguagem; evidências permanecem vinculadas aos dados disponíveis.

PRESERVAÇÕES
- sync_documents_automatically() preservada.
- audit_sat_excel_against_xml() preservada.
- test_sef_nfe_webservice() preservada.
- Fluxos NF-e Emitente/Destinatário preservados.

SEGURANÇA DE INFORMAÇÃO
- A IA não inventa documentos, causas, irregularidades ou valores.
- A IA não altera documentos ou dados fiscais automaticamente.
- Perguntas abertas recebem respostas baseadas no universo de evidências carregado.

OBSERVAÇÃO
- Esta evolução é local e baseada no próprio resultado da auditoria; não depende de uma API externa de IA para responder.
