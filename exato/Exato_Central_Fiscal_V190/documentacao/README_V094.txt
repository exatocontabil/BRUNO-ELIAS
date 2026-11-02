EXATO CENTRAL FISCAL — V094

Base operacional: V093. Os núcleos funcionais protegidos de NF-e e Auditoria SAT × XML não foram alterados intencionalmente.

Evoluções implementadas:
- Busca Global em Documentos Fiscais.
- Ações por documento: VER/GERAR DANFE, VER/GERAR DANFE NFC-e e VER/GERAR DACTE.
- Visualização do XML original, cópia da chave e abertura da pasta de visualização.
- Representação fiscal individual reutiliza PDF existente ou gera sob demanda.
- PDF consolidado único por tipo/ano/mês, sem fragmentação por Entrada/Saída.
- Opção de geração automática dos PDFs fiscais ao salvar XMLs, ativada por padrão.
- Estado de NF-e “Aguardando próxima janela” separado de falha real.
- Exato IA reconhece perguntas equivalentes a “Qual nota devo revisar primeiro?”.

Validação complementar:
- Exato IA legado: aprovado.
- Smoke test de geração: NF-e/DANFE, NFC-e/DANFE NFC-e e CT-e/DACTE: aprovado, 1 página por documento no caso simples.
- Inicialização da UI com Xvfb: aprovada.
- Navegação Documentos Fiscais: aprovada.
- Tela Buscar XML e habilitação do controle de PDFs após CNPJ confirmado: aprovada.
