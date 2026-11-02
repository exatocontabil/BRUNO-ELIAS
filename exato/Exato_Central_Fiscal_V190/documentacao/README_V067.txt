EXATO CENTRAL FISCAL — V067

Objetivo desta versão
----------------------
Corrigir o caminho de captura de NF-e sem quebrar o comportamento validado das versões anteriores.

Principais correções
--------------------
1. Removido o resync forçado para NSU=0 que havia sido introduzido nas versões V065/V066 apenas por a base local estar vazia.
   A regra volta a preservar os checkpoints persistidos, como na V061.
2. Em instalação realmente nova, a primeira sincronização de NF-e usa uma solicitação combinada indAtor=9 (Emitente e Destinatário)
   a partir do NSU=0. Esse caminho evita a sequência incorreta V066: Emitente=117 seguido imediatamente por Destinatário=657.
3. Após o bootstrap combinado, os dois cursores independentes são semeados no NSU coberto e o fluxo volta a operar com Emitente=1 e Destinatário=2.
4. Se um fluxo existente retornar cStat de sincronização/limite (117, 137, 110 ou 657), o outro fluxo não é disparado imediatamente, evitando novo excesso de consultas.
5. Migração automática de continuidade: quando V067 é executada em uma pasta nova de uma mesma instalação, ela procura versões anteriores irmãs, mescla documentos/checkpoints/configuração e não substitui dados já existentes.

Auditoria SAT
-------------
Mantida a autenticação por certificado do Windows e o diagnóstico de TLS/sessão.
A V067 não declara a Auditoria SAT concluída; a sessão web continua sendo uma investigação separada.
A tentativa agora grava AUTENTICACAO_REDE.txt com método/status/URL das chamadas relacionadas ao login, sem cookies, credenciais ou material do certificado.

Layout
------
Mantida a rolagem vertical na área principal e o enquadramento corrigido das telas.
