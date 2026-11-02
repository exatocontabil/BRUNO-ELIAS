V097 — TESTE DE ESTRUTURA DE EXPORTAÇÃO E REPRESENTAÇÃO FISCAL

Base: V096.
Proteção: núcleos funcionais validados de NF-e e Auditoria preservados.

Alterações desta versão, solicitadas explicitamente para teste:
1. XMLs continuam organizados por Empresa → Ano → Mês → Entrada/Saída → tipo documental.
2. PDFs consolidados deixam de usar a pasta “PDFs Fiscais” e passam para a pasta de seu próprio tipo documental no nível do mês:
   - NF-e → DANFEs_aa-aaaa.pdf
   - NFC-e → DANFE_NFCe_aa-aaaa.pdf
   - CT-e → DACTEs_aa-aaaa.pdf
   Entrada/Saída não fragmenta o PDF consolidado.
3. NF-e e NFC-e passam a usar o renderizador fiscal tradicional baseado nas referências do usuário, no estilo “RESUMO DA NF-e/NFC-e”, com cabeçalho institucional de Santa Catarina, identificação, chave, protocolo, destinatário, impostos, transportador, produtos, ISSQN, dados adicionais e reservado ao fisco.
4. A referência da NF-e e a referência da NFC-e fornecidas pelo usuário foram armazenadas em referencias/ para continuidade.
5. O brasão de Santa Catarina usado no modelo foi incorporado em assets/crest_sc_reference.png.

Critério de preservação:
- Não reescrever os núcleos protegidos de NF-e e Auditoria.
- Mudanças limitadas aos fluxos de exportação de XML/PDF e representação fiscal.

Testes direcionados:
- compilação Python;
- geração de PDF NF-e;
- geração de PDF NFC-e;
- exportação com Entrada/Saída;
- PDF consolidado dentro da pasta do tipo documental;
- ausência da pasta “PDFs Fiscais”;
- preservação por SHA-256 dos 9 núcleos protegidos.
