# Exato Web — instalação no servidor Windows

Faça com calma, na ordem. Cada passo tem um jeito de conferir.

## 1. Programas
1. Instale o **Python 3.12 (64 bits)** de python.org. Marque "Add python.exe to PATH" e deixe o **tcl/tk** marcado (o Exato usa).
2. Crie a pasta `C:\ExatoWeb` e extraia nela o pacote `Exato_Web_AAAAMMDD.zip` (fica `C:\ExatoWeb\Exato_Web`).
3. No PowerShell: `cd C:\ExatoWeb\Exato_Web` e `python -m pip install -r requirements.txt`.

## 2. Uma conta própria para o site
Crie um usuário do Windows só para isso (ex.: `exatoweb`), **sem** ser administrador. O site, a pasta de dados e o cofre dos certificados ficam sob essa conta. Entre com ela para os próximos passos.

## 3. Dados e primeiro usuário
- Pasta de dados (padrão `C:\Users\exatoweb\ExatoWebDados`). Para outro disco: variável `EXATO_WEB_DADOS`. XMLs em arquivos: `EXATO_WEB_ARQUIVOS` (ex.: `D:\ExatoXML`).
- Crie o primeiro usuário: `python -m web.usuarios criar --email voce@escritorio.com.br --nome "Seu Nome" --admin`
- **Importar o que já existe** (empresas, notas e pontos de busca do programa instalado). Pare o site e rode:
  `python -m web.importar --origem "C:\Users\voce\AppData\Local\Exato\Central Fiscal\Dados"` (ou um backup `.zip`). Pode repetir com outros computadores.

## 4. Conferir o certificado no Windows (obrigatório antes de usar)
O site coloca o A1 no repositório de certificados do usuário `exatoweb` só durante a consulta. Teste antes de confiar: entre no site, envie um A1 na tela **Certificados A1** e use **Buscar** em uma empresa pequena. Se aparecer "O Windows não aceitou o certificado...", me envie a mensagem.

## 5. Ligar o site
`INICIAR_SERVIDOR.bat` (escuta só em 127.0.0.1:8443). Para ficar sempre ligado: Agendador de Tarefas → "Ao iniciar o computador" → executar `INICIAR_SERVIDOR.bat` com a conta `exatoweb` ("Executar estando o usuário conectado ou não").

## 6. HTTPS e internet (obrigatório antes de abrir para fora)
- Um nome (domínio ou subdomínio) apontando para o IP do escritório e a porta **443** liberada no roteador/firewall para o servidor (só ela).
- **Caddy** (caddyserver.com) na frente, repassando para o site. Arquivo `Caddyfile`:
  ```
  exato.seudominio.com.br {
      reverse_proxy 127.0.0.1:8443
  }
  ```
  O Caddy obtém e renova o certificado HTTPS sozinho. Só depois disso abra no celular/casa.
- Firewall do Windows: bloqueie tudo que chega, exceto 443 (Caddy) e o que o escritório já usa.

## 7. Cópia de segurança (todo dia)
Copie `ExatoWebDados` (e a pasta de XMLs) para outro disco/computador. Exemplo de tarefa diária (robocopy):
`robocopy "C:\Users\exatoweb\ExatoWebDados" "E:\CopiaExato\ExatoWebDados" /MIR /R:2 /W:5`
Sem a pasta `cofre` o site não abre os certificados: ela precisa ir junto, e a chave só funciona na conta `exatoweb` deste servidor — por isso guarde também os arquivos A1 originais num lugar seguro.

## 8. No dia a dia
- Usuário novo: `python -m web.usuarios criar ...`. Perdeu o celular: `python -m web.usuarios zerar-2fa --email ...`. Trocou a senha: `... senha --email ...` (derruba os acessos abertos).
- Atualizar: pare o site, extraia o pacote novo por cima (os dados ficam fora da pasta) e inicie de novo.
