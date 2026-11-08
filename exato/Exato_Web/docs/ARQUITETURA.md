# Exato Web — arquitetura e segurança

## Decisões do escritório (08/11/2026)
- Tudo pelo site; acesso de fora do escritório por login; cerca de 3 usuários, cada um com o seu.
- Modelo do SIEG: certificados **A1** (todos são A1) guardados no site; o site busca sozinho, sem ninguém pedir.
- O site roda no **servidor do escritório**, aberto para a internet. Os XMLs ficam nesse servidor (banco + pasta do Repositório), como hoje.

## Peças
1. **Site** (`web/`): FastAPI + páginas HTML. Usa o código do Exato (`web.nucleo`) para banco, situação da busca, relatórios etc.
2. **Cofre** (`web/cofre.py`): A1 criptografado (AES-256-GCM); chave mestra protegida pelo DPAPI da conta que roda o site. Para consultar a SEFAZ, o certificado é colocado no repositório do Windows só durante a consulta (sem exportar a chave) e retirado em seguida.
3. **Segurança** (`web/seguranca.py`): sessão assinada, CSRF, limite de tentativas, TOTP obrigatório, cabeçalhos de segurança.
4. **Busca no servidor (`web/busca.py`, `web/agendador.py`)**: espelha a busca do programa instalado (NF-e, NFC-e, CT-e e NFS-e; pontos de continuação, espera da SEFAZ, causas explicadas) usando `Cofre.usar(cnpj)`; rodada a cada 4 h, sob pedido e por empresa. A empresa usa o A1 próprio; sem ele, o A1 do escritório (procuração).

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

## Manifestação do destinatário (Ciência da Operação 210210)
`web/manifestacao.py`: NF-e de entrada que chegaram só como resumo (resNFe) recebem a Ciência no Ambiente Nacional (evento assinado RSA-SHA1 com o A1 do cofre, enviado com o certificado no repositório do Windows). Só quando alguém pede (caixa "Confirmo") ou se a empresa foi ligada de propósito (automático, desligado por padrão); limite de 50 por clique; para após 3 recusas ou falha de rede; nunca reenvia o que já foi registrado; histórico em `web.db`. Há chave de homologação na tela. Testado só com o Ambiente Nacional simulado (assinatura conferida): testar primeiro em homologação no servidor. Confirmação/desconhecimento/não realizada continuam decisão do contador.

## NFS-e no site
`web/nfse_conferencia.py` + tela "NFS-e": por empresa e período mostra prestadas x tomadas (autorizadas e canceladas separadas), ISS retido, ISS devido a outro município, cancelada sem o XML do cancelamento e numeração de prestadas faltando; "Gerar relatório mensal em PDF" usa o mesmo `generate_monthly_report_pdf` do programa instalado (`relatorios.pedir_nfse`, em segundo plano). Só lê o banco; nunca cria nota nem evento.
