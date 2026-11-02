EXATO CENTRAL FISCAL — V082

Objetivo desta versão
---------------------
A V082 muda a Auditoria SAT × XML para um modo manual estável baseado no Excel oficial exportado pelo SAT. A captura automática via navegador/portal não é mais necessária para executar a auditoria nesta versão.

Fluxo da Auditoria
-------------------
1. Usuário acessa o SAT manualmente.
2. Faz as consultas necessárias (emitente/destinatário e NF-e/NFC-e conforme o período).
3. Exporta o(s) Excel(s) oficial(is) do SAT.
4. No Exato Central Fiscal, clica em "IMPORTAR EXCEL DO SAT".
5. Pode selecionar um ou mais arquivos XLSX de uma vez.
6. O sistema lê somente os campos relevantes e compara com os XMLs armazenados.
7. O resultado mostra:
   - documentos SAT;
   - XMLs analisados;
   - SAT sem XML;
   - XML sem SAT;
   - diferença financeira;
   - divergências de número, data e valor.
8. Após uma comparação concluída, o botão "GERAR PDF" fica disponível.

PDF da Auditoria
----------------
O PDF é específico da conciliação SAT × XML e utiliza o padrão visual dos relatórios Exato:
- cabeçalho Exato;
- empresa, CNPJ e período;
- cards-resumo;
- valor SAT x valor XML;
- diferença financeira;
- SAT sem XML;
- XML sem SAT;
- divergências de valor;
- divergências de número;
- divergências de data;
- arquivos SAT utilizados.

Cancelamento
------------
O botão "CANCELAR AUDITORIA" permanece disponível durante a leitura/comparação para interromper a operação com segurança.

Preservação de funcionalidades
------------------------------
A V082 não altera os blocos validados de captura NF-e/NFC-e/CT-e. As funções de Web Service NF-e, sincronização automática e parsing SEF/SC foram preservadas integralmente em relação à V081.

Regra importante
----------------
A seleção de certificado do Central continua sendo a seleção oficial do sistema. O cartão de certificado da tela Documentos Fiscais não exibe mais o CNPJ/CPF do certificado.

Layout
------
Mantido o padrão visual aprovado da Central e compactados os quadros superiores. A referência visual aprovada da Opção 2/Opção 4 permanece no pacote.
