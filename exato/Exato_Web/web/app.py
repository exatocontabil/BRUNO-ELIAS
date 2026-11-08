"""Exato Web — site do escritório. Rotas, sessão e telas. A lógica fiscal vem do código do Exato (web.nucleo); aqui só há acesso, cofre e apresentação."""
import re, secrets, sqlite3, time
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, nucleo, seguranca
from .cofre import Cofre, CofreErro, carregar_chave_mestra

AQUI = Path(__file__).resolve().parent
ROTULOS_TIPO = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}


def criar_app(importador=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)          # sem página de documentação técnica exposta na internet
    app.mount('/static', StaticFiles(directory=str(AQUI / 'static')), name='static')
    tpl = Jinja2Templates(directory=str(AQUI / 'templates'))
    core = nucleo.core()
    pasta_cofre = config.DADOS / 'cofre'
    chave = carregar_chave_mestra(pasta_cofre)
    cofre = Cofre(pasta_cofre, chave, importador=importador)
    totp = seguranca.Totp(config.DADOS / 'web.db', chave)
    limite = seguranca.LimiteLogin()
    app.state.cofre, app.state.totp, app.state.limite, app.state.core = cofre, totp, limite, core
    motivos = nucleo.modulo('exato_busca_motivos'); situacao = nucleo.modulo('exato_situacao_busca')

    # ------------------------------------------------------------ ajudantes
    def ip(request): return (request.client.host if request.client else '') or ''

    def cookie(resp, nome, valor, segundos, http_only=True):
        resp.set_cookie(nome, valor, max_age=segundos, httponly=http_only, samesite='strict', secure=config.HTTPS, path='/')

    def usuario(request):
        d = seguranca.verificar(request.cookies.get('exato_sessao', ''))
        if not d: return None
        u = core.db_auth_get_user_by_id(d.get('uid'))
        return core._auth_user_from_row(u) if u and str(u.get('status')) == 'active' else None

    def csrf_do_pedido(request): return request.cookies.get('exato_csrf') or secrets.token_urlsafe(24)

    def pagina(request, nome, ctx=None, status=200, user=None):
        c = dict(ctx or {}); tk = csrf_do_pedido(request)
        c.update({'request': request, 'csrf': tk, 'usuario': user, 'rotulos': ROTULOS_TIPO})
        resp = tpl.TemplateResponse(request, nome, c, status_code=status)
        if 'exato_csrf' not in request.cookies: cookie(resp, 'exato_csrf', tk, 86400 * 30, http_only=False)
        resp.headers['Cache-Control'] = 'no-store'
        return resp

    def csrf_ok(request, csrf):
        ck = request.cookies.get('exato_csrf', '')
        return bool(ck) and bool(csrf) and secrets.compare_digest(ck, str(csrf))

    def log(user, acao, detalhe=''):
        try: core.db_auth_log({'id': user.get('id'), 'email': user.get('email')}, acao, detalhe)
        except Exception: pass

    def exigir(request):
        """(usuario, None) se logado; senão (None, redirecionamento para o login)."""
        u = usuario(request)
        return (u, None) if u else (None, RedirectResponse('/login', status_code=303))

    @app.middleware('http')
    async def cabecalhos(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.update({'X-Frame-Options': 'DENY', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin',
                             'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; form-action 'self'"})
        if config.HTTPS: resp.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return resp

    def sessao_completa(resp, u):
        cookie(resp, 'exato_sessao', seguranca.assinar({'uid': u['id']}, config.SESSAO_HORAS * 3600), config.SESSAO_HORAS * 3600)
        resp.delete_cookie('exato_pre', path='/')

    # ------------------------------------------------------------ acesso
    @app.get('/saude')
    def saude(): return PlainTextResponse('ok')

    @app.get('/login', response_class=HTMLResponse)
    def login_tela(request: Request): return pagina(request, 'login.html', {'erro': ''})

    @app.post('/login')
    def login_envio(request: Request, email: str = Form(''), senha: str = Form(''), csrf: str = Form('')):
        if not csrf_ok(request, csrf): return pagina(request, 'login.html', {'erro': 'A página expirou. Tente de novo.'}, 400)
        falta = limite.bloqueado(ip(request), email)
        if falta: return pagina(request, 'login.html', {'erro': f'Muitas tentativas. Tente de novo em {max(1, falta // 60)} minuto(s).'}, 429)
        try: u = core.db_auth_login(email, senha)
        except ValueError:
            limite.falhou(ip(request), email); time.sleep(0.4)
            return pagina(request, 'login.html', {'erro': 'E-mail ou senha inválidos.'}, 401)
        limite.acertou(ip(request), email)
        etapa = 'codigo' if totp.ativo(u['id']) else ('config' if config.EXIGIR_2FA else '')
        resp = RedirectResponse('/situacao' if not etapa else ('/login/codigo' if etapa == 'codigo' else '/conta/2fa'), status_code=303)
        if etapa: cookie(resp, 'exato_pre', seguranca.assinar({'uid': u['id'], 'etapa': etapa}, 300), 300)
        else: sessao_completa(resp, u)
        return resp

    def pre(request):
        d = seguranca.verificar(request.cookies.get('exato_pre', ''))
        return d if d else None

    @app.get('/login/codigo', response_class=HTMLResponse)
    def codigo_tela(request: Request):
        if not pre(request): return RedirectResponse('/login', status_code=303)
        return pagina(request, 'codigo.html', {'erro': ''})

    @app.post('/login/codigo')
    def codigo_envio(request: Request, codigo: str = Form(''), csrf: str = Form('')):
        p = pre(request)
        if not p or p.get('etapa') != 'codigo' or not csrf_ok(request, csrf): return RedirectResponse('/login', status_code=303)
        u = core._auth_user_from_row(core.db_auth_get_user_by_id(p['uid']))
        chave_lim = f"uid{p['uid']}"
        falta = limite.bloqueado(ip(request), chave_lim)
        if falta: return pagina(request, 'codigo.html', {'erro': f'Muitas tentativas. Tente de novo em {max(1, falta // 60)} minuto(s).'}, 429)
        if not totp.conferir(p['uid'], codigo):
            limite.falhou(ip(request), chave_lim); log(u, 'LOGIN_FALHA', 'Código de verificação inválido')
            return pagina(request, 'codigo.html', {'erro': 'Código inválido ou já usado. Aguarde o próximo código do aplicativo.'}, 401)
        limite.acertou(ip(request), chave_lim); resp = RedirectResponse('/situacao', status_code=303); sessao_completa(resp, u); return resp

    @app.get('/conta/2fa', response_class=HTMLResponse)
    def config_2fa_tela(request: Request):
        p = pre(request); u = usuario(request)
        uid = u['id'] if u else (p['uid'] if p and p.get('etapa') == 'config' else None)
        if uid is None: return RedirectResponse('/login', status_code=303)
        info = core.db_auth_get_user_by_id(uid); email = info['email']
        seg = totp.preparar(uid)
        if seg is None: return RedirectResponse('/situacao', status_code=303)
        return pagina(request, 'config2fa.html', {'segredo': seg, 'uri': seguranca.uri_totp(seg, email), 'erro': ''}, user=u)

    @app.post('/conta/2fa')
    def config_2fa_envio(request: Request, codigo: str = Form(''), csrf: str = Form('')):
        p = pre(request); u = usuario(request)
        uid = u['id'] if u else (p['uid'] if p and p.get('etapa') == 'config' else None)
        if uid is None or not csrf_ok(request, csrf): return RedirectResponse('/login', status_code=303)
        if not totp.confirmar(uid, codigo):
            seg = totp.preparar(uid) or ''
            return pagina(request, 'config2fa.html', {'segredo': seg, 'uri': seguranca.uri_totp(seg, core.db_auth_get_user_by_id(uid)['email']) if seg else '', 'erro': 'Código inválido. Confira o código mostrado no aplicativo e tente de novo.'}, 400, user=u)
        usr = core._auth_user_from_row(core.db_auth_get_user_by_id(uid)); log(usr, '2FA_ATIVADO', 'Verificação em duas etapas ativada')
        resp = RedirectResponse('/situacao', status_code=303); sessao_completa(resp, usr); return resp

    @app.post('/sair')
    def sair(request: Request, csrf: str = Form('')):
        resp = RedirectResponse('/login', status_code=303); resp.delete_cookie('exato_sessao', path='/'); return resp

    @app.get('/')
    def raiz(): return RedirectResponse('/situacao', status_code=303)

    # ------------------------------------------------------------ empresas e certificados
    def empresas_lista():
        out = []
        for c in core.db_list_companies(5000):
            cid = re.sub(r'\D', '', str(c['cnpj'])); info = cofre.info(cid)
            out.append({'cnpj': cid, 'cnpj_fmt': core._format_cnpj(cid), 'nome': c.get('name') or cid, 'documentos': c.get('documents') or 0, 'certificado': info})
        return out

    @app.get('/empresas', response_class=HTMLResponse)
    def empresas(request: Request, ok: str = '', erro: str = ''):
        u, r = exigir(request)
        if r: return r
        return pagina(request, 'empresas.html', {'empresas': empresas_lista(), 'ok': ok, 'erro': erro, 'tela': 'empresas'}, user=u)

    @app.post('/empresas')
    def empresas_nova(request: Request, cnpj: str = Form(''), nome: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/empresas?erro=A+página+expirou.', status_code=303)
        d = re.sub(r'\D', '', cnpj)
        if len(d) != 14 or not core._is_valid_cnpj(d): return RedirectResponse('/empresas?erro=CNPJ+inválido.+Confira+os+14+dígitos.', status_code=303)
        core.db_register_company(d, nome.strip()); log(u, 'EMPRESA_CADASTRADA', d)
        return RedirectResponse('/empresas?ok=Empresa+cadastrada.', status_code=303)

    @app.get('/certificados', response_class=HTMLResponse)
    def certificados(request: Request, ok: str = '', erro: str = ''):
        u, r = exigir(request)
        if r: return r
        emp = empresas_lista(); nomes = {e['cnpj']: f"{e['nome']} — {e['cnpj_fmt']}" for e in emp}
        certs = [dict(c, nome=nomes.get(c.get('id'), 'Escritório (certificado com procuração)' if c.get('id') == 'escritorio' else c.get('id'))) for c in cofre.listar()]
        return pagina(request, 'certificados.html', {'empresas': emp, 'certs': certs, 'ok': ok, 'erro': erro, 'tela': 'certificados'}, user=u)

    @app.post('/certificados')
    async def certificado_enviar(request: Request, empresa: str = Form(''), senha: str = Form(''), csrf: str = Form(''), arquivo: UploadFile = File(None)):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/certificados?erro=A+página+expirou.', status_code=303)
        dados = await arquivo.read(5 * 1024 * 1024 + 1) if arquivo else b''
        if not dados or len(dados) > 5 * 1024 * 1024: return RedirectResponse('/certificados?erro=Escolha+o+arquivo+do+certificado+A1+(.pfx+ou+.p12).', status_code=303)
        try: info = cofre.guardar(empresa, dados, senha, enviado_por=u.get('email', ''))
        except CofreErro as e:
            from urllib.parse import quote
            return RedirectResponse('/certificados?erro=' + quote(str(e)), status_code=303)
        log(u, 'CERTIFICADO_ENVIADO', f"{info['id']} titular {info['titular'][:60]} validade {info['validade']}")
        return RedirectResponse('/certificados?ok=Certificado+guardado+com+segurança.', status_code=303)

    @app.post('/certificados/remover')
    def certificado_remover(request: Request, empresa: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/certificados?erro=A+página+expirou.', status_code=303)
        try: cofre.remover(empresa); log(u, 'CERTIFICADO_REMOVIDO', str(empresa)[:20])
        except CofreErro: pass
        return RedirectResponse('/certificados?ok=Certificado+removido.', status_code=303)

    # ------------------------------------------------------------ situação da busca e documentos
    @app.get('/situacao', response_class=HTMLResponse)
    def situacao_tela(request: Request):
        u, r = exigir(request)
        if r: return r
        cfg = core.load_config(); oc = motivos.ultimas(str(core.DB_PATH)); linhas = situacao.linhas(str(core.DB_PATH), cfg, None, ocorrencias=oc, diagnostico={}, acessos=dict(cfg.get('nfse_acesso') or {}))
        for l in linhas: l['cnpj_fmt'] = core._format_cnpj(l['cnpj']); l['certificado'] = cofre.info(l['cnpj'])
        return pagina(request, 'situacao.html', {'linhas': linhas, 'totais': situacao.totais(linhas), 'tipos': situacao.TIPOS, 'tela': 'situacao'}, user=u)

    @app.get('/documentos', response_class=HTMLResponse)
    def documentos(request: Request, empresa: str = '', tipo: str = '', mov: str = '', q: str = ''):
        u, r = exigir(request)
        if r: return r
        rows = core.db_list_documents(cnpj=empresa, family=tipo, direction=mov, query=q, limit=300, with_xml=False)
        rows = [x for x in rows if x.get('status') != 'Evento']
        docs = [{'id': x['doc_id'], 'tipo': ROTULOS_TIPO.get(str(x.get('family') or '').lower(), x.get('doc_type') or ''), 'numero': x.get('number') or '', 'empresa': x.get('company_name') or x.get('cnpj'),
                 'mov': x.get('direction') or '', 'data': str(x.get('issued_at') or '')[:10], 'valor': x.get('value') or '', 'situacao': x.get('status') or ''} for x in rows]
        return pagina(request, 'documentos.html', {'docs': docs, 'empresas': empresas_lista(), 'f': {'empresa': empresa, 'tipo': tipo, 'mov': mov, 'q': q}, 'tela': 'documentos'}, user=u)

    @app.get('/documentos/{doc_id}/xml')
    def documento_xml(request: Request, doc_id: str):
        u, r = exigir(request)
        if r: return r
        con = sqlite3.connect(str(core.DB_PATH), timeout=15)
        try: row = con.execute('SELECT xml, number, family FROM documents WHERE doc_id=?', (doc_id,)).fetchone()
        finally: con.close()
        if not row or not row[0]: return PlainTextResponse('Documento não encontrado.', status_code=404)
        xml = row[0] if isinstance(row[0], bytes) else str(row[0]).encode('utf-8'); log(u, 'XML_BAIXADO', str(doc_id)[:60])
        return Response(xml, media_type='application/xml', headers={'Content-Disposition': f'attachment; filename="{re.sub(r"[^0-9A-Za-z_.-]", "_", str(doc_id))[:80]}.xml"'})

    return app
