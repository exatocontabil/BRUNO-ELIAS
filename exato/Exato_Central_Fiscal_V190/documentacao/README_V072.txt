EXATO CENTRAL FISCAL — V072

Principais correções desta versão:
- SAT: autenticação reestruturada para usar diretamente o certificado selecionado do Windows na navegação para default.aspx, seguindo o fluxo manual comprovado: Login → default.aspx (302) → Apps.aspx (200).
- SAT: não utiliza CertificateAuth.ashx como mecanismo de sessão.
- SAT: a sessão criada com o certificado é validada também abrindo ConsultaOnlineCC.aspx antes de iniciar a consulta.
- SAT: cookies da sessão criada com o certificado são transferidos apenas para o navegador headless usado na consulta; nenhuma chave privada é exportada ou copiada.
- SAT: mantém Aplicações → 1. NFe/NFCe - Consulta.
- SAT: espera especificamente o POST/XHR real do botão Buscar antes de continuar.
- SAT: o detector de validação humana não trata o Cloudflare concluído com “Sucesso!” como erro.
- SAT: filtros de data passam a reconhecer os campos reais dtDataInicial/dtDataFinal observados no POST do portal.
- NF-e: preservados os dois fluxos independentes indAtor=1 (Emitente/Saída) e indAtor=2 (Destinatário/Entrada) da V071.
- Auditoria: mantém comparação SAT × XML por chave, com conferência de número, data e valor.
- Preservados NFC-e, CT-e, XMLs, banco, certificados, relatórios e identidade visual.

VALIDAÇÃO LOCAL
- compilação Python;
- teste sintético do detector de Cloudflare resolvido;
- teste do motor SAT × XML;
- verificação das rotinas NF-e indAtor=1/2;
- inspeção estática do fluxo Login → default.aspx → Apps.aspx → ConsultaOnlineCC.aspx.

A autenticação real no SAT precisa ser validada no Windows do usuário porque depende do certificado instalado e da sessão real do portal.
