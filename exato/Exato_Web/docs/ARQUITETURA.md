# Exato Web — arquitetura e segurança

## Decisões do escritório (08/11/2026)
- Tudo pelo site; acesso de fora do escritório por login; cerca de 3 usuários, cada um com o seu.
- Modelo do SIEG: certificados **A1** (todos são A1) guardados no site; o site busca sozinho, sem ninguém pedir.
- O site roda no **servidor do escritório**, aberto para a internet. Os XMLs ficam nesse servidor (banco + pasta do Repositório), como hoje.

## Peças
1. **Site** (`web/`): FastAPI + páginas HTML. Usa o código do Exato (`web.nucleo`) para banco, situação da busca, relatórios etc.
2. **Cofre** (`web/cofre.py`): A1 criptografado (AES-256-GCM); chave mestra protegida pelo DPAPI da conta que roda o site. Para consultar a SEFAZ, o certificado é colocado no repositório do Windows só durante a consulta (sem exportar a chave) e retirado em seguida.
3. **Segurança** (`web/seguranca.py`): sessão assinada, CSRF, limite de tentativas, TOTP obrigatório, cabeçalhos de segurança.
4. **Fase 2 (a fazer)**: agendador no servidor (rodada a cada 4 h, cliente novo, NFS-e por certificado e procuração), usando `Cofre.usar(cnpj)` + as rotinas atuais.

## Para abrir na internet (obrigatório)
- HTTPS na frente (ex.: Caddy ou IIS com certificado válido), repassando para `127.0.0.1:8443`. Nada de HTTP aberto.
- Firewall: só a porta 443 chega ao servidor; o resto fica fechado.
- Windows e Python atualizados; conta própria só para o site (sem administrador); disco com BitLocker.
- Cópia diária de `ExatoWebDados` para outro lugar (disco externo/outro computador).
- Usuários criados só pelo servidor (`python -m web.usuarios`); quem perder o celular: `zerar-2fa`.

## Riscos que a diretoria precisa conhecer
- O servidor passa a guardar os certificados A1 de todos os clientes e fica visível na internet: um alvo valioso. As defesas acima reduzem o risco, mas quem conseguir controle do servidor consegue usar os certificados.
- Se a internet ou a luz do escritório cair, o site sai do ar.
- Notas de NFS-e por portal com usuário e senha (captcha) não podem ser automáticas no servidor; só por certificado.

## Não testado ainda
- `ImportadorWindows` (colocar o A1 no repositório do Windows e retirá-lo) foi escrito mas só roda no Windows: testar no servidor antes de qualquer busca real.
