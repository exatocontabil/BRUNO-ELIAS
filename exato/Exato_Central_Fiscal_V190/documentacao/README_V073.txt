EXATO CENTRAL FISCAL — V073

OBJETIVO
Corrigir a autenticação automática da Auditoria SAT × XML a partir das evidências reais obtidas no portal SAT e preservar a captura de NF-e de entrada que havia sido validada.

CORREÇÃO PRINCIPAL — SAT
- V072 foi revisada e o caminho Login → default.aspx foi considerado inadequado para representar a autenticação por certificado.
- V073 passa a usar o endpoint CertificateAuth.ashx observado no fluxo real do SAT.
- O certificado utilizado é exatamente o certificado previamente selecionado na Central, identificado pelo thumbprint.
- A autenticação usa o certificado diretamente do armazenamento do Windows através do WinHTTP.
- O fluxo mantém os cookies retornados pelo SAT e segue os redirecionamentos até Apps.aspx.
- A sessão só é considerada autenticada quando o portal chega a Apps.aspx sem voltar à tela de login.
- Nenhuma chave privada é exportada, copiada ou convertida em PFX.
- Depois da autenticação, o navegador de consulta continua invisível e recebe apenas os cookies da sessão autenticada.
- A navegação continua respeitando Aplicações → 1. NFe / NFCe - Consulta.
- A consulta espera a resposta POST/XHR real do botão Buscar, reduzindo falsos erros quando o SAT estiver lento.
- O filtro de datas mantém os nomes reais observados no formulário: dtDataInicial e dtDataFinal.

CORREÇÃO DE INTEGRIDADE DA AUDITORIA
- V072 havia removido acidentalmente as rotinas internas _audit_xml_rows, _normalize_access_key e _audit_key.
- V073 restaura essas rotinas para que a comparação SAT × XML permaneça funcional após a obtenção dos dados.
- A comparação continua priorizando a chave de acesso e usando número + série + data como fallback.
- A conferência considera os dados importantes definidos no projeto: número da nota, data e valor.
- A chave permanece interna para vincular os registros e não precisa dominar a apresentação ao usuário.

NF-e
- V073 preserva os dois fluxos independentes já validados: indAtor=1 (Emitente/Saída) e indAtor=2 (Destinatário/Entrada).
- O checkpoint de cada participação permanece separado.
- Não foi mantida a alteração da V072 que podia interromper o segundo fluxo após um cStat 117 no primeiro.
- Não alterar esta arquitetura sem evidência técnica e teste real.

PRESERVAÇÃO
- NFC-e;
- CT-e;
- XMLs;
- banco de dados;
- empresas;
- certificado selecionado;
- relatórios;
- identidade visual Exato;
- histórico e checkpoints.

VALIDAÇÕES LOCAIS EXECUTADAS
- compilação Python;
- importação do módulo;
- presença das rotinas de auditoria;
- leitura dos Excel reais de NF-e e NFC-e fornecidos para teste;
- teste do motor SAT × XML com dados simulados;
- verificação estática dos fluxos NF-e indAtor=1 e indAtor=2;
- inspeção do fluxo de autenticação V073.

VALIDAÇÃO REAL NECESSÁRIA
A autenticação final precisa ser testada no Windows do usuário com o certificado selecionado na Central e com acesso ao SAT real. O teste deve observar se o fluxo chega a Apps.aspx e, em seguida, à consulta NFe/NFCe sem retornar ao Login.
