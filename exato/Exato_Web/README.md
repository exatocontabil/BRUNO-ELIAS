# Exato Web

Site do escritório (Exato Central Fiscal na internet): login com verificação em duas etapas, cofre dos certificados A1, empresas, situação da busca e documentos.
Fase 1: acesso, cofre e consulta. Fase 2: busca automática no servidor (NF-e, NFC-e, CT-e e NFS-e, inclusive por procuração), a cada 4 horas e sob pedido.

## O que já tem
Login com verificação em duas etapas • cofre dos certificados A1 • empresas • situação da busca com busca automática (NF-e, NFC-e, CT-e, NFS-e, A1 próprio ou do escritório) •
Auditoria (Excel do SAT, PDF do comparativo, buscar só os XML que faltam) • Repositório (XMLs em arquivos e ZIP por mês) • Relatórios em PDF • documentos e XML •
importação dos dados do programa instalado (`python -m web.importar`). Instalação: `docs/INSTALACAO_WINDOWS.md`. Pacote: `python montar_web.py`.

## Como roda
- Python 3.12+ **no Windows** (as rotinas fiscais do Exato usam o repositório de certificados do Windows). O servidor do escritório serve.
- `pip install -r requirements.txt`
- Primeiro usuário: `python -m web.usuarios criar --email voce@escritorio.com.br --nome "Seu Nome" --admin`
- Iniciar: `INICIAR_SERVIDOR.bat` (porta 8443 só para o próprio servidor). Quem acessa de fora passa por um proxy com HTTPS (veja docs/ARQUITETURA.md).
- Dados em `%USERPROFILE%\ExatoWebDados` (ou `EXATO_WEB_DADOS`). Faça cópia desta pasta todos os dias.

## Regras
- Nunca abrir o site na internet sem HTTPS e sem a verificação em duas etapas (vem ligada).
- Os módulos do Exato (inclusive os 13 núcleos fiscais protegidos) são usados como estão; nada deles é alterado.
- Testes: `python testes/rodar_todos.py` (SEFAZ e Emissor Nacional simulados).
