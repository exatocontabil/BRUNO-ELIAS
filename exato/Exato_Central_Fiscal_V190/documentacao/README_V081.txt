EXATO CENTRAL FISCAL — V081

OBJETIVO
- Evoluir a Auditoria SAT × XML sem abrir navegador.
- Usar exatamente o certificado previamente selecionado no Central Fiscal pelo thumbprint do Windows.
- Permitir cancelamento seguro da auditoria.
- Refinar o layout aprovado com cabeçalho escuro, sidebar escura, cards compactos e dashboard visual.

AUDITORIA SEM NAVEGADOR
- curl.exe com Schannel usa o certificado do Windows por CurrentUser\\MY\\<thumbprint>.
- Sessão HTTP mantém cookies e segue redirecionamentos somente no domínio do SAT.
- Tenta Login → default.aspx → Apps.aspx e, se necessário, CertificateAuth → Apps.aspx.
- ConsultaOnlineCC.aspx é acessada na mesma sessão.
- O POST real do ASP.NET Web Forms é reproduzido com ViewState/EventValidation e os campos capturados do formulário.
- São feitas quatro consultas: NF-e Emitente, NF-e Destinatário, NFC-e Emitente, NFC-e Destinatário.
- Exportar é priorizado; há fallback de leitura da tabela HTML.
- Nenhum seletor de certificado é aberto e nenhuma chave privada/PFX é exportada.

CANCELAMENTO
- Novo botão CANCELAR AUDITORIA.
- Cancela a comunicação em andamento e restaura a interface.

PRESERVAÇÃO
- NF-e: indAtor=1 Emitente e indAtor=2 Destinatário com checkpoints independentes.
- NFC-e e CT-e preservados.
- Banco, XMLs, relatórios, histórico e certificados preservados.

LAYOUT
- Cabeçalho escuro/preto e sidebar escura.
- Logo reduzida ao símbolo Exato no cabeçalho.
- Cards superiores compactos, especialmente Certificado Digital e Empresa.
- Dashboard visual baseado na referência aprovada.
- CNPJ/CPF abaixo do certificado permanece oculto.
- Referências visuais incluídas no pacote.
