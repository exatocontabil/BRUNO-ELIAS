EXATO CENTRAL FISCAL — V102

Base: V101
Objetivo desta versão:
- iniciar a grande evolução de desempenho, UX e operação aprovada pelo usuário;
- manter os fluxos fiscais validados e evoluir somente ao redor deles;
- preparar uma experiência mais orientada à rotina de escritório.

Evoluções implementadas nesta V102:
- versão interna atualizada para V102;
- SQLite com WAL + ajustes de concorrência e índices adicionais para chave, número e escopo CNPJ/tipo/direção/data;
- diagnóstico do sistema passou a verificar também espaço livre em disco;
- atalhos globais: Ctrl+K (Busca Global), Ctrl+B (Buscar XML), Ctrl+Shift+A (Auditoria Fiscal);
- Busca Global em janela própria, com número, chave, empresa e tipo documental e abertura da representação por duplo clique;
- tela Documentos Fiscais com seleção múltipla e cópia de várias chaves de acesso;
- Centro de Processamento na tela de Busca XML, com estado por família documental e destaque explícito de Entrada + Saída para NF-e;
- preparação da interface para distinguir operação em processamento, concluída e próximo fluxo.

PRESERVAÇÃO CRÍTICA:
- NF-e Entrada/Saída validada na V101 permanece protegida;
- Auditoria SAT × XML permanece protegida;
- salvamento XML + PDF individual + PDF consolidado permanece congelado nesta versão;
- geração de representação fiscal e relatório PDF não foram reescritos nesta etapa.

TESTE RECOMENDADO:
1. Executar BUSCAR XML em empresa que tenha NF-e de Entrada e Saída;
2. confirmar no card NF-e as contagens Entrada/Saída;
3. validar a Busca Global (Ctrl+K);
4. abrir Documentos Fiscais, selecionar mais de uma linha e copiar chaves;
5. executar Auditoria SAT × XML;
6. validar representação fiscal e salvamento XML + PDF.

Nota de arquitetura:
Esta é uma etapa de fundação. Novas melhorias visuais e de inteligência podem ser incorporadas em versões seguintes, sempre com regressão dos fluxos protegidos.
