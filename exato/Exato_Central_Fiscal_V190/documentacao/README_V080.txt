EXATO CENTRAL FISCAL — V080

ORIGEM
V080 foi criada a partir da V079, após a investigação do fluxo real de autenticação do SAT e dos feedbacks do usuário.

AUDITORIA SAT × XML
- Leitura da identidade canônica do certificado diretamente do Windows usando o thumbprint previamente selecionado no Central.
- O filtro AutoSelectCertificateForUrls não usa mais o texto formatado exibido pela interface; usa CN/Subject/Issuer reais do certificado.
- Mantido o certificado selecionado como requisito absoluto; não selecionar outro silenciosamente.
- Primeiro caminho de automação: Edge em contexto persistente, minimizado, com política temporária AutoSelectCertificateForUrls quando possível.
- Segundo caminho: diálogo nativo de seleção de certificado do Windows, com automação para localizar e selecionar exatamente o certificado correspondente.
- Diagnóstico detalhado por tentativa em SAT_AUDITORIA/ (identidade do certificado, monitor do diálogo, tentativas de autenticação e log de consultas).
- Após autenticação, reprodução do fluxo manual: Apps.aspx → NFe/NFCe - Consulta → POST/XHR do botão Buscar.
- Consultas automáticas previstas para: NF-e Emitente, NF-e Destinatário, NFC-e Emitente e NFC-e Destinatário.
- Exportação automática dos resultados e consolidação/deduplicação antes da comparação SAT × XML.
- Motor de auditoria mantém comparação por chave, com conferência de número, data e valor e normalização de chave NFe+44 dígitos.
- Fallback HTTP direto permanece apenas como diagnóstico; não é tratado como prova de sessão autenticada do SAT.

NF-e / NFC-e / CT-e
- Preservado o fluxo NF-e Emitente: indAtor=1.
- Preservado o fluxo NF-e Destinatário: indAtor=2.
- Mantidos checkpoints independentes.
- NFC-e e CT-e preservados.
- Não alterar essas rotinas sem necessidade concreta.

LAYOUT — REFERÊNCIA APROVADA
- Cabeçalho escuro/preto com logo Exato, nome do sistema, versão e identificação do usuário/certificado.
- Sidebar esquerda escura com item ativo em vermelho.
- Área de conteúdo clara com cards e dashboard visual.
- Documentos Fiscais com cards de certificado/empresa, período, ações, indicadores NF-e/NFC-e/CT-e/Total, gráfico e resumo.
- Auditoria com indicadores SAT, XMLs, SAT sem XML, XML sem SAT e diferença.
- Cartão do certificado não exibe CNPJ/CPF.
- Cards superiores foram compactados para reduzir espaços vazios; seguir esse princípio nas demais abas.
- REFERENCIA_LAYOUT_OPCAO2.png acompanha o pacote como referência visual.

VALIDAÇÃO LOCAL
- py_compile: OK.
- Smoke test Tkinter: App, Documentos Fiscais, Auditoria e Histórico: OK.
- Verificação estrutural dos fluxos NF-e indAtor=1/2: OK.
- Verificação do pacote e arquivos de configuração: OK.

VALIDAÇÃO PENDENTE NO WINDOWS DO USUÁRIO
- Autenticação real no SAT com o certificado instalado.
- Chegada efetiva em Apps.aspx.
- Abertura de NFe/NFCe - Consulta.
- Execução real das quatro consultas e exportação.

IMPORTANTE
A V080 não substitui nem sobrescreve versões anteriores. Versões V071–V079 permanecem preservadas como histórico de testes.
