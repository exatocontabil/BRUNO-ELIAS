EXATO CENTRAL FISCAL — V076

OBJETIVO
Grande avanço técnico na Auditoria SAT × XML, preservando as rotinas fiscais já validadas.

AUDITORIA SAT
- Referência: fluxo real capturado manualmente: Login → certificado → default.aspx → Apps.aspx 200 → ConsultaOnlineCC.aspx 200 → POST/XHR do Buscar.
- A autenticação direta agora prioriza default.aspx com o certificado exato do Windows. CertificateAuth.ashx deixou de ser o mecanismo principal.
- Cookies são capturados com domínio, caminho e flags para possível transferência ao Edge, sem exportar chave privada.
- Fallback: Edge headless + AutoSelectCertificateForUrls, também iniciando por default.aspx.
- Consulta continua pela área Aplicações e pelo POST/XHR real do Buscar.

NF-e
- Preservados indAtor=1 (Emitente/Saída) e indAtor=2 (Destinatário/Entrada), sem alteração deliberada da arquitetura validada na V071/V075.

PRESERVAÇÃO
- NFC-e, CT-e, XML, banco, checkpoints, certificados, relatórios e identidade Exato preservados.

NOTA TÉCNICA
Playwright possui suporte a client certificates quando cert/key são fornecidos ao contexto, mas esse mecanismo não é usado porque o projeto exige o certificado instalado no Windows sem exportar/copiar a chave privada.
