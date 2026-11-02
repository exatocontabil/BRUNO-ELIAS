V098 — RELATÓRIO EXECUTIVO + DETALHAMENTO SEPARADO + XML/PDF JUNTOS

Base: V097.
Autorização: nova versão explicitamente solicitada pelo usuário.

ALTERAÇÕES AUTORIZADAS
1. Relatório de Documentos Fiscais redesenhado de acordo com as referências visuais aprovadas:
   - página 1 executiva/resumida;
   - páginas seguintes detalhadas por direção;
   - Entrada e Saída nunca são misturadas nas páginas detalhadas.
2. Página 1 com a composição aprovada: empresa/período, quatro KPIs, movimentação do período, Exato IA, auditoria documental, principais documentos, pontos de atenção e próximas ações.
3. Páginas de detalhamento:
   - ENTRADAS em páginas próprias;
   - SAÍDAS em páginas próprias;
   - uma linha por documento;
   - coluna Natureza da Operação;
   - fornecedor/emitente ou cliente/destinatário conforme a direção;
   - análise específica da Exato IA e ranking de Naturezas da Operação por direção.
4. Não existe listagem “Todos” nas páginas detalhadas.
5. Exportação dos arquivos:
   Empresa → Ano → Mês → Entrada/Saída → Tipo documental → XML + PDF individual.
   Não criar pasta “PDFs Fiscais” e não criar pastas de tipo documental fora de Entrada/Saída.
6. Cada PDF individual é salvo ao lado do XML correspondente e reutilizado quando já existe e está íntegro.
7. As representações fiscais NF-e/NFC-e/CT-e permanecem baseadas no XML original.
8. Assets oficiais e referências visuais aprovadas permanecem incorporados ao pacote.

FIDELIDADE VISUAL
- A página 1 e a página 2 foram implementadas tomando as imagens aprovadas pelo usuário como especificação visual, preservando a hierarquia, proporções relativas, cores, tipografia, blocos, espaçamento e composição.
- Conteúdo textual/numérico permanece dinâmico e é derivado dos dados fiscais reais, portanto pode variar sem alterar a estrutura visual.

PROTEÇÃO
- Não foi alterado o núcleo protegido de captura NF-e.
- Não foi alterado o núcleo protegido da Auditoria SAT × XML.
- Abertura/geração de representação pela Auditoria permanece preservada.

TESTES
- py_compile;
- geração de DANFE NF-e;
- geração de DANFE NFC-e;
- relatório 1 página executiva + páginas separadas por direção;
- Natureza da Operação nas páginas detalhadas;
- ausência de página de direção vazia;
- exportação XML + PDF lado a lado;
- ausência de pastas de PDF separadas;
- regressão dos núcleos protegidos por SHA-256.
