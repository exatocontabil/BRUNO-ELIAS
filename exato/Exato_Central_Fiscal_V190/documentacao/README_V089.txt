EXATO CENTRAL FISCAL — V089

Base de desenvolvimento: V088.

OBJETIVO DESTA VERSÃO
- Preservar os núcleos fiscais validados e evoluir segurança de dados, manutenção, diagnóstico, painel inicial e apresentação visual.

ALTERAÇÕES
- Dados persistentes passam a ficar em pasta compartilhada do usuário, fora da pasta da versão, reduzindo risco de perda ao atualizar.
- Migração conservadora de central_fiscal.db, config.json e histórico para a pasta de dados quando ainda não existir conteúdo persistente.
- Backup automático de segurança ao iniciar uma versão nova e backup manual pela área Manutenção.
- Nova aba Manutenção e Segurança: diagnóstico, backup, pasta de dados e detecção de versões locais mais recentes.
- Dashboard inicial ampliado com resumo inteligente da operação e últimas atividades.
- Pendências passam a considerar também registros de auditoria além das execuções de captura.
- Padronização de empacotamento: cada versão é entregue em uma única pasta, com assets, documentação, testes e referências separados por finalidade.
- PDF da Auditoria Fiscal refinado: hierarquia tipográfica mais equilibrada, cores harmonizadas, status menos dominante, blocos uniformes, tabela em ordem crescente por número da nota e mascote Exato IA transparente/proporcional.
- Aba Auditoria visualmente alinhada ao padrão do PDF, sem alterar o motor de conciliação.

PRESERVAÇÃO CRÍTICA
- Não foram alterados os motores funcionais de Auditoria SAT × XML validados na V085.
- Não foram alterados os motores de busca/captura de NF-e validados na V085.
- NF-e Emitente (indAtor=1) e Destinatário (indAtor=2) permanecem independentes.
- Checkpoints, NSU e armazenamento fiscal permanecem preservados.

NOTA SOBRE ATUALIZAÇÃO
- O Centro de Atualização detecta versões mais novas já extraídas no mesmo diretório, mas não sobrescreve instalações automaticamente.
- O fluxo seguro recomendado é: backup → confirmar nova pasta → abrir nova versão → validar → manter a versão anterior disponível até a validação.
- Nenhuma chave privada de certificado é exportada no backup.
