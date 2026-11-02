EXATO CENTRAL FISCAL — V076

OBJETIVO DA VERSÃO
Preservar as funcionalidades validadas e atacar os problemas reportados na Auditoria SAT, na NF-e e no layout.

AUDITORIA SAT × XML
- Corrigido o erro de execução "name 'ps' is not defined".
- O caminho principal agora tenta reproduzir o fluxo real comprovado no portal: Login → certificado → Apps.aspx → NFe/NFCe - Consulta.
- O navegador é invisível.
- O Edge recebe um filtro de certificado por SERIAL + Subject + Issuer, usando o certificado previamente selecionado no Central.
- O fluxo não exporta nem copia a chave privada.
- Se o caminho do navegador falhar, existe um caminho direto secundário apenas como fallback/diagnóstico.
- Após autenticar, a consulta executa o POST/XHR real do botão Buscar e exporta automaticamente os resultados, sem Excel manual.
- Mantida a comparação SAT × XML por chave, com conferência de número, data e valor.

NF-e
- Mantidos os dois fluxos independentes já validados:
  indAtor=1 → Emitente / Saída
  indAtor=2 → Destinatário / Entrada
- Após 117/137 no primeiro fluxo, o segundo não é mais abandonado; existe um pequeno intervalo antes da segunda consulta.
- Checkpoints independentes continuam preservados.
- NFC-e e CT-e não foram redesenhados nem substituídos.

CERTIFICADO
- O certificado selecionado no Central continua sendo a referência.
- Não há fallback para primeiro certificado.
- Na tela Documentos Fiscais, o cartão do certificado não exibe mais CNPJ/CPF do titular.

INTERFACE
- Novo padrão visual baseado na referência aprovada "Opção 2 — Com Dashboard Visual".
- Shell global, navegação, cartões, espaçamentos e principais telas de Documentos Fiscais e Auditoria foram modernizados.
- O padrão visual foi alinhado para ser aplicado de forma consistente nas demais abas.

PRESERVAÇÃO
- Banco, XMLs, empresas, checkpoints, certificados, relatórios, NFC-e, CT-e e identidade Exato preservados.

VALIDAÇÃO LOCAL
- py_compile: OK
- importação do módulo: OK
- GUI smoke test: OK
- construção de todas as telas: OK
- rotinas de auditoria presentes: OK
- filtro de certificado por serial: OK
- estrutura NF-e indAtor=1/2: OK

VALIDAÇÃO REAL NECESSÁRIA
- Rodar no Windows do usuário para validar o handshake real com o certificado selecionado e a sessão real do SAT.
