EXATO CENTRAL FISCAL — V077

Principais pontos:
- Auditoria SAT: fluxo real Login -> Entrar com Certificado Digital -> Apps.aspx, usando Edge headed off-screen e AutoSelectCertificateForUrls com filtro apenas por SUBJECT/ISSUER (sem SERIAL).
- A janela do Edge é criada fora da área visível; o usuário não precisa interagir com o navegador.
- Consulta SAT segue pela área Aplicações e usa o POST/XHR real de ConsultaOnlineCC.aspx.
- NF-e preservada nos fluxos independentes indAtor=1 (Emitente) e indAtor=2 (Destinatário).
- Redesign visual aplicado ao shell da Central e Auditoria, aproximando o padrão Opção 2 - Dashboard Visual.
- CNPJ/CPF do certificado não é exibido no cartão de Documentos Fiscais.
- Nenhuma chave privada é exportada.
