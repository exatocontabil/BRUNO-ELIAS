EXATO CENTRAL FISCAL — V083

Objetivo
--------
A V083 inaugura a nova experiência visual e analítica da Auditoria Fiscal, preservando a base funcional validada da V082. O foco desta versão é transformar a conciliação SAT × XML em uma experiência única, clara, document-first e integrada ao novo Exato IA.

Principais alterações
---------------------
1. Nova Auditoria Fiscal
   - Layout baseado fielmente na referência visual aprovada.
   - Cabeçalho/contexto compactos com empresa, CNPJ, período e fonte.
   - Ações de Importar Excel, Gerar PDF, Histórico e Nova auditoria.
   - Indicadores: Documentos conciliados, Pendências de XML, Divergências de dados, Valor conciliado e Status.
   - Uma única tabela de documentos, com Situação, Nº Nota, Data, Modelo, Valor SAT, Valor XML e Observação.
   - Busca, filtro por situação, paginação e detalhes da conciliação.
   - As categorias principais da experiência são: Conforme, XML não localizado e Divergência.
   - “XML sem SAT” permanece apenas como informação complementar, não como bloco principal da experiência.

2. Motor de conciliação revisado
   - Chave de acesso como primeira forma de correspondência.
   - Fallback com número, série, data, modelo e direção para reduzir colisões.
   - Deduplicação dos registros SAT importados.
   - Comparação explícita de número, data e valor após a localização do documento.
   - Totais de valor conciliado separados dos documentos pendentes.
   - Resultado estruturado por documento para alimentar a interface e o PDF.
   - Tipos de documento normalizados visualmente para NF-e, NFC-e e CT-e.

3. Exato IA
   - Novo motor de análise contextual baseado exclusivamente nos resultados da conciliação.
   - Mensagens variadas, com diferentes níveis de atenção.
   - Identificação de documentos específicos quando existem achados.
   - Geração de principais insights e próximo passo.
   - Humor leve e contextual em situações apropriadas, sem inventar fatos.
   - Linguagem prudente: não transforma uma ausência ou diferença em “irregularidade” sem evidência.
   - Estados do mascote: conforme, analisando, atenção/alerta, dica e demais expressões disponíveis.

4. Mascote oficial
   - Exato IA passa a integrar oficialmente a Auditoria e seus PDFs.
   - Uniforme preto social de manga longa, com botões, símbolo Exato no lado esquerdo do peito e “exato soluções contábeis” abaixo do símbolo.
   - Expressão/pose varia conforme o resultado da análise.

5. PDF da Auditoria
   - Redesign completo alinhado à lógica da tela.
   - Cabeçalho Exato, contexto da empresa/período/fonte, KPIs, painel Exato IA, insights e tabela única de documentos.
   - Documentos problemáticos recebem destaque visual por situação.
   - Título da tabela muda entre “Documentos conciliados” e “Documentos analisados” conforme os resultados reais.
   - Observações técnicas permanecem compactas e secundárias.

6. Identidade da Central
   - Mantido o padrão escuro de cabeçalho/menu e área de trabalho clara.
   - Tipografia, espaçamentos e cards superiores foram compactados.
   - O nome “Auditoria Fiscal” e a linguagem da tela passaram a seguir a nova referência aprovada.

Preservação de funcionalidades
------------------------------
A V083 parte diretamente da V082 e mantém os blocos validados de captura NF-e/NFC-e/CT-e, sincronização e organização dos XMLs. Não foram alterados os fluxos de captura Web Service que já estavam validados.

A seleção de certificado permanece vinculada ao certificado escolhido no Central. A Auditoria desta versão continua baseada no Excel oficial do SAT importado manualmente, sem abrir navegador para executar a conciliação.

Histórico de auditorias
-----------------------
A V083 passa a registrar automaticamente as auditorias concluídas em arquivo local (auditoria_historico.json), criado na primeira execução, com empresa, período, status, contagens e arquivos de origem.

Testes executados
-----------------
- py_compile do exato_central_fiscal.py: OK.
- Inicialização da interface em ambiente virtual X: OK.
- Tela Auditoria Fiscal em ambiente virtual X: OK.
- Fluxo de auditoria com caso misto (conforme + divergência + XML não localizado): OK.
- Fluxo de auditoria integralmente conforme: OK.
- Importação real dos dois Excels SAT fornecidos para o período 01/08/2026–31/08/2026: 64 documentos únicos lidos; todos classificados como “XML não localizado” no banco de teste sem XMLs correspondentes.
- Geração dos PDFs de teste: OK.
- Verificação de chave de acesso e fallback de correspondência por modelo/direção: OK.
- Teste de não colisão entre NF-e/NFC-e e Entrada/Saída no fallback: OK.

Observação de teste
-------------------
O resultado do Excel real acima reflete o conteúdo do banco de teste utilizado neste ambiente. A classificação “XML não localizado” não significa que os XMLs estejam ausentes na instalação do usuário; ela é consequência direta da base de teste utilizada para a validação da rotina.
