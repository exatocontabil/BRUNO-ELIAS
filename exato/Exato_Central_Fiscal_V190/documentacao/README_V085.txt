EXATO CENTRAL FISCAL — V085

BASE
----
V085 foi criada a partir da V084, preservando a V082 como referência de segurança e sem alterar retroativamente V082, V083 ou V084.

OBJETIVOS DESTA VERSÃO
----------------------
1. NF-e — corrigir o consumo sequencial inseguro dos fluxos independentes.
   - Mantidos os dois fluxos oficiais e independentes:
       Emitente       = indAtor=1
       Destinatário   = indAtor=2
   - O sistema não consulta mais os dois atores em sequência imediata para o mesmo CNPJ.
   - Cada ciclo de serviço executa apenas um dos dois fluxos e registra qual será o próximo.
   - Após uma resposta real da SEF/SC, a Central persiste um intervalo de segurança de 12 horas antes de nova consulta para o mesmo CNPJ.
   - O intervalo também é respeitado pela consulta diagnóstica NF-e e pela captura manual de próximo lote.
   - Se o usuário tentar consultar durante o intervalo, a Central não envia nova requisição e informa qual fluxo será executado depois.
   - O primeiro fluxo, na ausência de histórico anterior, prioriza Destinatário/Entrada para evitar repetir o cenário observado em V083/V084 em que Emitente retornava 117 e a consulta seguinte do Destinatário recebia 657.
   - Se já houver fontes locais de apenas um ator, o V085 prioriza o outro ator na migração.
   - Falhas de transporte sem cStat não geram artificialmente um bloqueio de 12 horas.
   - O estado do agendamento é persistido por CNPJ em nfe_sync_control.

2. Auditoria Fiscal — correção de travamento antes do worker.
   - Corrigido o uso incorreto do campo de período.
   - O contêiner de widgets de período não é mais tratado como Label.
   - Foi criado um Label específico para a indicação textual do período.
   - A importação do Excel agora atualiza esse Label sem gerar TclError.
   - Mantida a arquitetura da Auditoria SAT × XML, Exato IA, histórico e PDF.
   - Mantida a proteção de finalização/erro para evitar permanecer indefinidamente em estado de processamento.

3. Transparência da captura NF-e.
   - O card pode indicar que o próximo fluxo está aguardando o intervalo de segurança.
   - O resultado detalha o próximo fluxo e o tempo aproximado restante quando aplicável.
   - cStat 657 continua sendo tratado como bloqueio e nunca como captura concluída com zero documentos.

BASE TÉCNICA PRESERVADA
-----------------------
- V082 não foi alterada.
- V083 e V084 permanecem como histórico.
- NFC-e e CT-e permanecem no mesmo motor já validado.
- NSU e checkpoints continuam independentes por fluxo.
- Não foi reintroduzido navegador, seleção manual de certificado ou exportação de chave privada.
- A Auditoria continua baseada em Excel oficial do SAT + XMLs armazenados na Central.
- A tabela única e o Exato IA da V083/V084 permanecem.

REFERÊNCIA EXTERNA DO CONTROLE DE CONSUMO
------------------------------------------
A implementação do intervalo de 12 horas foi baseada no Correio Eletrônico Circular SEF/DIAT nº 14/2022, que determinou que, atingida a sincronia com status 117 (Nenhum DF-e localizado para distribuição), devem ser aguardadas 12 horas para uma nova tentativa.

VALIDAÇÃO TÉCNICA REALIZADA
---------------------------
- py_compile: OK.
- Importação do módulo V085: OK.
- Inicialização da aplicação em Xvfb: OK.
- Teste do scheduler NF-e: OK.
- Teste do payload SOAP com indAtor=1 e indAtor=2: OK.
- Teste de controle 117 → cooldown persistente → próximo ator: OK.
- Teste sintético da conciliação SAT × XML: OK.
- Teste sintético de XML não localizado: OK.
- Teste isolado da construção da tela da Auditoria: OK.
- Teste do campo de período: o Frame continua sendo o contêiner e o Label textual passa a ser atualizado separadamente, sem TclError.

OBSERVAÇÃO
----------
A validação final da captura NF-e depende de teste real contra o Web Service da SEF/SC em máquina Windows com o certificado real da empresa. A V085 evita novas requisições durante o intervalo de segurança para impedir a repetição do cStat 657.


V087: somente identidade visual do PDF e da aba Auditoria. Motores fiscais preservados.
