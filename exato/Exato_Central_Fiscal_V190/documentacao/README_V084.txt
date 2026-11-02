EXATO CENTRAL FISCAL — V084

Base
----
V084 foi criada a partir da V083, preservando a V082 como referência de segurança.

Correções desta versão
----------------------
1. Auditoria Fiscal — estabilidade
   - proteção contra exceções ocorridas na etapa de apresentação do resultado na interface;
   - a auditoria não deve permanecer indefinidamente em estado de processamento se a renderização final falhar;
   - registro do traceback em SAT_AUDITORIA/ULTIMO_ERRO_AUDITORIA_UI.txt quando houver falha de apresentação.

2. Auditoria Fiscal — desempenho
   - leitura dos metadados já persistidos no banco antes de reprocessar o XML;
   - parsing do XML somente quando faltar informação necessária;
   - quando o Excel contém uma única família documental, a consulta ao banco fica restrita àquela família;
   - redução de trabalho redundante antes da conciliação.

3. Auditoria Fiscal — progresso
   - indicação explícita das etapas: leitura do Excel, conferência SAT × XML e montagem da análise do Exato IA.

4. NF-e — tratamento de resposta da SEF/SC
   - cStat 657 deixa de ser tratado como uma execução concluída sem documentos;
   - a captura registra a consulta como bloqueada/observada e apresenta o cStat e motivo no resultado;
   - os fluxos independentes Emitente (indAtor=1) e Destinatário (indAtor=2) permanecem intactos;
   - nenhum navegador ou seletor manual de certificado foi reintroduzido.

5. Interface de sincronização
   - quando aplicável, o card da NF-e passa a indicar “Sem novos documentos” ou “Bloqueado — cStat 657”, em vez de apresentar “Concluído” de forma enganosa.

Preservação
-----------
- V082 não é alterada.
- V083 permanece disponível como versão anterior.
- Captura NF-e/NFC-e/CT-e, NSU/checkpoints, organização de XML, certificado e identidade visual permanecem preservados.
- A Auditoria continua baseada em Excel oficial do SAT + XMLs armazenados na Central.
