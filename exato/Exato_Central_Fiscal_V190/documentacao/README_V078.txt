EXATO CENTRAL FISCAL — V078

Base: V077

OBJETIVO DESTA VERSÃO
- Aumentar a confiabilidade da autenticação SAT com o certificado selecionado no Windows.
- Reproduzir o fluxo real comprovado manualmente: Login → certificado → Aplicações → NFe/NFCe.
- Refinar a interface seguindo o padrão visual aprovado como “Opção 2 — Dashboard Visual”.
- Preservar a arquitetura NF-e, NFC-e, CT-e, XML, banco e checkpoints já validados.

SAT / CERTIFICADO
- AutoSelectCertificateForUrls passou a usar prioritariamente SUBJECT.CN, porque a documentação do Edge aceita os campos CN/O/OU/L em SUBJECT/ISSUER e o certificado selecionado continua sendo identificado internamente pelo thumbprint.
- Edge usa perfil temporário dedicado, janela fora da área visível e política de autoseleção.
- Foi criado fallback para a janela nativa de seleção de certificado do Windows: o sistema procura o certificado pelo Subject CN e confirma automaticamente o certificado correspondente, sem exportar a chave privada.
- O monitor do diálogo é encerrado assim que Apps.aspx é detectado ou quando a tentativa termina.
- O fluxo HTTP direto permanece apenas como diagnóstico.

CONSULTA SAT
- Depois da autenticação, continua abrindo “1. NFe / NFCe - Consulta” pela área Aplicações.
- A pesquisa continua usando o POST/XHR real de ConsultaOnlineCC.aspx.
- Exportação e comparação SAT × XML permanecem automáticas.

NF-e
- indAtor=1 = Emitente / Saída.
- indAtor=2 = Destinatário / Entrada.
- Checkpoints independentes preservados.
- Não usar esta versão para substituir a arquitetura já validada.

REDESIGN
- Documentos Fiscais: cards de certificado e empresa, período, ações e indicadores com visual de dashboard.
- Indicadores NF-e/NFC-e/CT-e receberam barras visuais e hierarquia mais próxima da Opção 2.
- Auditoria Fiscal recebeu cards de resumo, cabeçalho de status e organização visual mais próxima do padrão aprovado.
- CNPJ/CPF do certificado continua oculto no cartão de Documentos Fiscais.

TESTES LOCAIS
- py_compile: OK
- importação do módulo: OK
- construção das principais telas em smoke test Tk/Xvfb: OK
- filtro do certificado: SUBJECT.CN
- parser Excel real: mantido
- motor SAT × XML: mantido

PONTO A VALIDAR NO WINDOWS DO USUÁRIO
- Se a autoseleção do certificado ou o fallback nativo conseguir completar Login → Apps.aspx sem intervenção manual.
- Se a sessão for mantida ao abrir NFe/NFCe - Consulta.
