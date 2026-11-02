EXATO CENTRAL FISCAL — V096


Base: V095 histórica, preservada.


Evoluções desta versão:
- XMLs: Empresa → Ano → Mês → Entrada/Saída → NF-e/NFC-e/CT-e.
- Entrada e Saída são criadas primeiro; os tipos documentais ficam dentro da direção.
- Se a direção não estiver disponível no registro, o sistema consulta o XML com o CNPJ da empresa; não classifica silenciosamente como Entrada quando não consegue determinar.
- PDFs fiscais consolidados ficam em “PDFs Fiscais” no nível do mês, um por tipo documental, reunindo Entrada e Saída.
- A abertura/geração da representação fiscal na Auditoria permanece disponível.
- DANFE de NF-e recebeu representação mais tradicional, com identificação fiscal, chave e código de barras, destinatário, faturamento, impostos, transportador/volumes, produtos, dados adicionais e paginação adaptativa.
- Assets oficiais enviados para continuidade foram incorporados.

Preservação:
- Não houve alteração nos núcleos de consulta/captura NF-e nem no motor de conciliação da Auditoria SAT × XML.
