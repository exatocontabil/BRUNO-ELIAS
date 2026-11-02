EXATO CENTRAL FISCAL — V068

Objetivo:
- aprofundar a autenticação do SAT;
- reproduzir diretamente o endpoint CertificateAuth.ashx observado no fluxo real;
- usar o certificado selecionado no Windows sem exportar a chave privada;
- manter a mesma sessão/cookies durante Login -> CertificateAuth -> redirects -> Consulta;
- registrar status, redirects e contagem de cookies para diagnóstico.

A captura NF-e e o layout da V067 foram preservados nesta versão.
