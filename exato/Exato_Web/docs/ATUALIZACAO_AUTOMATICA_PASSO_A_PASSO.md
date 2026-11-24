# Atualização automática do Exato Web (Opção A) - o que você precisa fazer uma vez

O Exato confere uma vez por dia se há versão nova num endereço PÚBLICO e se atualiza pelo botão "Atualizar agora" (menu "Atualizar o Exato").
Esse endereço é um repositório do GitHub só com os instaladores (o código-fonte continua no repositório privado).

## 1. Criar o lugar das atualizações (uma vez)
1. Entre em github.com com a conta **exatocontabil**.
2. Clique em **New repository** (botão verde).
3. Nome: `exato-web-atualizacoes`. Marque **Public**. Marque "Add a README file". Clique em **Create repository**.
   (Se usar outro nome ou conta, avise: o endereço fica dentro do Exato e eu ajusto.)

## 2. Criar a chave que permite publicar lá (uma vez)
1. No GitHub: foto do perfil > **Settings** > (lá embaixo) **Developer settings** > **Personal access tokens** > **Fine-grained tokens** > **Generate new token**.
2. Nome: `Exato atualizacoes`. Validade: 1 ano. **Repository access**: "Only select repositories" > `exato-web-atualizacoes`.
3. Em **Permissions** > **Repository permissions**: **Contents** = **Read and write**. Clique em **Generate token** e **copie** a chave (ela só aparece uma vez).
4. Vá no repositório **BRUNO-ELIAS** > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**.
5. Name: `ATUALIZACOES_TOKEN`. Secret: cole a chave. **Add secret**.

## 3. Depois disso
Cada vez que eu publicar uma versão nova (Actions > "Instalador do Exato Web" > Run workflow, ou eu aviso que já publiquei), ela vai também para o lugar das atualizações.
No Exato: menu **Atualizar o Exato** > aparece "Há uma versão nova" > senha > **Atualizar agora**. Também aparece o selo "Nova" no menu.

Se a chave vencer, a publicação mostra um aviso e o instalador continua indo para a página Releases do repositório privado; renove a chave (passo 2).
