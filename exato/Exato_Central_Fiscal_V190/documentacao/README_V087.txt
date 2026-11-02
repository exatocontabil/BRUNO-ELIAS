EXATO CENTRAL FISCAL — V087

BASE
----
V087 deriva da V085, a última versão validada nos fluxos de Auditoria SAT × XML e captura/busca de NF-e. V086 foi mantida apenas como etapa visual não validada e não foi usada como base funcional.

OBJETIVO
--------
1. Aplicar ao PDF de Auditoria Fiscal o layout visual aprovado pelo usuário: cabeçalho preto/vermelho, cores vivas, KPI cards, banner de status, Exato IA, bloco de próxima etapa e tabela coesa.
2. Remover do PDF linguagem técnica desnecessária, campo Fonte, bloco de Principais Insights e listas de arquivos/fonte.
3. Dar um UP na aba Auditoria Fiscal da Central, alinhando sua linguagem visual ao novo PDF e retirando completamente o painel de insights.

PRESERVAÇÃO
-----------
- Não foi alterado o motor de conciliação SAT × XML.
- Não foi alterado o código de busca/captura de NF-e.
- V082, V083, V084 e V085 permanecem intactas.
- NFC-e, CT-e, checkpoints, NSU e demais fluxos fiscais permanecem preservados.

ALTERAÇÕES VISUAIS
------------------
- PDF com identidade Exato mais atual e viva.
- Cabeçalho escuro com destaque vermelho e data/hora do relatório.
- Identificação da empresa, CNPJ e período sem campo Fonte.
- KPI cards compactos e coloridos.
- Banner de status com mensagem contextual.
- Exato IA com mascote e callout.
- Próxima etapa em card azul, sem botão Importar Agora.
- Tabela documental com cabeçalho escuro e estados por cor.
- Rodapé Exato com identidade visual.
- Aba Auditoria redesenhada para espelhar a linguagem do PDF, com destaque de status, Exato IA e Próxima etapa, sem Insights.

VALIDAÇÃO
---------
- py_compile do código: obrigatório antes da entrega.
- teste de geração do PDF com dados sintéticos: obrigatório.
- renderização do PDF e inspeção visual: obrigatória.
- teste de abertura da interface em ambiente gráfico: obrigatório.
- verificação de igualdade textual das funções fiscais críticas V085 → V087 para provar que os motores NF-e e Auditoria não foram alterados.
