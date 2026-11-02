EXATO CENTRAL FISCAL — V069

Objetivos desta versão:
- reforçar a captura de NF-e usando o fluxo combinado oficial indAtor=9 da distribuição contabilista da SEF/SC;
- preservar checkpoints antigos, evitando saltos e permitindo recuperação segura sem perder documentos;
- evitar a sequência indevida de chamadas actor=1/actor=2 que já produziu cStat 117 seguido de 657;
- manter a captura automática lote a lote até o ponto disponível;
- avançar o diagnóstico da Auditoria SAT com NetLog do Edge, além do fluxo CertificateAuth.ashx já identificado;
- preservar as correções de layout e rolagem.

Observação:
O certificado continua sendo utilizado diretamente pelo Windows, sem exportação da chave privada.
