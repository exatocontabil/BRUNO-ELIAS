V099 — CORREÇÕES DO RELATÓRIO DE DOCUMENTOS FISCAIS

Base: V098.
Autorização: continuidade explicitamente solicitada pelo usuário.

CORREÇÕES IMPLEMENTADAS
1. Totais das páginas detalhadas agora distinguem:
   - TOTAL DA OPERAÇÃO = total de documentos da Entrada ou Saída em todo o relatório;
   - NESTA PÁGINA = quantidade e valor somente do bloco da página atual.
2. “Principais informações” usa o escopo completo da direção (Entrada ou Saída), evitando misturar total da operação com subtotal da página.
3. A Exato IA das páginas detalhadas não é repetida em todas as páginas; aparece uma única vez, no fechamento de cada direção.
4. Paginação detalhada passou a ser balanceada para evitar páginas finais com apenas 1 documento quando o conteúdo permite uma distribuição mais uniforme.
5. O gráfico da página executiva passou de 4 para 5 semanas, cobrindo também os dias 29 a 31 em períodos mensais de 31 dias.
6. O texto da Exato IA passou a explicar “natureza registrada nos documentos de entrada/saída”, evitando sugerir que o sistema alterou o sentido da operação.
7. A coluna “Natureza da Operação” recebeu mais largura relativa, reduzindo quebras desnecessárias.
8. “DOCUMENTOS DE DESTAQUE” substitui o título “PRINCIPAIS DOCUMENTOS” na página executiva para deixar a seção como destaque documental, sem sugerir análise fiscal abrangente.

PRESERVAÇÃO
- Núcleo protegido de captura NF-e preservado.
- Núcleo protegido da Auditoria SAT × XML preservado.
- Abertura/geração de representação fiscal pela Auditoria preservada.
- Regra de organização XML + PDF lado a lado permanece na estrutura Entrada/Saída → Tipo documental.

TESTES
- py_compile;
- relatório com 68 documentos sintéticos (19 entradas + 49 saídas);
- paginação balanceada e sem mistura de direções;
- total da operação × subtotal da página;
- Exato IA apenas uma vez por direção;
- semana 5 do gráfico cobrindo 29–31;
- XML/PDF lado a lado;
- regressão da Exato IA;
- regressão da interface da Auditoria;
- preservação dos 9 núcleos fiscais por SHA-256.
