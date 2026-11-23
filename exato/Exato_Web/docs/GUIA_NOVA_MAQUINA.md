# Exato Web: guia para instalar em outra máquina

Resumo do que funcionou na primeira instalação (computador AUXILIAR2, Windows 10, usuário sem senha, pasta de rede `\\SERVER\...`) e das armadilhas que apareceram.
Siga na ordem. Em caso de erro, mande o texto da janela e o arquivo `ExatoWebDados\logs\servidor_saida.log`.

## 0. Antes de começar (decidir)
- **Qual computador será o servidor do site?** Precisa ficar **ligado e com o usuário do Windows entrando sozinho** (entrada automática) para o site voltar após reiniciar. O ideal é um computador dedicado.
- **Qual usuário do Windows vai rodar o site?** Sempre o **mesmo**: o cofre dos certificados fica preso a ele (e à máquina).
- **Endereço:** o padrão é `https://fiscal.exatosolucoescontabeis.com` (só rede do escritório). O IP do computador precisa ser **reservado no roteador** (reserva de DHCP pelo MAC). Hoje: `192.168.0.136`.

## 1. Programas
1. Python 3.12 ou mais novo (64 bits), de python.org. Marque "Add python.exe to PATH". (Na primeira instalação havia o Python 3.15: funcionou; as dependências não têm versão fixa.)
2. Extraia o pacote `Exato_Web_AAAAMMDD?.zip` numa pasta **do próprio computador**, sem acentos nem espaços (ex.: `C:\ExatoWeb`). **Nunca rode o site de uma pasta de rede** (`\\SERVIDOR\...`): o Windows avisa "Não há suporte para caminhos UNC", cria letras de unidade soltas e não deixa ligar sozinho.
3. `INSTALAR_DEPENDENCIAS.bat`. Se o comando `python` falhar, o `.bat` usa `py -3`.

## 2. Dados e primeiro usuário
- Pasta de dados padrão: `<pasta do usuário>\ExatoWebDados` (banco, usuários, cofre, registros). Para outro disco: variável `EXATO_WEB_DADOS`; XMLs: `EXATO_WEB_ARQUIVOS`.
- Primeiro usuário (administrador): `py -3 -m web.usuarios criar --email ... --nome "..." --admin` (senha com no mínimo 10 caracteres). **Os demais usuários são criados pela tela Usuários** (menu, só administrador): nome, e-mail e perfil; o Exato gera uma senha provisória que a pessoa troca no primeiro acesso. Na mesma tela: bloquear, tornar administrador, nova senha provisória, zerar o código do celular, encerrar acessos. Cada pessoa troca a própria senha em Minha senha. Entrada exige o código de 6 números do celular: o site mostra um **QR code** para ler no aplicativo (não digite a chave à mão: a causa do "código inválido" foi chave digitada errada; os horários do celular e do computador também precisam estar certos).
- Importar o que já existe do Central Fiscal: `py -3 -m web.importar --origem "...\Dados"` com o site parado.

## 2b. Disco cheio? Dados em outro disco
Se o C: for pequeno, rode `MOVER_DADOS_PARA_OUTRO_DISCO.bat` (não precisa ser administrador): ele desliga o site, copia `ExatoWebDados` para uma pasta de outro disco **deste computador**, confere, grava o novo caminho em `dados.txt` (na pasta do site; sobrevive às atualizações) e liga de novo. A pasta antiga fica renomeada `..._ANTIGA_apagar_depois`: apague só depois de conferir que tudo funciona. Não use pasta de rede para o banco. Em máquina nova, já instale escolhendo o disco certo.

Para não digitar o código do celular toda vez: na tela do código, marque **"Confiar neste computador por 30 dias"** (só em computador do escritório). Nesse computador pede só a senha e a sessão dura até 7 dias. "Sair e esquecer este computador" (cadeado ao lado de Sair), trocar a senha ou zerar a verificação desfazem isso.

## 3. Ligar sozinho, sem janela preta
1. `INSTALAR_INICIO_AUTOMATICO.bat` (a partir da pasta local ou da rede: se estiver na rede ele copia para uma pasta local, padrão `C:\ExatoWeb`).
2. Informe o usuário do Windows. **Usuário sem senha:** aperte Enter na senha; a tarefa liga quando esse usuário **entra no Windows** (use `netplwiz` para a entrada automática). **Com senha:** liga com o computador, antes do login.
3. O site responde em `http://127.0.0.1:8443` (**http**, sem "s"; com "s" dá `ERR_SSL_PROTOCOL_ERROR`).
4. Dia a dia: `PARAR_SITE.bat`, `LIGAR_SITE.bat`, `VER_REGISTRO_DO_SITE.bat`, `REMOVER_INICIO_AUTOMATICO.bat`.

## 4. Endereço com cadeado (só rede do escritório)
1. `INSTALAR_ENDERECO_COMERCIAL.bat` (da pasta local, como administrador). Enter aceita `fiscal.exatosolucoescontabeis.com`. Baixa o Caddy, liga junto com o Windows (tarefa "Exato Web Endereco"), libera a 443 só para a rede local, registra o nome neste computador e gera a pasta `para_os_outros_pcs`.
2. **Cada outro computador** (até 3): copiar `para_os_outros_pcs` e rodar `INSTALAR_CERTIFICADO_NESTE_PC.bat` uma vez (o Windows pede um "Sim"; responder **S** ao registro do nome).
3. O registro no cPanel da HostGator (tipo A, `fiscal` → IP do computador) é **opcional**: sem ele o nome é registrado no arquivo `hosts` de cada PC. A senha da HostGator não é necessária.
4. A pasta `para_os_outros_pcs` tem o certificado do escritório: não espalhar fora.
5. Computador do site novo = certificado novo: rodar de novo os `.bat` dos outros PCs com a pasta nova.

## 5. Certificados A1 (cofre)
- **O cofre NÃO se copia de uma máquina/usuário para outro** (a chave é protegida pelo Windows): na máquina nova, **reenvie os certificados** na tela "Certificados A1" (guarde os arquivos .pfx originais num lugar seguro).
- A senha de e-mail do Box-e também é protegida pela mesma chave: digitar de novo.
- O site coloca o certificado no repositório do Windows só durante a busca. Se o **mesmo certificado já estiver instalado** no usuário, o site usa o que está lá e **nunca o remove** (corrigido no pacote s; antes ele apagava o seu).
- Para mudar de máquina mantendo notas, empresas e usuários: copiar `ExatoWebDados` **sem a pasta `cofre`** (e sem `logs`), parar o site antes.

## 6. Conferências depois de instalar
1. Entrar no site, enviar um certificado de teste e fazer uma busca numa empresa pequena.
2. Reiniciar o computador, entrar no Windows: site e endereço voltam sozinhos.
3. Abrir `https://fiscal...` num outro computador.
4. `CERTMGR.MSC`: conferir que os certificados do usuário continuam lá depois de uma busca.
5. Espaço em disco: o site para de copiar XMLs com menos de 1 GB livre; a cópia automática para a pasta vem **desligada** (liga na tela Repositório).

## 6b. Cópia de segurança (fazer logo no começo)
Menu **Cópia de segurança** (só administrador): escolha uma pasta em **outro disco, HD externo ou NAS**, a hora (padrão 02:00) e quantas cópias guardar (padrão 7), marque "Fazer a cópia todo dia" e **Salvar**. Use **Copiar agora** para testar. Leva o banco, usuários, cofre, auditorias e configuração; não leva `Arquivos`, ZIPs e PDFs (se refazem). Restaurar: na tela Cópia de segurança, botão **Restaurar** ao lado da cópia (pede a sua senha; o Exato reinicia sozinho e os dados de hoje ficam em `_antes_da_restauracao_...` dentro da pasta de dados). Se o Exato nem abrir: `RESTAURAR_BACKUP.bat`. Teste a restauração de vez em quando. A Situação da busca avisa (só o administrador) se a cópia não está ligada ou parou há mais de 2 dias. Guarde os `.pfx` originais.

Quando algo der errado: menu **Diagnóstico** (só administrador) → "Baixar o diagnóstico" (ZIP sem notas, certificados nem senhas; CNPJ, CPF e e-mails escondidos por padrão) ou enviar por e-mail ao suporte.

## 7. Atualizar o site (1 clique)
Baixe o pacote novo (`Exato_Web_AAAAMMDD?.zip`, normalmente em Downloads) e rode **`ATUALIZAR_SITE.bat`** na pasta do site (ou o atalho **Ctrl+Alt+A** da Área de Trabalho, criado por `CRIAR_ATALHOS_NA_AREA_DE_TRABALHO.bat`). Ele acha o ZIP mais novo, mostra "versão instalada → versão nova", desliga o site, guarda a versão anterior em `_versao_anterior`, troca os arquivos (nunca mexe nos dados, no cofre, no endereço nem no `dados.txt`), instala dependências novas se precisar, religa e confere. Se o site não subir, **volta sozinho** para a versão anterior. Depois: Ctrl+F5 no navegador.
Atalhos: **Ctrl+Alt+A** atualiza, **Ctrl+Alt+P** para, **Ctrl+Alt+L** liga (valem enquanto os atalhos ficarem na Área de Trabalho; a tecla pode ser mudada nas Propriedades do atalho).

## 8. Problemas já vistos
| Sintoma | Causa | O que fazer |
|---|---|---|
| "No module named 'web'" / "Did you mean 'Web'?" | pasta de rede ou `web` com maiúscula | rodar de pasta local; o `INICIAR_SERVIDOR.bat` corrige a caixa |
| Letras `\\SERVER` aparecendo no Explorador | `pushd` de pasta de rede | rodar de pasta local |
| Instalador: "Sem senha não dá para ligar" | usuário sem senha | versão u ou mais nova (liga no login) |
| `ERR_SSL_PROTOCOL_ERROR` | usou https no endereço 127.0.0.1:8443 | `http://127.0.0.1:8443`, ou o endereço com cadeado |
| "Internal Server Error" no Repositório | disco C: cheio | liberar espaço; `ExatoWebDados\Arquivos` pode ser apagado (são cópias) |
| Certificado sumiu do `CERTMGR.MSC` | bug antigo (antes do pacote s) | reinstalar o .pfx no Windows e usar pacote s ou mais novo |
| Busca "Em andamento" para sempre | etapas finais pesadas | corrigido no pacote o |
| Cadeado com aviso num PC | certificado do escritório não instalado nele | `INSTALAR_CERTIFICADO_NESTE_PC.bat` |
