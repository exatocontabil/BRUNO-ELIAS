EXATO CENTRAL FISCAL — V103

Objetivo desta versão
Implementar a primeira evolução da Auditoria Fiscal para permitir seleção múltipla de NF-e (modelo 55) e NFC-e (modelo 65), mantendo as conciliações internamente independentes por tipo.

Fluxo aprovado
1. Usuário seleciona um ou mais tipos documentais.
2. Importa um ou mais Excel(s) do SAT.
3. O sistema identifica o tipo de cada arquivo com segurança.
4. Arquivos são agrupados por tipo; múltiplos arquivos do mesmo tipo são consolidados e deduplicados.
5. Cada tipo é enviado separadamente ao motor audit_sat_excel_against_xml, preservando o núcleo de conciliação.
6. A interface apresenta um resultado consolidado, com métricas e IA baseadas nos subresultados.
7. Perguntas da Exato IA que citam explicitamente NF-e/NFC-e são encaminhadas ao subresultado correspondente.
8. O PDF da auditoria multi-tipo usa identificação "NF-e + NFC-e · Modelo 55 + 65" e pode ser gerado a partir do resultado consolidado.

Proteções
- Núcleos V085/V101 protegidos não foram alterados.
- Funções de salvamento/geração de PDF validadas permanecem sem alteração de corpo.
- O fluxo NF-e Entrada/Saída validado na V101 permanece sem alteração.

Testes V103
- V103_AUDIT_MULTITYPE_OK
- V103_MULTI_PDF_OK
- V103_UI_SMOKE_OK
- regressões V094–V101 e V100/V102 executadas quando compatíveis com a árvore do pacote.
