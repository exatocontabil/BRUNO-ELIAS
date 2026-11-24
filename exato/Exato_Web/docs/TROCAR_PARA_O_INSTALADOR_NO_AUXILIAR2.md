# Trocar o Exato Web do AUXILIAR2 pelo instalador único

Tempo: uns 15 minutos. O site fica fora do ar durante a troca. Faça fora do horário de uso.
Nada é apagado: a pasta antiga `C:\ExatoWeb` fica como está, para você poder voltar atrás.

## Antes de começar
1. Entre no Exato (pelo endereço de sempre) > **Cópia de segurança** > **Fazer cópia agora**. Espere terminar.
2. Baixe o instalador: https://github.com/exatocontabil/BRUNO-ELIAS/releases/tag/exato-web-instalador-11
   (arquivo `Exato_Web_Instalador_...exe`, no fim da página). Deixe na Área de Trabalho.

## Passo 1 - Parar o Exato antigo
1. Abra `C:\ExatoWeb` e dê dois cliques em **PARAR_SITE.bat**.
2. Abra o **Agendador de Tarefas** (Iniciar > digite "Agendador de Tarefas").
3. Em "Biblioteca do Agendador de Tarefas", clique na tarefa **Exato Web** com o botão direito > **Desabilitar**.
   (Sem isso, o Exato antigo ligaria junto com o novo e um atrapalharia o outro.)
4. Não mexa na tarefa/serviço do endereço com cadeado (o "fiscal.exatosolucoescontabeis.com"). Ele continua valendo.

## Passo 2 - Instalar
1. Dê dois cliques no instalador. Se o Windows avisar "protegeu o computador": **Mais informações > Executar assim mesmo**.
2. Na tela da pasta de dados, o instalador deve sugerir a pasta **ExatoWebDados** que já existe no usuário do AUXILIAR2. **Confira o caminho e deixe esse mesmo.**
   Se você já tinha mudado os dados para outro disco, escolha aqui a pasta onde eles estão.
   (NÃO aceite uma pasta nova e vazia: o Exato abriria como se fosse a primeira vez.)
3. Na tela **Endereço do escritório**, confira se aparece `fiscal.exatosolucoescontabeis.com` (se vier em branco, digite). Assim o Exato abre pelo endereço com cadeado.
4. Avance até o fim. O Exato abre sozinho no navegador.

## Passo 3 - Conferir
1. Abra https://fiscal.exatosolucoescontabeis.com. Deve pedir o seu usuário, senha e código do autenticador, como sempre.
   Se aparecer "Criar o administrador", a pasta de dados escolhida está errada: veja "Se der errado".
2. Confira se as empresas, as notas e o certificado continuam aparecendo.
3. Reinicie o AUXILIAR2 e veja se o Exato liga sozinho, sem janela preta.

## Passo 4 - Arrumar depois (quando estiver tudo certo por alguns dias)
- O atalho Ctrl+Alt+A (atualizar) do jeito antigo deixa de ser usado. Para atualizar a partir de agora: rodar o instalador novo por cima.
- A pasta `C:\ExatoWeb` pode ser guardada ou apagada por você. Não apague a pasta de dados `ExatoWebDados`.

## Se der errado (voltar ao Exato antigo)
1. Menu Iniciar > **Parar o Exato** (do Exato novo).
2. Agendador de Tarefas > tarefa **Exato Web** > **Habilitar**, e clique em **Executar**.
3. Seus dados continuam intactos. Se precisar, restaure a cópia de segurança feita no começo.
