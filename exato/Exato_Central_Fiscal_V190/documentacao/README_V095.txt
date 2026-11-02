EXATO CENTRAL FISCAL — V095

Base operacional: V094. Os núcleos funcionais protegidos de NF-e e Auditoria SAT × XML não foram alterados.

Evolução desta versão:
- Auditoria Fiscal agora permite abrir/gerar a representação fiscal diretamente pela própria tela.
- Botão contextual: VER/GERAR DANFE para NF-e e VER/GERAR DANFE NFC-e para NFC-e.
- Menu de contexto pelo botão direito na tabela da Auditoria.
- A ação resolve o documento original na base local usando chave de acesso e, como fallback, número/data/série.
- A geração continua usando o XML original armazenado na Central e reaproveita PDF já existente quando disponível.
- Linhas sem XML localizado permanecem sem ação de geração, evitando criação de representação sem fonte fiscal.

Preservação:
- Fluxos protegidos de NF-e e Auditoria SAT × XML não foram reescritos.
