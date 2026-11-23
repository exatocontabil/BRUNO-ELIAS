"""Exato Web como produto: nenhuma linguagem de programação/técnica visível ao usuário (telas, respostas do Exatinho, causas da busca, mensagens)."""
import os, re, sys, tempfile, html
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ['EXATO_WEB_DADOS'] = tempfile.mkdtemp(prefix='exato_web_txt_'); os.environ['EXATO_WEB_HTTPS'] = '0'; os.environ['EXATO_WEB_EXIGIR_2FA'] = '0'; os.environ['EXATO_WEB_COFRE_CHAVE'] = 'x'
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / 'testes')); sys.path.insert(0, str(RAIZ.parent / 'Exato_Central_Fiscal_V190' / 'testes'))
from fastapi.testclient import TestClient
from web import cofre as cm, config, texto_claro
from web.app import criar_app
from web.exatinho_base import TOPICOS

PROIBIDOS = re.compile(r"\.bat\b|PowerShell|Python|pythonw|\bSMTP\b|STARTTLS|\bSSL\b|\bcStat\b|\bNSU\b|registro de erros|exato\.log|DPAPI|thumbprint|\bCSRF\b|\bcookies?\b|\bcache\b|\bJSON\b|\bAPI\b|Traceback|\bCaddy\b|\bpushd\b|web\.usuarios|web\.importar|python -m|INICIAR_SERVIDOR|RESTAURAR_BACKUP|ATUALIZAR_SITE|central_fiscal\.db|web\.db|\bbanco\b", re.I)

# 1) limpeza dos textos que vêm de módulos do programa instalado
assert 'STARTTLS' not in texto_claro.limpar('Tente a porta 587 com STARTTLS ou 465 com SSL no SMTP') and 'exato.log' not in texto_claro.limpar('envie o arquivo exato.log ao suporte') and 'registro de erros' not in texto_claro.limpar('foi guardado no registro de erros')
assert texto_claro.limpar(None) is None and texto_claro.limpar('Texto normal.') == 'Texto normal.'

# 2) respostas do Exatinho
for t in TOPICOS:
    for r in t['resposta'] + [t['titulo']]:
        m = PROIBIDOS.search(r); assert not m, (t['id'], m.group(0), r[:80])

# 3) telas (como administrador) e causas da busca
app = criar_app(importador=cm.ImportadorFalso()); core = app.state.core; motor = app.state.motor; config.EXIGIR_2FA = False
core.db_auth_register_user('Admin', 'a@exemplo.com.br', 'SenhaForte#2026'); c_ = core._auth_connect(); c_.execute("UPDATE users SET role='admin'"); c_.commit(); c_.close()
for cod, v in motor.motivos.CAUSAS.items():
    for x in v:
        if isinstance(x, str): m = PROIBIDOS.search(x); assert not m, (cod, m.group(0), x[:80])
cl = TestClient(app, base_url='http://testserver', follow_redirects=True); cl.get('/login'); tk = cl.cookies.get('exato_csrf'); cl.post('/login', data={'email': 'a@exemplo.com.br', 'senha': 'SenhaForte#2026', 'csrf': tk})
rotas = sorted({r.path for r in app.routes if hasattr(r, 'methods') and 'GET' in r.methods and '{' not in r.path and not r.path.startswith(('/static', '/docs', '/openapi', '/redoc')) and r.path not in ('/saude', '/busca/estado', '/exportar/estado', '/exatinho/resumo', '/backup/pastas', '/repositorio/zip', '/fechamento/arquivo', '/resumo/previa')})
assert len(rotas) >= 15, rotas
for p in rotas:
    r = cl.get(p); assert r.status_code == 200, (p, r.status_code)
    t = re.sub(r'(?s)<(script|style|svg)[^>]*>.*?</\1>', '', r.text); t = re.sub(r'(?s)<!--.*?-->', '', t); t = html.unescape(re.sub(r'<[^>]+>', '\n', t))
    m = PROIBIDOS.search(t); assert not m, (p, m.group(0), t[max(0, m.start() - 60):m.end() + 60])
print('Exato Web (textos em português claro): OK')
