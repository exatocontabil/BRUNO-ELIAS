EXATO CENTRAL FISCAL — V070

OBJETIVO DA VERSÃO
Aproximar a Auditoria SAT × XML do fluxo real comprovado manualmente no SAT/SEF-SC, sem depender de Excel manual no produto final.

ALTERAÇÕES
1. Após a autenticação por certificado, a auditoria não navega mais diretamente para ConsultaOnlineCC.aspx. Ela exige a sequência observada manualmente: Login → Aplicações → 1. NFe / NFCe - Consulta. O link oficial da área Aplicações é acionado dentro da mesma sessão; se o portal abrir nova aba, ela é usada.
2. Corrigido o parser de ValorTotalNota do Excel SAT: números decimais do XLSX, como 635.36, não são mais confundidos com separadores de milhar. Textos brasileiros como 1.234,56 continuam suportados.
3. A comparação SAT × XML continua usando a chave de acesso como vínculo principal, mas a auditoria passa a registrar explicitamente divergências de número, data e valor.
4. O relatório da auditoria exibe somente as informações necessárias para a conferência (número, data e valor); a chave permanece interna para a conciliação.

PRESERVAÇÃO
NF-e, NFC-e, CT-e, certificados, histórico, relatórios e demais funções existentes foram mantidos a partir da V069.

VALIDAÇÃO LOCAL EXECUTADA
- compilação Python;
- leitura dos Excel reais de NF-e e NFC-e fornecidos pelo usuário;
- verificação do parsing de valores decimais;
- teste do motor de comparação com chaves reais dos arquivos fornecidos.

LIMITAÇÃO
A autenticação automática no SAT não pode ser considerada validada nesta máquina de desenvolvimento, pois depende do certificado instalado no Windows do usuário e da sessão real do portal SAT. Esta versão incorpora o fluxo manual comprovado no computador do usuário, mas a validação final da captura automática deve ocorrer no Windows do usuário com o certificado selecionado na Central.
