# Exato Web

Site do escritório (Exato Central Fiscal na internet): login com verificação em duas etapas, cofre dos certificados A1, empresas, situação da busca e documentos.
Fase 1 (esta). A busca automática no servidor é a fase 2.

## Como roda
- Python 3.12+ **no Windows** (as rotinas fiscais do Exato usam o repositório de certificados do Windows). O servidor do escritório serve.
- `pip install -r requirements.txt`
- Primeiro usuário: `python -m web.usuarios criar --email voce@escritorio.com.br --nome "Seu Nome" --admin`
- Iniciar: `INICIAR_SERVIDOR.bat` (porta 8443 só para o próprio servidor). Quem acessa de fora passa por um proxy com HTTPS (veja docs/ARQUITETURA.md).
- Dados em `%USERPROFILE%\ExatoWebDados` (ou `EXATO_WEB_DADOS`). Faça cópia desta pasta todos os dias.

## Regras
- Nunca abrir o site na internet sem HTTPS e sem a verificação em duas etapas (vem ligada).
- Os módulos do Exato (inclusive os 13 núcleos fiscais protegidos) são usados como estão; nada deles é alterado.
- Testes: `python testes/test_web_f1.py`.
