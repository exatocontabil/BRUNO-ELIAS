EXATO CENTRAL FISCAL — V074

OBJETIVO
Preservar o comportamento validado da captura fiscal e eliminar a possibilidade de a atualização usar silenciosamente um certificado diferente daquele confirmado pelo usuário.

CORREÇÃO PRINCIPAL — CERTIFICADO PRESERVADO
- Ao iniciar/atualizar a lista de certificados, a seleção existente não é apagada.
- O sistema restaura automaticamente o certificado previamente confirmado, usando o THUMBPRINT salvo no config.json.
- O certificado restaurado é marcado na lista, habilitado para continuar e refletido no cabeçalho.
- Se o certificado salvo não estiver mais disponível no Windows, o sistema não escolhe outro automaticamente; informa que o certificado salvo não foi localizado.
- Não existe fallback para “primeiro certificado disponível”.
- A atualização grava um arquivo ULTIMO_CERTIFICADO_USADO.txt com nome, documento e thumbprint do certificado efetivamente usado.

NF-e
- Não altera a arquitetura validada da V071/V073: indAtor=1 Emitente/Saída e indAtor=2 Destinatário/Entrada.
- Não altera NFC-e, CT-e, banco, XMLs ou checkpoints.

AUDITORIA SAT
- Mantida a estrutura da V073 para a investigação da autenticação do SAT.
- A correção desta versão é de preservação/identidade do certificado para evitar que um certificado diferente seja usado entre testes.

VALIDAÇÃO
- compilação Python;
- importação;
- restauração por thumbprint;
- integridade dos blocos de NF-e;
- preservação das rotinas de auditoria SAT × XML.
