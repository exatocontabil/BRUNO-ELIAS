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

## Buscar notas (manual)
Tela "Buscar notas": uma empresa, tipos escolhidos (NF-e, NFC-e, CT-e, NFS-e) e como começar: "só o que veio depois" (continua do ponto salvo) ou "refazer desde o começo" (com confirmação; ponto de partida 0). Usa a mesma rotina da rodada automática (`Motor.rodada(only, tipos, recomecar)`), uma busca por vez, com o andamento ao vivo e a situação da empresa embaixo.

## Andamento ao vivo e busca a partir de uma data
`Motor.andamento` guarda, por tipo de nota (NF-e, NFC-e, CT-e, NFS-e): estado (na fila, consultando, concluído, sem notas novas, aguardando a SEFAZ, não concluído, cancelada), consultas, notas recebidas e guardadas e a causa em português com o que fazer. A tela Buscar notas lê isso de `/busca/estado` (campo `andamento`, atualizado a cada 1,5 s) e mostra o resultado final em destaque. "A partir de uma data": recomeça no maior NSU de nota já guardada com data anterior a (data - 3 dias); "até" para quando o lote inteiro é mais novo que a data final; o ponto de continuação nunca volta e busca só até uma data não vale como "em dia até hoje". "Aguardando a janela" só aparece quando há espera de verdade; recusa da SEFAZ mostra a causa.

## Baixar XMLs em ZIP, eventos, PDF da nota e editar empresa
- `web/exportar.py` + tela "Baixar XMLs (ZIP)": por empresa, período livre (De/Até), tipos e movimentação, ou só as **notas novas de uma busca** (`desde`). Formatos: "organizado" (Tipo/Movimentação, com `Eventos` ao lado das notas) e "dominio" (um ZIP por mês, tipo e movimentação, XMLs e eventos soltos, tudo dentro de um ZIP). Os **eventos vêm pela chave da nota, em qualquer mês** (`core._zip_eventos`: só evento completo de nota cancelada, nunca o resumo); falta de evento é avisada (AVISOS.txt e tela), nunca inventada. Gerado em segundo plano, em lotes; ZIPs ficam 7 dias.
- Tela Buscar notas: opção "Gerar o ZIP das notas novas desta busca" e, no resultado, botões para baixar/ver as notas novas. Documentos: botão "Baixar ZIP deste filtro" e filtro `desde`.
- `web/fechamento_eventos.py`: o ZIP de eventos do Fechamento do mês passa a trazer o evento de cada nota cancelada (pela chave) e nunca o resumo (o Exato V190 usa a data do evento e inclui o resumo; a correção é feita aqui, sem alterar a V190).
- Documentos: coluna PDF (`/documentos/{id}/pdf`: DANFE/DACTE/NFS-e gerados na hora do XML guardado, sem gravar nada).
- Empresas: editar nome (`/empresas/editar`): CNPJ fixo; o nome das notas só é trocado com confirmação; o nome escolhido vale mais que o das notas (`nomes_manuais`, reaplicado depois de cada busca); a pasta do Repositório acompanha; registro de atividade.

## Exatinho (assistente local)
`web/exatinho.py` (cérebro, sem tela e sem IA externa), `web/exatinho_base.py` (base de conhecimento: tópicos de uso do sistema, em linguagem simples, com perguntas de exemplo conferidas por teste), `web/exatinho_log.py` (perguntas que ele não soube responder e "não ajudou", em `web.db`; o administrador vê em "Dúvidas do Exatinho"). Rotas: `/exatinho/resumo`, `/exatinho/perguntar`, `/exatinho/acao` (só buscas, só depois do "sim"; exige o cabeçalho X-CSRF), `/exatinho/feedback`, `/exatinho/duvidas` (admin). Tela: `static/exatinho.js` e `exatinho.css` (botão flutuante com o mascote, painel de conversa, Ctrl+J, claro/escuro, celular em tela cheia, acompanha a busca ao vivo e continua depois que a página recarrega).
Ele responde: quem ainda não buscou notas, por quê (causa em português da Situação da busca) e de quais tipos; situação de uma empresa; certificados que vencem e empresas sem A1; quantas notas (por tipo, período); canceladas sem evento; resumo do dia; abrir telas; levar ao formulário de ZIP; e dúvidas de uso. Pergunta fora da base: diz que não sabe e anota. **Todo recurso novo do site deve ganhar um tópico em `exatinho_base.py` (com exemplos).** Não há piloto automático (o servidor busca sozinho).
