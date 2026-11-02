EXATO CENTRAL FISCAL — V071

Principais correções desta versão:
- SAT: inicia pelo Login oficial e aguarda Apps.aspx após a autenticação por certificado, reproduzindo o fluxo manual demonstrado.
- SAT: mantém o navegador invisível; CertificateAuth não é usado como atalho de sessão, apenas permanece como diagnóstico técnico.
- SAT: espera a conclusão real da autenticação e das consultas, evitando tratar lentidão do portal como falha imediata.
- SAT: mantém o fluxo Aplicações → 1. NFe/NFCe - Consulta antes das pesquisas.
- SAT: executa as consultas sem depender de Excel selecionado manualmente.
- NF-e: restaura os fluxos independentes indAtor=1 (Emitente/Saída) e indAtor=2 (Destinatário/Entrada), cada um com seu checkpoint.
- NF-e: migração segura dos cursores que foram semeados pelo antigo indAtor=9; a gravação local continua deduplicando XMLs repetidos.
- NF-e: evita a sequência imediata 117 → segundo fluxo que já produziu 657 em diagnóstico anterior.
- Auditoria: mantém comparação SAT × XML baseada em chave, com conferência de número, data e valor.
- Preservados NFC-e, CT-e, XMLs, banco, certificados, relatórios e identidade visual.

VALIDAÇÃO LOCAL
- compilação Python;
- teste do parser XLSX SAT;
- teste da conciliação SAT × XML;
- teste sintético de divergência de número/data/valor;
- verificação estática das duas chamadas NF-e (indAtor=1 e indAtor=2).

A autenticação automática SAT precisa ser validada no Windows real, porque o certificado selecionado reside no Windows e o portal exige esse fluxo de autenticação.
