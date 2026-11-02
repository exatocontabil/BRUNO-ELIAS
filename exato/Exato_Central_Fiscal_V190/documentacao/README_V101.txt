EXATO CENTRAL FISCAL — V101

Base: V100

Objetivo desta versão:
- corrigir o orquestrador da captura de NF-e para que o fluxo Emitente/Saída seja efetivamente executado quando o primeiro fluxo termina sem o status que exige espera;
- impedir que versões anteriores deixem um cooldown falso por conta de cStat diferente de 117;
- preservar a estrutura de salvamento XML + PDF + consolidado validada na V100.

IMPORTANTE:
- O corpo das funções protegidas da NF-e/Auditoria permanece preservado.
- O núcleo fiscal do Web Service não foi reescrito.
- A alteração está concentrada na camada de orquestração/controle do ciclo.
- O PDF individual e o PDF consolidado não foram alterados nesta versão.

TESTE RECOMENDADO NO AMBIENTE REAL:
1. Selecionar o mesmo CNPJ que apresenta NF-e de Entrada e Saída em agosto/2026.
2. Confirmar o período.
3. Executar BUSCAR XML.
4. Verificar no card NF-e as contagens Entrada e Saída.
5. Consultar o resultado detalhado e confirmar que documentos de Saída foram capturados quando disponíveis.

Atenção: se a SEF/SC retornar cStat=117, a Central respeitará a janela de segurança; a documentação oficial da SEF/SC registra que o intervalo é aplicado após atingir a sincronia nesse status. 
