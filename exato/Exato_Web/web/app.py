"""Exato Web — site do escritório. Rotas, sessão e telas. A lógica fiscal vem do código do Exato (web.nucleo); aqui só há acesso, cofre e apresentação."""
import re, secrets, sqlite3, time
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, PlainTextResponse, FileResponse
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auditoria as aud, backup, exatinho as exa, exatinho_log as exalog, exportar as exp, nfse_conferencia as nfc, config, manifestacao as manif, nucleo, relatorios as rel, seguranca
from .agendador import Agendador
from .busca import Motor
from .cofre import Cofre, CofreErro, carregar_chave_mestra

AQUI = Path(__file__).resolve().parent
ROTULOS_TIPO = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}


def criar_app(importador=None, iniciar_agendador=False, nfse_transport=None, manif_transporte=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)          # sem página de documentação técnica exposta na internet
    app.mount('/static', StaticFiles(directory=str(AQUI / 'static')), name='static')

    @app.exception_handler(Exception)
    async def erro_inesperado(request: Request, exc: Exception):
        """Nenhuma tela mostra "Internal Server Error": mensagem em português, com a causa mais provável, e o detalhe vai para o registro de erros."""
        try: nucleo.core().log_exception(f'Web: erro em {request.url.path}', (type(exc), exc, exc.__traceback__))
        except Exception: pass
        disco = isinstance(exc, (sqlite3.OperationalError, OSError)) and any(k in str(exc).lower() for k in ('full', 'space', 'espaco', 'no space', 'disk'))
        causa = 'O disco do servidor parece estar cheio. Libere espaço no C: e tente de novo.' if disco else 'Algo deu errado do nosso lado. Tente de novo; se continuar, avise quem cuida do site e diga o que você estava fazendo.'
        corpo = ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Algo deu errado — Exato</title>'
                 '<body style="font-family:system-ui,Segoe UI,Arial;background:#f3f5fa;color:#0f172a;display:grid;place-items:center;min-height:100vh;margin:0"><div style="max-width:460px;background:#fff;border:1px solid #e2e8f2;border-radius:16px;padding:28px;box-shadow:0 8px 24px rgba(15,23,42,.08)">'
                 '<h1 style="margin:0 0 8px;font-size:22px">Algo deu errado</h1><p style="margin:0 0 16px;color:#334155;line-height:1.5">' + causa + '</p><a href="/situacao" style="display:inline-block;background:#e11d2e;color:#fff;padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:600">Voltar ao início</a></div></body></html>')
        return HTMLResponse(corpo, status_code=500)
    tpl = Jinja2Templates(directory=str(AQUI / 'templates'))
    core = nucleo.core()
    pasta_cofre = config.DADOS / 'cofre'
    chave = carregar_chave_mestra(pasta_cofre)
    cofre = Cofre(pasta_cofre, chave, importador=importador)
    totp = seguranca.Totp(config.DADOS / 'web.db', chave)
    limite = seguranca.LimiteLogin(); sessoes = seguranca.Sessoes(config.DADOS / 'web.db'); dispositivos = seguranca.Dispositivos(config.DADOS / 'web.db')
    app.state.cofre, app.state.totp, app.state.limite, app.state.core, app.state.sessoes, app.state.dispositivos = cofre, totp, limite, core, sessoes, dispositivos
    motor = Motor(core, cofre, nfse_transport=nfse_transport); motor.manifestador = manif.Manifestador(core, cofre, motor.certificado_para, transporte=manif_transporte); agendador = Agendador(motor); app.state.motor, app.state.agendador = motor, agendador
    if iniciar_agendador: agendador.iniciar()
    motivos = nucleo.modulo('exato_busca_motivos'); situacao = nucleo.modulo('exato_situacao_busca')

    # ------------------------------------------------------------ ajudantes
    def ip(request): return (request.client.host if request.client else '') or ''

    def cookie(resp, nome, valor, segundos, http_only=True):
        resp.set_cookie(nome, valor, max_age=segundos, httponly=http_only, samesite='strict', secure=config.HTTPS, path='/')

    def usuario(request):
        d = seguranca.verificar(request.cookies.get('exato_sessao', ''))
        if not d or sessoes.usuario(d.get('sid')) != d.get('uid'): return None          # sessão encerrada no servidor (sair, troca de senha) não vale mais
        u = core.db_auth_get_user_by_id(d.get('uid'))
        return core._auth_user_from_row(u) if u and str(u.get('status')) == 'active' else None

    def csrf_do_pedido(request): return request.cookies.get('exato_csrf') or secrets.token_urlsafe(24)

    def pagina(request, nome, ctx=None, status=200, user=None):
        c = dict(ctx or {}); tk = csrf_do_pedido(request)
        c.update({'request': request, 'csrf': tk, 'usuario': user, 'rotulos': ROTULOS_TIPO, 'asset_v': int(max((f.stat().st_mtime for f in (AQUI / 'static').iterdir() if f.is_file()), default=0))})
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
        if request.url.path.startswith('/static/'): resp.headers['Cache-Control'] = 'no-cache'          # o navegador confere se o arquivo mudou (depois de uma atualização do site, nada de visual antigo)
        return resp

    def sessao_completa(resp, u, horas=None):
        horas = horas or config.SESSAO_HORAS; sid = sessoes.criar(u['id'], horas * 3600)
        cookie(resp, 'exato_sessao', seguranca.assinar({'uid': u['id'], 'sid': sid}, horas * 3600), horas * 3600)
        resp.delete_cookie('exato_pre', path='/')

    def dispositivo_confiavel(request, uid):
        """True se este navegador foi marcado como "confiar por N dias" por esta pessoa (e ainda vale no servidor)."""
        d = seguranca.verificar(request.cookies.get('exato_confiavel', ''))
        return bool(d and d.get('uid') == uid and dispositivos.valido(d.get('t'), uid))

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
        if etapa == 'codigo' and dispositivo_confiavel(request, u['id']):          # computador marcado como confiável: só a senha
            resp = RedirectResponse('/situacao', status_code=303); log(u, 'LOGIN_DISPOSITIVO_CONFIAVEL', 'Entrou sem pedir o código (computador confiável)'); sessao_completa(resp, u, config.SESSAO_HORAS_CONFIAVEL); return resp
        resp = RedirectResponse('/situacao' if not etapa else ('/login/codigo' if etapa == 'codigo' else '/conta/2fa'), status_code=303)
        if etapa: cookie(resp, 'exato_pre', seguranca.assinar({'uid': u['id'], 'etapa': etapa}, 300), 300)
        else: sessao_completa(resp, u)
        return resp

    def qr_svg(uri):
        """QR code (SVG) para o aplicativo autenticador ler com a câmera; sem o pacote, a tela só mostra a chave."""
        try:
            import segno
            return segno.make(uri, error='m').svg_inline(scale=5, border=2, dark='#0F172A', light='#FFFFFF')
        except Exception: return ''

    def pre(request):
        d = seguranca.verificar(request.cookies.get('exato_pre', ''))
        return d if d else None

    @app.get('/login/codigo', response_class=HTMLResponse)
    def codigo_tela(request: Request):
        if not pre(request): return RedirectResponse('/login', status_code=303)
        return pagina(request, 'codigo.html', {'erro': '', 'dias': config.DISPOSITIVO_DIAS})

    @app.post('/login/codigo')
    def codigo_envio(request: Request, codigo: str = Form(''), confiar: str = Form(''), csrf: str = Form('')):
        p = pre(request)
        if not p or p.get('etapa') != 'codigo' or not csrf_ok(request, csrf): return RedirectResponse('/login', status_code=303)
        u = core._auth_user_from_row(core.db_auth_get_user_by_id(p['uid']))
        chave_lim = f"uid{p['uid']}"
        falta = limite.bloqueado(ip(request), chave_lim)
        if falta: return pagina(request, 'codigo.html', {'erro': f'Muitas tentativas. Tente de novo em {max(1, falta // 60)} minuto(s).', 'dias': config.DISPOSITIVO_DIAS}, 429)
        if not totp.conferir(p['uid'], codigo):
            limite.falhou(ip(request), chave_lim); log(u, 'LOGIN_FALHA', 'Código de verificação inválido')
            return pagina(request, 'codigo.html', {'erro': 'Código inválido ou já usado. Aguarde o próximo código do aplicativo.', 'dias': config.DISPOSITIVO_DIAS}, 401)
        limite.acertou(ip(request), chave_lim); resp = RedirectResponse('/situacao', status_code=303)
        if confiar == '1':          # "confiar neste computador": guarda um identificador (só o hash fica no servidor) e a sessão dura mais
            token = dispositivos.criar(u['id'], config.DISPOSITIVO_DIAS)
            cookie(resp, 'exato_confiavel', seguranca.assinar({'uid': u['id'], 't': token}, config.DISPOSITIVO_DIAS * 86400), config.DISPOSITIVO_DIAS * 86400); log(u, 'DISPOSITIVO_CONFIAVEL', f'Computador marcado como confiável por {config.DISPOSITIVO_DIAS} dias')
            sessao_completa(resp, u, config.SESSAO_HORAS_CONFIAVEL)
        else: sessao_completa(resp, u)
        return resp

    @app.get('/conta/2fa', response_class=HTMLResponse)
    def config_2fa_tela(request: Request):
        p = pre(request); u = usuario(request)
        uid = u['id'] if u else (p['uid'] if p and p.get('etapa') == 'config' else None)
        if uid is None: return RedirectResponse('/login', status_code=303)
        info = core.db_auth_get_user_by_id(uid); email = info['email']
        seg = totp.preparar(uid)
        if seg is None: return RedirectResponse('/situacao', status_code=303)
        return pagina(request, 'config2fa.html', {'segredo': seg, 'uri': seguranca.uri_totp(seg, email), 'qr': qr_svg(seguranca.uri_totp(seg, email)), 'erro': ''}, user=u)

    @app.post('/conta/2fa')
    def config_2fa_envio(request: Request, codigo: str = Form(''), csrf: str = Form('')):
        p = pre(request); u = usuario(request)
        uid = u['id'] if u else (p['uid'] if p and p.get('etapa') == 'config' else None)
        if uid is None or not csrf_ok(request, csrf): return RedirectResponse('/login', status_code=303)
        if not totp.confirmar(uid, codigo):
            seg = totp.preparar(uid) or ''
            return pagina(request, 'config2fa.html', {'segredo': seg, 'uri': seguranca.uri_totp(seg, core.db_auth_get_user_by_id(uid)['email']) if seg else '', 'qr': qr_svg(seguranca.uri_totp(seg, core.db_auth_get_user_by_id(uid)['email'])) if seg else '', 'erro': 'Código inválido. Confira o código mostrado no aplicativo e tente de novo.'}, 400, user=u)
        usr = core._auth_user_from_row(core.db_auth_get_user_by_id(uid)); log(usr, '2FA_ATIVADO', 'Verificação em duas etapas ativada')
        resp = RedirectResponse('/situacao', status_code=303); sessao_completa(resp, usr); return resp

    @app.post('/sair')
    def sair(request: Request, csrf: str = Form(''), esquecer: str = Form('')):
        d = seguranca.verificar(request.cookies.get('exato_sessao', ''))
        if d: sessoes.revogar(d.get('sid'))
        resp = RedirectResponse('/login', status_code=303); resp.delete_cookie('exato_sessao', path='/')
        if esquecer == '1':          # "sair e esquecer este computador": o código do celular volta a ser pedido aqui
            t = seguranca.verificar(request.cookies.get('exato_confiavel', ''))
            if t: dispositivos.revogar(t.get('t'))
            resp.delete_cookie('exato_confiavel', path='/')
        return resp

    @app.get('/')
    def raiz(): return RedirectResponse('/situacao', status_code=303)

    # ------------------------------------------------------------ empresas e certificados
    def empresas_lista():
        motor.reaplicar_nomes(); out = []
        for c in core.db_list_companies(5000):
            cid = re.sub(r'\D', '', str(c['cnpj'])); info = cofre.info(cid); man = motor.nome_manual(cid)
            out.append({'cnpj': cid, 'cnpj_fmt': core._format_cnpj(cid), 'nome': man or c.get('name') or cid, 'documentos': c.get('documents') or 0, 'certificado': info, 'manual': bool(man)})
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

    @app.get('/empresas/editar', response_class=HTMLResponse)
    def empresas_editar_tela(request: Request, cnpj: str = '', erro: str = ''):
        u, r = exigir(request)
        if r: return r
        d = re.sub(r'\D', '', cnpj); e = next((x for x in empresas_lista() if x['cnpj'] == d), None)
        if not e: return RedirectResponse(_msg('/empresas', 'erro', 'Empresa não encontrada.'), status_code=303)
        try: nome_notas, verificado = core.db_company_verified_name(d)
        except Exception: nome_notas, verificado = '', False
        motor.reaplicar_nomes()
        return pagina(request, 'empresa_editar.html', {'e': e, 'nome_notas': nome_notas if verificado else '', 'erro': erro, 'tela': 'empresas'}, user=u)

    @app.post('/empresas/editar')
    def empresas_editar(request: Request, cnpj: str = Form(''), nome: str = Form(''), confirmo: str = Form(''), csrf: str = Form('')):
        """Muda o nome da empresa (o CNPJ nunca muda). O nome que as notas trazem só é trocado com confirmação; a pasta do Repositório acompanha o nome novo."""
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/empresas?erro=A+página+expirou.', status_code=303)
        d = re.sub(r'\D', '', cnpj); novo = re.sub(r'\s+', ' ', re.sub(r'[\x00-\x1f]', ' ', nome)).strip()
        if len(d) != 14 or d not in {re.sub(r'\D', '', str(c['cnpj'])) for c in core.db_list_companies(5000)}: return RedirectResponse(_msg('/empresas', 'erro', 'Empresa não encontrada.'), status_code=303)
        if len(novo) < 3 or len(novo) > 120: return RedirectResponse(_msg('/empresas', 'erro', 'O nome precisa ter de 3 a 120 letras.'), status_code=303)
        antigo = motor.nome_manual(d) or core.db_get_company_name(d) or ''
        try: do_xml, verificado = core.db_company_verified_name(d)
        except Exception: do_xml, verificado = '', False
        if verificado and do_xml and do_xml.casefold() != novo.casefold() and not motor.nome_manual(d) and not confirmo:
            return RedirectResponse(_msg('/empresas', 'erro', f'As notas desta empresa trazem o nome "{do_xml}". Para usar "{novo}" mesmo assim (a empresa mudou de nome), marque a confirmação e salve de novo.'), status_code=303)
        if not core.db_set_company_name(d, novo): return RedirectResponse(_msg('/empresas', 'erro', 'Esse nome não pode ser usado.'), status_code=303)
        motor.cfg.setdefault('nomes_manuais', {})[d] = {'nome': novo, 'em': time.strftime('%Y-%m-%dT%H:%M:%S'), 'por': u.get('email', '')}; motor.salvar_cfg()
        log(u, 'EMPRESA_EDITADA', f'{d}: {antigo} -> {novo}'[:200])
        if motor.repo_cfg()['auto'] and not motor.estado_repo['copiando']:          # a pasta do servidor é renomeada (ou unida à antiga) na próxima cópia; nada é apagado
            import threading; threading.Thread(target=motor.copiar_repositorio, kwargs={'ignorar_pausa': True}, daemon=True, name='repositorio').start()
        return RedirectResponse(_msg('/empresas', 'ok', 'Nome atualizado. A pasta da empresa no servidor acompanha o nome novo na próxima cópia para a pasta de arquivos.'), status_code=303)

    @app.post('/empresas/restaurar-nome')
    def empresas_restaurar(request: Request, cnpj: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        d = re.sub(r'\D', '', cnpj)
        if csrf_ok(request, csrf) and len(d) == 14 and (motor.cfg.get('nomes_manuais') or {}).pop(d, None) is not None:
            motor.salvar_cfg()
            try: core.db_company_verified_name(d)          # volta ao nome que as notas trazem
            except Exception: pass
            log(u, 'EMPRESA_NOME_RESTAURADO', d)
        return RedirectResponse(_msg('/empresas', 'ok', 'Voltou ao nome que as notas trazem.'), status_code=303)

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
        cfg = motor.cfg; oc = motivos.ultimas(str(core.DB_PATH)); linhas = situacao.linhas(str(core.DB_PATH), cfg, None, ocorrencias=oc, diagnostico={}, acessos=dict(cfg.get('nfse_acesso') or {}))
        for l in linhas: l['cnpj_fmt'] = core._format_cnpj(l['cnpj']); l['certificado'] = cofre.info(l['cnpj'])
        return pagina(request, 'situacao.html', {'backup_aviso': (backup.aviso(motor.cfg) if u.get('role') == 'admin' else ''), 'linhas': linhas, 'totais': situacao.totais(linhas), 'tipos': situacao.TIPOS, 'tela': 'situacao', 'rodando': bool(motor.estado['rodando']), 'auto': agendador.ligado(), 'proxima': agendador.proxima()}, user=u)

    @app.get('/documentos', response_class=HTMLResponse)
    def documentos(request: Request, empresa: str = '', tipo: str = '', mov: str = '', q: str = '', desde: str = ''):
        u, r = exigir(request)
        if r: return r
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', desde or ''):          # "as notas novas desta busca": guardadas a partir de um instante
            d14 = re.sub(r'\D', '', empresa); con = sqlite3.connect(str(core.DB_PATH), timeout=30); con.row_factory = sqlite3.Row
            try:
                sql = "SELECT d.doc_id, d.family, d.doc_type, d.number, d.cnpj, COALESCE(c.name,d.cnpj) AS company_name, d.direction, d.issued_at, d.value, d.status FROM documents d LEFT JOIN companies c ON c.cnpj=d.cnpj WHERE d.first_seen_at>=? AND COALESCE(d.status,'')<>'Evento'"; args = [desde]
                if len(d14) == 14: sql += ' AND d.cnpj=?'; args.append(d14)
                if tipo in ROTULOS_TIPO: sql += ' AND d.family=?'; args.append(tipo)
                if mov in ('Entrada', 'Saída'): sql += ' AND d.direction=?'; args.append(mov)
                rows = [dict(x) for x in con.execute(sql + ' ORDER BY d.issued_at DESC LIMIT 300', args)]
            finally: con.close()
        else:
            desde = ''; rows = core.db_list_documents(cnpj=empresa, family=tipo, direction=mov, query=q, limit=300, with_xml=False)
            rows = [x for x in rows if x.get('status') != 'Evento']
        docs = [{'id': x['doc_id'], 'tipo': ROTULOS_TIPO.get(str(x.get('family') or '').lower(), x.get('doc_type') or ''), 'numero': x.get('number') or '', 'empresa': x.get('company_name') or x.get('cnpj'),
                 'mov': x.get('direction') or '', 'data': str(x.get('issued_at') or '')[:10], 'valor': x.get('value') or '', 'situacao': x.get('status') or '', 'pdf': str(x.get('family') or '').lower() in ROTULOS_TIPO} for x in rows]
        return pagina(request, 'documentos.html', {'docs': docs, 'empresas': empresas_lista(), 'f': {'empresa': empresa, 'tipo': tipo, 'mov': mov, 'q': q, 'desde': desde}, 'tela': 'documentos'}, user=u)

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

    @app.get('/documentos/{doc_id}/pdf')
    def documento_pdf(request: Request, doc_id: str):
        """Abre a nota em PDF (DANFE/DACTE/NFS-e) gerado na hora a partir do XML guardado. Nada é gravado: o arquivo temporário some depois de enviado."""
        u, r = exigir(request)
        if r: return r
        con = sqlite3.connect(str(core.DB_PATH), timeout=15)
        try: row = con.execute('SELECT xml, family, status, cnpj FROM documents WHERE doc_id=?', (doc_id,)).fetchone()
        finally: con.close()
        if not row or not row[0]: return PlainTextResponse('Documento não encontrado.', status_code=404)
        xml = row[0] if isinstance(row[0], bytes) else str(row[0]).encode('utf-8'); fam = str(row[1] or '').lower(); status = str(row[2] or ''); cnpj = str(row[3] or '')
        if status == 'Evento': return PlainTextResponse('Evento não tem PDF: baixe o XML.', status_code=400)
        if fam not in ROTULOS_TIPO: return PlainTextResponse('Este tipo de documento não tem PDF.', status_code=400)
        if len(xml) > 8 * 1024 * 1024: return PlainTextResponse('O XML é grande demais para gerar o PDF aqui.', status_code=413)
        import tempfile
        from starlette.background import BackgroundTask
        tmp = tempfile.NamedTemporaryFile(prefix='exato_pdf_', suffix='.pdf', dir=str(config.DADOS), delete=False); tmp.close()
        try:
            logo = core.LOGO_PATH if getattr(core, 'LOGO_PATH', None) and Path(core.LOGO_PATH).exists() else None
            if fam == 'nfse':
                nucleo.modulo('exato_nfse_pdf').generate_nfse_pdf([{'xml': xml, 'cnpj': cnpj, 'situacao': 'Cancelada' if status == 'Cancelado' else 'Autorizada'}], tmp.name, core.db_get_company_name(cnpj) or '', logo)
            else:
                core.generate_fiscal_representation_pdf([{'xml': xml, 'family': fam}], tmp.name, fam)
        except Exception:
            Path(tmp.name).unlink(missing_ok=True)
            try: core.log_exception('Web: PDF da nota', __import__('sys').exc_info())
            except Exception: pass
            return PlainTextResponse('Não foi possível gerar o PDF desta nota. O XML continua disponível para baixar.', status_code=500)
        log(u, 'PDF_ABERTO', str(doc_id)[:60])
        return FileResponse(tmp.name, media_type='application/pdf', headers={'Content-Disposition': 'inline; filename="nota.pdf"'}, background=BackgroundTask(lambda: Path(tmp.name).unlink(missing_ok=True)))

    # ------------------------------------------------------------ Exatinho (assistente local: situação da busca e dúvidas de uso)
    def exa_linhas():
        cfg = motor.cfg; oc = motivos.ultimas(str(core.DB_PATH)); esc = cofre.info('escritorio'); esc_ok = bool(esc and not esc.get('vencido'))
        out = situacao.linhas(str(core.DB_PATH), cfg, None, ocorrencias=oc, diagnostico={}, acessos=dict(cfg.get('nfse_acesso') or {}))
        for l in out: l['certificado'] = cofre.info(l['cnpj']); l['cert_escritorio'] = esc_ok
        return out

    def exa_dados():
        def certs():
            lista = []
            for e in empresas_lista():
                i = e.get('certificado')
                if i: lista.append({'nome': e['nome'], 'validade': i.get('validade'), 'vencido': bool(i.get('vencido'))})
            i = cofre.info('escritorio')
            if i: lista.append({'nome': 'o certificado do escritório', 'validade': i.get('validade'), 'vencido': bool(i.get('vencido'))})
            return lista
        def sem_evento():
            por = {}
            for cn, _k in (core.db_canceladas_sem_evento() or []): por[cn] = por.get(cn, 0) + 1
            return [{'cnpj': cn, 'nome': core.db_get_company_name(cn) or cn, 'qtd': q} for cn, q in sorted(por.items(), key=lambda x: -x[1])]
        def novas_hoje():
            con = sqlite3.connect(str(core.DB_PATH), timeout=15)
            try: return con.execute("SELECT COUNT(*) FROM documents WHERE first_seen_at>=? AND COALESCE(status,'')<>'Evento'", (time.strftime('%Y-%m-%dT00:00:00'),)).fetchone()[0]
            finally: con.close()
        def contagem(cnpj, de, ate):
            con = sqlite3.connect(str(core.DB_PATH), timeout=30); out = {}
            try:
                sql = "SELECT family, status, COUNT(*) FROM documents WHERE COALESCE(status,'')<>'Evento' AND substr(COALESCE(NULLIF(issued_at,''),first_seen_at),1,10) BETWEEN ? AND ?"; args = [de, ate]
                if cnpj: sql += ' AND cnpj=?'; args.append(re.sub(r'\D', '', str(cnpj)))
                for fam, st, n in con.execute(sql + ' GROUP BY family, status', args):
                    d = out.setdefault(str(fam), {'aut': 0, 'canc': 0}); d['canc' if st == 'Cancelado' else 'aut'] += n
            finally: con.close()
            return out
        import datetime as _dt
        return {'empresas': lambda: [{'cnpj': e['cnpj'], 'name': e['nome']} for e in empresas_lista()], 'linhas': exa_linhas, 'hoje': _dt.date.today, 'certs': certs, 'canceladas_sem_evento': sem_evento,
                'novas_hoje': novas_hoje, 'auto_ligado': agendador.ligado, 'contagem': contagem}

    def csrf_cabecalho(request): return csrf_ok(request, request.headers.get('x-csrf', ''))

    @app.get('/exatinho/resumo')
    async def exatinho_resumo(request: Request):
        u, r = exigir(request)
        if r: return Response('{}', status_code=401, media_type='application/json')
        import json
        resp = await run_in_threadpool(lambda: exa.resposta_resumo(exa_dados(), u.get('name', '')))
        itens = [i for i in resp.get('lines', [])]
        resp['badge'] = sum(1 for l in itens if l.startswith('⚠')) + sum(1 for l in itens if not l.startswith('⚠') and 'em dia' not in l)
        resp['sugestoes'] = exa.sugestoes_iniciais()
        return Response(json.dumps(resp, ensure_ascii=False), media_type='application/json', headers={'Cache-Control': 'no-store'})

    @app.post('/exatinho/perguntar')
    async def exatinho_perguntar(request: Request):
        u, r = exigir(request)
        if r: return Response('{}', status_code=401, media_type='application/json')
        import json
        if not csrf_cabecalho(request): return Response(json.dumps({'erro': 'A página expirou. Recarregue.'}), status_code=403, media_type='application/json')
        try: corpo = await request.json()
        except Exception: corpo = {}
        q = str((corpo or {}).get('q') or '').strip()[:400]; ctx = (corpo or {}).get('ctx') if isinstance((corpo or {}).get('ctx'), dict) else {}
        ctx = {k: ctx[k] for k in ('company', 'topic', 'period') if k in ctx and isinstance(ctx[k], (str, list)) and len(str(ctx[k])) < 200}
        resp = await run_in_threadpool(lambda: exa.responder(q, exa_dados(), u.get('name', ''), ctx))
        try: resp['id'] = exalog.registrar(u.get('email', ''), q, resp.get('topic', ''), 'desconhecido' if resp.get('desconhecida') else 'ok')
        except Exception: resp['id'] = 0
        return Response(json.dumps(resp, ensure_ascii=False, default=str), media_type='application/json', headers={'Cache-Control': 'no-store'})

    @app.post('/exatinho/feedback')
    async def exatinho_feedback(request: Request):
        u, r = exigir(request)
        if r: return Response('{}', status_code=401, media_type='application/json')
        if not csrf_cabecalho(request): return Response('{}', status_code=403, media_type='application/json')
        try: corpo = await request.json(); exalog.feedback(int(corpo.get('id') or 0), bool(corpo.get('util')))
        except Exception: pass
        return Response('{"ok": true}', media_type='application/json')

    @app.post('/exatinho/acao')
    async def exatinho_acao(request: Request):
        """Executa uma ação que a pessoa CONFIRMOU no chat (só buscas; nunca apaga nada)."""
        u, r = exigir(request)
        if r: return Response('{}', status_code=401, media_type='application/json')
        import json
        if not csrf_cabecalho(request): return Response(json.dumps({'ok': False, 'msg': 'A página expirou. Recarregue.'}), status_code=403, media_type='application/json')
        try: corpo = await request.json()
        except Exception: corpo = {}
        a = (corpo or {}).get('acao') or {}; kind = str(a.get('kind') or ''); msg = ''; ok = False
        if kind == 'buscar':
            d = re.sub(r'\D', '', str(a.get('cnpj') or '')); tipos = tuple(t for t in (a.get('tipos') or list(ROTULOS_TIPO)) if t in ROTULOS_TIPO) or tuple(ROTULOS_TIPO)
            if len(d) != 14 or not core._is_valid_cnpj(d): msg = 'Empresa inválida.'
            elif not motor.certificado_para(d): msg = 'Esta empresa não tem certificado A1 guardado (nem o do escritório). Envie em Certificados A1.'
            elif agendador.disparar(only=[d], manual=True, tipos=tipos): ok = True; msg = 'Busca iniciada.'; log(u, 'BUSCA_EXATINHO', d)
            else: msg = 'Já existe uma busca em andamento. Espere terminar.'
        elif kind in ('buscar_pendentes', 'buscar_todas'):
            only = None if kind == 'buscar_todas' else await run_in_threadpool(pendentes)
            if only is not None and not only: msg = 'Não há empresas pendentes de busca.'
            elif agendador.disparar(only=only, manual=True): ok = True; msg = 'Busca iniciada.'; log(u, 'BUSCA_EXATINHO', kind)
            else: msg = 'Já existe uma busca em andamento. Espere terminar.'
        else: msg = 'Ação desconhecida.'
        return Response(json.dumps({'ok': ok, 'msg': msg}, ensure_ascii=False), media_type='application/json', headers={'Cache-Control': 'no-store'})

    @app.get('/exatinho/duvidas', response_class=HTMLResponse)
    def exatinho_duvidas(request: Request):
        u, r = exigir(request)
        if r: return r
        if u.get('role') != 'admin': return RedirectResponse('/situacao', status_code=303)
        from .exatinho_base import TOPICOS
        return pagina(request, 'exatinho_duvidas.html', {'lista': exalog.para_ensinar(200), 'res': exalog.resumo(), 'topicos': [(t['id'], t['titulo']) for t in TOPICOS], 'tela': 'exatinho'}, user=u)


    # ------------------------------------------------------------ cópia de segurança (só administrador)
    def _so_admin(request):
        u, r = exigir(request)
        if r: return None, r
        if u.get('role') != 'admin': return None, RedirectResponse('/situacao', status_code=303)
        return u, None

    @app.get('/backup', response_class=HTMLResponse)
    def backup_tela(request: Request, ok: str = '', erro: str = ''):
        u, r = _so_admin(request)
        if r: return r
        c = backup.cfg_de(motor.cfg); aviso_disco = ''; lista = []
        if str(c.get('destino') or '').strip():
            try: aviso_disco = backup.validar_destino(c['destino'])[1]
            except backup.BackupErro as e: aviso_disco = str(e)
            lista = backup.listar(c['destino'])
        return pagina(request, 'backup.html', {'c': c, 'lista': lista, 'aviso_disco': aviso_disco, 'rodando': backup.andamento['rodando'], 'etapa': backup.andamento['etapa'], 'ok': ok, 'erro': erro, 'dados': str(config.DADOS), 'tela': 'backup'}, user=u)

    @app.get('/backup/pastas')
    def backup_pastas(request: Request, caminho: str = ''):
        u, r = _so_admin(request)
        if r: return JSONResponse({'erro': 'Entre no site como administrador.'}, status_code=403)
        try: return JSONResponse(backup.listar_pastas(caminho), headers={'Cache-Control': 'no-store'})
        except backup.BackupErro as e: return JSONResponse({'erro': str(e)}, status_code=400, headers={'Cache-Control': 'no-store'})

    @app.post('/backup/salvar')
    def backup_salvar(request: Request, destino: str = Form(''), hora: str = Form('02:00'), manter: int = Form(7), ativo: str = Form(''), csrf: str = Form('')):
        u, r = _so_admin(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/backup', status_code=303)
        c = backup.cfg_de(motor.cfg)
        if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', hora or ''): return RedirectResponse(_msg('/backup', 'erro', 'Hora inválida. Use o formato 02:00.'), status_code=303)
        try: pasta, _a = backup.validar_destino(destino)
        except backup.BackupErro as e: return RedirectResponse(_msg('/backup', 'erro', str(e)), status_code=303)
        c.update(destino=str(pasta), hora=hora, manter=max(2, min(60, int(manter or 7))), ativo=(ativo == '1')); motor.salvar_cfg(); log(u, 'BACKUP_CONFIG', f"{'ligado' if c['ativo'] else 'desligado'} {c['destino']}")
        return RedirectResponse(_msg('/backup', 'ok', 'Configuração salva.' + (' A cópia diária está ligada.' if c['ativo'] else ' A cópia diária está desligada.')), status_code=303)

    @app.post('/backup/agora')
    def backup_agora(request: Request, csrf: str = Form('')):
        u, r = _so_admin(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/backup', status_code=303)
        if backup.andamento['rodando']: return RedirectResponse(_msg('/backup', 'erro', 'Já existe uma cópia em andamento.'), status_code=303)
        if not str(backup.cfg_de(motor.cfg).get('destino') or '').strip(): return RedirectResponse(_msg('/backup', 'erro', 'Salve primeiro a pasta de destino.'), status_code=303)
        import threading
        threading.Thread(target=motor.fazer_backup, kwargs={'por': u.get('email', '')}, daemon=True, name='backup-manual').start(); log(u, 'BACKUP_AGORA', '')
        return RedirectResponse(_msg('/backup', 'ok', 'Cópia iniciada. Esta página se atualiza sozinha.'), status_code=303)

    # ------------------------------------------------------------ exportar XMLs em ZIP (com os eventos das notas)
    @app.get('/exportar', response_class=HTMLResponse)
    def exportar_tela(request: Request, empresa: str = '', de: str = '', ate: str = '', tipo: str = '', mov: str = '', desde: str = '', erro: str = '', ok: str = ''):
        u, r = exigir(request)
        if r: return r
        return pagina(request, 'exportar.html', {'empresas': empresas_lista(), 'jobs': exp.recentes(20), 'f': {'empresa': re.sub(r'\D', '', empresa), 'de': de, 'ate': ate, 'tipo': tipo if tipo in ROTULOS_TIPO else '', 'mov': mov, 'desde': desde},
                                                 'tipos_exp': list(ROTULOS_TIPO.items()), 'erro': erro, 'ok': ok, 'tela': 'exportar'}, user=u)

    @app.post('/exportar')
    async def exportar_pedir(request: Request):
        u, r = exigir(request)
        if r: return r
        f = await request.form()
        if not csrf_ok(request, str(f.get('csrf') or '')): return RedirectResponse('/exportar', status_code=303)
        tipos = [t for t in f.getlist('tipo') if t in ROTULOS_TIPO] or None
        try: j = exp.pedir(str(f.get('empresa') or ''), str(f.get('de') or ''), str(f.get('ate') or ''), tipos, str(f.get('mov') or ''), str(f.get('formato') or 'organizado'), str(f.get('desde') or ''), u.get('email', ''))
        except exp.ExportarErro as e:
            return RedirectResponse(_msg('/exportar', 'erro', str(e)) + '&empresa=' + re.sub(r'\D', '', str(f.get('empresa') or '')), status_code=303)
        log(u, 'EXPORTAR_PEDIDO', f"{j['filtros']['empresa']} {j['filtros']['formato']} {j['id']}")
        return RedirectResponse(_msg('/exportar', 'ok', 'Gerando o ZIP. Quando ficar pronto, o botão Baixar aparece na lista.'), status_code=303)

    @app.get('/exportar/{jid}/zip')
    def exportar_zip(request: Request, jid: str):
        u, r = exigir(request)
        if r: return r
        p = exp.caminho_zip(jid); j = exp.ler(jid)
        if not p or not j: return PlainTextResponse('Arquivo não encontrado (ZIPs ficam disponíveis por 7 dias).', status_code=404)
        log(u, 'ZIP_BAIXADO', jid)
        fi = j['filtros']; nome = f"Exato_XML_{fi['empresa']}_{(fi['de'] or 'inicio')}_{(fi['ate'] or 'hoje')}.zip" if not fi.get('desde') else f"Exato_XML_{fi['empresa']}_notas_novas.zip"
        return FileResponse(str(p), media_type='application/zip', filename=nome)

    @app.get('/exportar/estado')
    def exportar_estado(request: Request, jid: str = ''):
        u, r = exigir(request)
        if r: return Response('{}', status_code=401, media_type='application/json')
        import json
        j = exp.ler(jid) or {}
        return Response(json.dumps({k: j.get(k) for k in ('estado', 'total', 'feito', 'notas', 'eventos', 'canceladas', 'sem_evento', 'erro')}, ensure_ascii=False), media_type='application/json', headers={'Cache-Control': 'no-store'})

    # ------------------------------------------------------------ busca
    def pendentes():
        cfg = motor.cfg; oc = motivos.ultimas(str(core.DB_PATH))
        return [l['cnpj'] for l in situacao.linhas(str(core.DB_PATH), cfg, None, ocorrencias=oc, diagnostico={}) if l['pendentes']]

    @app.post('/busca/agora')
    def busca_agora(request: Request, empresa: str = Form(''), pendentes_so: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/situacao', status_code=303)
        only = [empresa] if empresa else (pendentes() if pendentes_so else None)
        if only is not None and not only: return RedirectResponse('/situacao', status_code=303)
        if agendador.disparar(only=only, manual=True): log(u, 'BUSCA_PEDIDA', (empresa or ('pendentes' if pendentes_so else 'todas'))[:40])
        return RedirectResponse('/situacao', status_code=303)

    @app.post('/busca/cancelar')
    def busca_cancelar(request: Request, csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if csrf_ok(request, csrf): motor.cancelar(); log(u, 'BUSCA_CANCELADA', '')
        return RedirectResponse('/situacao', status_code=303)

    @app.post('/busca/auto')
    def busca_auto(request: Request, ligar: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if csrf_ok(request, csrf): agendador.definir(ligar == '1'); log(u, 'BUSCA_AUTOMATICA', 'ligada' if ligar == '1' else 'desligada')
        return RedirectResponse('/situacao', status_code=303)

    @app.get('/busca/estado')
    def busca_estado(request: Request):
        u, r = exigir(request)
        if r: return Response('{}', status_code=401, media_type='application/json')
        import json
        e = dict(motor.estado); e['progresso'] = core.busca_progresso_texto() if e.get('rodando') else ''; e['auto'] = agendador.ligado(); e['proxima'] = agendador.proxima(); e['andamento'] = motor.and_foto()
        return Response(json.dumps(e, ensure_ascii=False), media_type='application/json', headers={'Cache-Control': 'no-store'})

    # ------------------------------------------------------------ busca manual (uma empresa, tipos escolhidos)
    TIPOS_BUSCA = (('nfe', 'NF-e'), ('nfce', 'NFC-e'), ('cte', 'CT-e'), ('nfse', 'NFS-e'))

    @app.get('/buscar', response_class=HTMLResponse)
    def buscar_tela(request: Request, empresa: str = '', erro: str = '', ok: str = ''):
        u, r = exigir(request)
        if r: return r
        d = re.sub(r'\D', '', empresa); linha = None; resumo = None
        if len(d) == 14:
            cfg = motor.cfg; oc = motivos.ultimas(str(core.DB_PATH))
            for l in situacao.linhas(str(core.DB_PATH), cfg, None, ocorrencias=oc, diagnostico={}, acessos=dict(cfg.get('nfse_acesso') or {})):
                if l['cnpj'] == d: linha = l; l['cnpj_fmt'] = core._format_cnpj(d); l['certificado'] = cofre.info(d) or cofre.info('escritorio'); l['cert_proprio'] = bool(cofre.info(d))
        resumo = motor.estado.get('resumo') if not motor.estado.get('rodando') else None
        return pagina(request, 'buscar.html', {'empresas': empresas_lista(), 'sel': d, 'l': linha, 'tipos': situacao.TIPOS, 'tipos_busca': TIPOS_BUSCA, 'resumo': resumo, 'rodando': bool(motor.estado['rodando']), 'erro': erro, 'ok': ok, 'hoje': time.strftime('%Y-%m-%d'), 'tela': 'buscar'}, user=u)

    @app.post('/buscar/manual')
    async def buscar_manual(request: Request):
        u, r = exigir(request)
        if r: return r
        f = await request.form(); csrf = str(f.get('csrf') or '')
        if not csrf_ok(request, csrf): return RedirectResponse('/buscar', status_code=303)
        d = re.sub(r'\D', '', str(f.get('empresa') or ''))
        if len(d) != 14 or not core._is_valid_cnpj(d): return RedirectResponse(_msg('/buscar', 'erro', 'Escolha a empresa.'), status_code=303)
        tipos = tuple(t for t, _ in TIPOS_BUSCA if t in f.getlist('tipo'))
        if not tipos: return RedirectResponse(_msg('/buscar', 'erro', 'Marque pelo menos um tipo de nota.') + '&empresa=' + d, status_code=303)
        modo = str(f.get('modo') or 'continuar'); recomecar = modo == 'recomecar'; de = ate = None
        if modo == 'data':
            import datetime as _dt
            try: de = _dt.date.fromisoformat(str(f.get('de') or ''))
            except ValueError: return RedirectResponse(_msg('/buscar', 'erro', 'Informe a data inicial (a partir de quando buscar).') + '&empresa=' + d, status_code=303)
            try: ate = _dt.date.fromisoformat(str(f.get('ate'))) if str(f.get('ate') or '').strip() else None
            except ValueError: return RedirectResponse(_msg('/buscar', 'erro', 'A data final não é válida.') + '&empresa=' + d, status_code=303)
            if de > _dt.date.today(): return RedirectResponse(_msg('/buscar', 'erro', 'A data inicial não pode ser no futuro.') + '&empresa=' + d, status_code=303)
            if ate and ate < de: return RedirectResponse(_msg('/buscar', 'erro', 'A data final não pode ser antes da inicial.') + '&empresa=' + d, status_code=303)
        if recomecar and not f.get('confirmo'): return RedirectResponse(_msg('/buscar', 'erro', 'Para buscar desde o começo, marque a confirmação: pode demorar bastante.') + '&empresa=' + d, status_code=303)
        if not motor.certificado_para(d) and not cofre.info('escritorio'): return RedirectResponse(_msg('/buscar', 'erro', 'Esta empresa não tem certificado A1 guardado (nem o do escritório). Envie em Certificados A1.') + '&empresa=' + d, status_code=303)
        zip_formato = (str(f.get('zip_formato') or 'organizado') if str(f.get('zip_auto') or '') == '1' else None)
        if zip_formato not in (None, 'organizado', 'dominio'): zip_formato = 'organizado'
        if not agendador.disparar(only=[d], manual=True, tipos=tipos, recomecar=recomecar, de=de, ate=ate, zip_formato=zip_formato): return RedirectResponse(_msg('/buscar', 'erro', 'Já existe uma busca em andamento. Espere terminar ou cancele.') + '&empresa=' + d, status_code=303)
        log(u, 'BUSCA_MANUAL', f"{d} {','.join(tipos)} {modo}" + (f" {de}..{ate or ''}" if de else '') + (f' zip={zip_formato}' if zip_formato else ''))
        return RedirectResponse(_msg('/buscar', 'ok', 'Busca iniciada. O andamento aparece abaixo.') + '&empresa=' + d, status_code=303)

    # ------------------------------------------------------------ auditoria
    def _msg(url, tipo, texto):
        from urllib.parse import quote
        return f'{url}?{tipo}=' + quote(texto)

    @app.get('/auditoria', response_class=HTMLResponse)
    def auditoria_tela(request: Request, ok: str = '', erro: str = '', empresa: str = ''):
        u, r = exigir(request)
        if r: return r
        hoje = time.localtime(); ini_mes = time.mktime((hoje.tm_year, hoje.tm_mon, 1, 0, 0, 0, 0, 0, -1)) - 86400
        ant = time.localtime(ini_mes); import calendar
        ini = f'{ant.tm_year}-{ant.tm_mon:02d}-01'; fim = f'{ant.tm_year}-{ant.tm_mon:02d}-{calendar.monthrange(ant.tm_year, ant.tm_mon)[1]:02d}'
        return pagina(request, 'auditoria.html', {'empresas': empresas_lista(), 'hist': aud.historico(60, empresa), 'ok': ok, 'erro': erro, 'ini': ini, 'fim': fim, 'f_empresa': empresa, 'tela': 'auditoria'}, user=u)

    @app.post('/auditoria')
    async def auditoria_enviar(request: Request, empresa: str = Form(''), de: str = Form(''), ate: str = Form(''), tipo_nfe: str = Form(''), tipo_nfce: str = Form(''),
                               csrf: str = Form(''), arquivos: list[UploadFile] = File(default=[])):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse(_msg('/auditoria', 'erro', 'A página expirou. Tente de novo.'), status_code=303)
        arqs = [a for a in (arquivos or []) if a and a.filename]
        if not arqs or len(arqs) > aud.MAX_ARQUIVOS: return RedirectResponse(_msg('/auditoria', 'erro', f'Envie de 1 a {aud.MAX_ARQUIVOS} arquivos Excel (.xlsx) do SAT.'), status_code=303)
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix='exato_aud_', dir=str(config.DADOS)))
        try:
            caminhos = []
            for i, a in enumerate(arqs, 1):
                if not str(a.filename).lower().endswith('.xlsx'): return RedirectResponse(_msg('/auditoria', 'erro', f'"{a.filename}" não é um Excel (.xlsx) do SAT.'), status_code=303)
                dados = await a.read(aud.MAX_ARQUIVO + 1)
                if len(dados) > aud.MAX_ARQUIVO: return RedirectResponse(_msg('/auditoria', 'erro', f'"{a.filename}" é grande demais.'), status_code=303)
                p = tmp / f'sat_{i}.xlsx'; p.write_bytes(dados); caminhos.append(p)
            fams = [f for f, v in (('nfe', tipo_nfe), ('nfce', tipo_nfce)) if v]
            try: res = await run_in_threadpool(aud.auditar, empresa, caminhos, fams, de, ate, u.get('email', ''))
            except aud.AuditoriaErro as e: return RedirectResponse(_msg('/auditoria', 'erro', str(e)), status_code=303)
            log(u, 'AUDITORIA_FEITA', f"{res['id']} {res['status']}")
            return RedirectResponse('/auditoria/' + res['id'], status_code=303)
        finally:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)

    @app.get('/auditoria/{aid}', response_class=HTMLResponse)
    def auditoria_resultado(request: Request, aid: str, situacao: str = ''):
        u, r = exigir(request)
        if r: return r
        res = aud.ler(aid)
        if not res: return PlainTextResponse('Auditoria não encontrada.', status_code=404)
        linhas = [l for l in res['linhas'] if not situacao or l['situacao'] == situacao]
        return pagina(request, 'auditoria_resultado.html', {'a': res, 'rodando': bool(motor.estado['rodando']), 'linhas': linhas[:600], 'total_linhas': len(linhas), 'f_situacao': situacao, 'cnpj_fmt': core._format_cnpj(res['cnpj']), 'tela': 'auditoria'}, user=u)

    @app.get('/auditoria/{aid}/pdf')
    def auditoria_pdf(request: Request, aid: str):
        u, r = exigir(request)
        if r: return r
        p = aud.caminho_pdf(aid)
        if not p: return PlainTextResponse('Auditoria não encontrada.', status_code=404)
        log(u, 'AUDITORIA_PDF_BAIXADO', aid)
        return FileResponse(str(p), media_type='application/pdf', filename=p.name)

    def _tarefa_faltantes(aid, email):
        """Em segundo plano: busca só os XMLs que faltam e, se achou algum, refaz a auditoria com os mesmos Excels."""
        try:
            res = aud.ler(aid); cnpj = res['cnpj']; cid = motor.certificado_para(cnpj)
            motor.estado.update(empresa=res['empresa'], indice=1, total=1)
            if cid is None:
                aud.atualizar(aid, busca={'em': time.strftime('%Y-%m-%dT%H:%M:%S'), 'mensagem': 'Esta empresa não tem certificado A1 guardado no site (nem o do escritório). Envie o certificado na tela Certificados A1.', 'nova': ''}); return
            with cofre.usar(cid) as thumb: r = motor.buscar_faltantes(cnpj, res['faltantes'], thumb)
            total = len(res['faltantes']); restam = len(r.get('restam') or []); achadas = max(0, total - restam)
            partes = [f'{achadas} de {total} XML encontrado(s)' if not r.get('cancelado') else 'Busca cancelada']
            if restam: partes.append(f'{restam} ainda sem XML (a SEFAZ não entregou)')
            partes += r.get('esperar') or []; partes += r.get('erros') or []
            nova = ''
            if r.get('novos'):
                try: nova = aud.auditar(cnpj, aud.excels_guardados(aid), res['tipos'], res['periodo'][0], res['periodo'][1], email)['id']
                except Exception: nova = ''
            aud.atualizar(aid, busca={'em': time.strftime('%Y-%m-%dT%H:%M:%S'), 'mensagem': ' • '.join(partes), 'nova': nova})
        except Exception as exc:
            try: core.log_exception('Web: auditoria (buscar o que falta)', __import__('sys').exc_info())
            except Exception: pass
            aud.atualizar(aid, busca={'em': time.strftime('%Y-%m-%dT%H:%M:%S'), 'mensagem': 'A busca não foi concluída. O detalhe foi guardado no registro de erros.', 'nova': ''})
        finally:
            motor.estado.update(rodando=False, empresa=''); motor._trava.release()

    @app.post('/auditoria/{aid}/buscar-faltantes')
    def auditoria_buscar_faltantes(request: Request, aid: str, csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        res = aud.ler(aid)
        if not res: return PlainTextResponse('Auditoria não encontrada.', status_code=404)
        if csrf_ok(request, csrf) and res.get('faltantes') and motor.reservar():
            motor._cancelar.clear(); log(u, 'AUDITORIA_BUSCAR_FALTANTES', aid)
            import threading; threading.Thread(target=_tarefa_faltantes, args=(aid, u.get('email', '')), daemon=True, name='auditoria-busca').start()
        return RedirectResponse('/auditoria/' + aid, status_code=303)

    # ------------------------------------------------------------ repositório (XMLs em arquivos) e download em ZIP
    repo = nucleo.modulo('exato_repositorio')

    @app.get('/repositorio', response_class=HTMLResponse)
    def repositorio_tela(request: Request, ok: str = ''):
        u, r = exigir(request)
        if r: return r
        db = str(core.DB_PATH); linhas = []; falha_banco = ''
        try:
            res = repo.resumo(db); lista_mes = repo.por_empresa_mes(db)[:300]
        except (sqlite3.Error, OSError) as exc:          # disco cheio ou banco ocupado: a tela abre mesmo assim e explica
            res = {'total': 0, 'copiados': 0, 'fila': 0, 'diferentes': 0, 'erros': 0, 'ultima_copia': '', 'motivos': [], 'proxima_tentativa': ''}; lista_mes = []
            falha_banco = 'O banco não respondeu. Se o disco do servidor estiver cheio, libere espaço no C: e abra de novo.'
            try: core.log_exception('Web: tela do Repositório', __import__('sys').exc_info())
            except Exception: pass
        for cnpj, nome, mes, docs, copiados in lista_mes:
            linhas.append({'cnpj': cnpj, 'cnpj_fmt': core._format_cnpj(cnpj), 'nome': nome or cnpj, 'mes': mes, 'docs': docs, 'copiados': copiados, 'zip': bool(re.fullmatch(r'\d{4}-\d{2}', mes))})
        return pagina(request, 'repositorio.html', {'res': res, 'linhas': linhas, 'pasta': str(config.ARQUIVOS), 'copiando': bool(motor.estado_repo['copiando']), 'ultimo': motor.estado_repo.get('ultimo'), 'auto': motor.repo_cfg()['auto'], 'livre': motor.espaco_livre(), 'falha_banco': falha_banco, 'motivo': (motor.estado_repo.get('resultado') or {}).get('motivo') if isinstance(motor.estado_repo.get('resultado'), dict) else '', 'ok': ok, 'tela': 'repositorio'}, user=u)

    @app.post('/repositorio/copiar')
    def repositorio_copiar(request: Request, csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if csrf_ok(request, csrf) and not motor.estado_repo['copiando']:
            import threading; threading.Thread(target=motor.copiar_repositorio, kwargs={'ignorar_pausa': True}, daemon=True, name='repositorio').start(); log(u, 'REPOSITORIO_COPIAR', '')
        return RedirectResponse('/repositorio?ok=Copiando+os+XMLs+para+a+pasta+de+arquivos...', status_code=303)

    @app.post('/repositorio/auto')
    def repositorio_auto(request: Request, ligar: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if csrf_ok(request, csrf):
            motor.repo_cfg()['auto'] = (ligar == '1'); motor.salvar_cfg(); log(u, 'REPOSITORIO_AUTO', 'ligada' if ligar == '1' else 'desligada')
        return RedirectResponse(_msg('/repositorio', 'ok', 'Cópia automática ligada.' if ligar == '1' else 'Cópia automática desligada. Os XMLs ficam só no banco; use "Copiar agora" quando quiser.').replace('/repositorio?ok=', '/repositorio?ok='), status_code=303)

    @app.get('/repositorio/zip')
    def repositorio_zip(request: Request, empresa: str = '', mes: str = '', tipo: str = ''):
        """Antigo ZIP do mês: agora é o formulário de exportação já preenchido (período do mês), com os eventos das notas e o resumo do que foi gerado."""
        u, r = exigir(request)
        if r: return r
        d = re.sub(r'\D', '', empresa)
        if len(d) != 14 or not re.fullmatch(r'\d{4}-\d{2}', mes): return PlainTextResponse('Pedido inválido.', status_code=400)
        import calendar
        ano, m = int(mes[:4]), int(mes[5:])
        return RedirectResponse(f'/exportar?empresa={d}&de={mes}-01&ate={mes}-{calendar.monthrange(ano, m)[1]:02d}' + (f'&tipo={tipo}' if tipo in ROTULOS_TIPO else ''), status_code=303)


    # ------------------------------------------------------------ conferência e relatório mensal de NFS-e
    @app.get('/nfse', response_class=HTMLResponse)
    async def nfse_tela(request: Request, empresa: str = '', de: str = '', ate: str = '', erro: str = ''):
        u, r = exigir(request)
        if r: return r
        d = re.sub(r'\D', '', empresa); conf = None
        if len(d) == 14 and re.fullmatch(r'(\d{4}-\d{2}-\d{2})?', de) and re.fullmatch(r'(\d{4}-\d{2}-\d{2})?', ate):
            conf = await run_in_threadpool(nfc.conferir, d, de, ate)
        return pagina(request, 'nfse.html', {'empresas': empresas_lista(), 'sel': d, 'de': de, 'ate': ate, 'c': conf, 'erro': erro, 'tela': 'nfse'}, user=u)

    @app.post('/nfse/relatorio')
    def nfse_relatorio(request: Request, empresa: str = Form(''), de: str = Form(''), ate: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/nfse', status_code=303)
        try: j = rel.pedir_nfse(empresa, de, ate, u.get('email', ''))
        except rel.RelatorioErro as e: return RedirectResponse(_msg('/nfse', 'erro', str(e)), status_code=303)
        log(u, 'RELATORIO_NFSE_PEDIDO', j['id'])
        return RedirectResponse('/relatorios', status_code=303)

    # ------------------------------------------------------------ relatórios em PDF
    @app.get('/relatorios', response_class=HTMLResponse)
    def relatorios_tela(request: Request, erro: str = ''):
        u, r = exigir(request)
        if r: return r
        return pagina(request, 'relatorios.html', {'empresas': empresas_lista(), 'jobs': rel.recentes(30), 'erro': erro, 'tela': 'relatorios'}, user=u)

    @app.post('/relatorios')
    def relatorios_pedir(request: Request, empresa: str = Form(''), tipo: str = Form(''), mov: str = Form(''), de: str = Form(''), ate: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/relatorios', status_code=303)
        try: j = rel.pedir(empresa, tipo, mov, de, ate, u.get('email', ''))
        except rel.RelatorioErro as e:
            from urllib.parse import quote
            return RedirectResponse('/relatorios?erro=' + quote(str(e)), status_code=303)
        log(u, 'RELATORIO_PEDIDO', j['id'])
        return RedirectResponse('/relatorios', status_code=303)

    @app.get('/relatorios/{jid}/pdf')
    def relatorio_pdf(request: Request, jid: str):
        u, r = exigir(request)
        if r: return r
        p = rel.caminho_pdf(jid)
        if not p: return PlainTextResponse('Relatório não encontrado ou ainda sendo gerado.', status_code=404)
        j = rel.ler(jid); nome = re.sub(r'[^0-9A-Za-z_-]', '_', f"Relatorio_{j.get('empresa') or 'documentos'}_{j.get('periodo','')}")[:80] + '.pdf'
        log(u, 'RELATORIO_BAIXADO', jid)
        return FileResponse(str(p), media_type='application/pdf', filename=nome)

    # ------------------------------------------------------------ fechamento do mês e ZIPs da Domínio
    @app.get('/fechamento', response_class=HTMLResponse)
    def fechamento_tela(request: Request, ok: str = ''):
        u, r = exigir(request)
        if r: return r
        return pagina(request, 'fechamento.html', {'linhas': motor.fechamento_linhas()[:400], 'fechando': bool(motor.estado_fech['fechando']), 'cfg': motor.fechamento_cfg(), 'ok': ok, 'tela': 'fechamento',
                                                   'res': motor.estado_fech.get('resultado'), 'ultimo': motor.estado_fech.get('ultimo')}, user=u)

    @app.post('/fechamento/agora')
    def fechamento_agora(request: Request, csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if csrf_ok(request, csrf) and not motor.estado_fech['fechando']:
            import threading; threading.Thread(target=motor.fechar_meses, kwargs={'manual': True}, daemon=True, name='fechamento').start(); log(u, 'FECHAMENTO_AGORA', '')
        return RedirectResponse('/fechamento?ok=Fechando+os+meses+prontos...', status_code=303)

    @app.post('/fechamento/auto')
    def fechamento_auto(request: Request, ligar: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if csrf_ok(request, csrf): motor.fechamento_cfg()['ativo'] = (ligar == '1'); motor.salvar_cfg(); log(u, 'FECHAMENTO_AUTO', ligar)
        return RedirectResponse('/fechamento', status_code=303)

    @app.get('/fechamento/arquivo')
    def fechamento_arquivo(request: Request, empresa: str = '', mes: str = '', nome: str = ''):
        u, r = exigir(request)
        if r: return r
        d = re.sub(r'\D', '', empresa)
        if len(d) != 14 or not re.fullmatch(r'\d{4}-\d{2}', mes): return PlainTextResponse('Pedido inválido.', status_code=400)
        marca = motor.fechamento_info(d, mes, core.db_get_company_name(d) or '')
        permitidos = (set(marca.get('arquivos') or []) | {x for h in marca.get('historico') or [] for x in h.get('arquivos') or []}) if marca else set()          # inclui os arquivos das revisões anteriores
        if not marca or nome not in permitidos or '/' in nome or '\\' in nome: return PlainTextResponse('Arquivo não encontrado.', status_code=404)          # só o que o fechamento gravou
        p = motor.pasta_fechamento(d, mes, core.db_get_company_name(d) or '') / nome
        if not p.exists(): return PlainTextResponse('Arquivo não encontrado.', status_code=404)
        log(u, 'FECHAMENTO_BAIXADO', f'{d} {mes} {nome}'[:100])
        return FileResponse(str(p), filename=nome, media_type='application/pdf' if nome.lower().endswith('.pdf') else 'application/zip')

    # ------------------------------------------------------------ Box-e
    boxe = nucleo.modulo('exato_boxe')

    @app.get('/boxe', response_class=HTMLResponse)
    def boxe_tela(request: Request, ok: str = '', erro: str = '', etapas: str = ''):
        u, r = exigir(request)
        if r: return r
        import json as _j
        c = dict(motor.boxe_cfg()); c.pop('senha_protegida', None)
        return pagina(request, 'boxe.html', {'c': c, 'tem_senha': bool(motor.boxe_cfg().get('senha_protegida')), 'pronto': motor.boxe_pronto(), 'res': boxe.resumo(str(core.DB_PATH)), 'ok': ok, 'erro': erro,
                                             'resumo': motor.resumo_cfg(), 'etapas': _j.loads(etapas) if etapas else [], 'enviando': bool(motor.estado_boxe['enviando']), 'ultimo': motor.estado_boxe.get('resultado'), 'tela': 'boxe'}, user=u)

    @app.post('/boxe/salvar')
    def boxe_salvar(request: Request, destino: str = Form(''), servidor: str = Form(''), porta: str = Form('587'), seguranca_: str = Form('STARTTLS'), usuario_: str = Form(''), senha: str = Form(''),
                    remetente: str = Form(''), tomadas: str = Form(''), antigas: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse(_msg('/boxe', 'erro', 'A página expirou.'), status_code=303)
        aviso = boxe.conferir_servidor(servidor)
        if aviso: return RedirectResponse(_msg('/boxe', 'erro', aviso), status_code=303)
        try: pt = int(porta)
        except ValueError: return RedirectResponse(_msg('/boxe', 'erro', 'A porta deve ser um número (por exemplo 587).'), status_code=303)
        c = motor.boxe_cfg(); c.update({'destino': destino.strip() or boxe.DESTINO_PADRAO, 'servidor': servidor.strip(), 'porta': pt, 'seguranca': seguranca_ if seguranca_ in ('STARTTLS', 'SSL', 'NENHUMA') else 'STARTTLS',
                                        'usuario': usuario_.strip(), 'remetente': remetente.strip(), 'tomadas': bool(tomadas)})
        if senha: c['senha_protegida'] = cofre.proteger_texto(senha)          # a senha nunca é mostrada de novo
        if not antigas and not c.get('desde'): c['desde'] = time.strftime('%Y-%m-%dT%H:%M:%S')          # só NFS-e novas desde agora (as antigas não são reenviadas)
        if antigas: c['desde'] = ''
        motor.salvar_cfg(); log(u, 'BOXE_CONFIGURADO', c['servidor'])
        return RedirectResponse(_msg('/boxe', 'ok', 'Configuração guardada.'), status_code=303)

    @app.post('/boxe/ativar')
    def boxe_ativar(request: Request, ligar: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/boxe', status_code=303)
        c = motor.boxe_cfg()
        if ligar == '1' and not motor.boxe_pronto(): return RedirectResponse(_msg('/boxe', 'erro', 'Preencha o servidor, o usuário, a senha e o e-mail remetente antes de ligar.'), status_code=303)
        c['ativo'] = (ligar == '1')
        if c['ativo'] and not c.get('desde'): c['desde'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        motor.salvar_cfg(); log(u, 'BOXE_LIGADO' if c['ativo'] else 'BOXE_DESLIGADO', '')
        return RedirectResponse(_msg('/boxe', 'ok', 'Box-e ligado: as NFS-e novas seguem sozinhas.' if c['ativo'] else 'Box-e desligado.'), status_code=303)

    @app.post('/boxe/testar')
    async def boxe_testar(request: Request, csrf: str = Form(''), enviar: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/boxe', status_code=303)
        import json as _j
        cfg_ = motor.boxe_cfg_envio()
        if enviar:
            try: await run_in_threadpool(boxe.enviar_teste, cfg_)
            except Exception as e: return RedirectResponse(_msg('/boxe', 'erro', boxe.erro_amigavel(e)), status_code=303)
            return RedirectResponse(_msg('/boxe', 'ok', 'E-mail de teste enviado para ' + str(cfg_.get('remetente')) + '.'), status_code=303)
        etapas = await run_in_threadpool(boxe.testar_conexao, cfg_)
        from urllib.parse import quote
        return RedirectResponse('/boxe?etapas=' + quote(_j.dumps(etapas, ensure_ascii=False)), status_code=303)

    # ------------------------------------------------------------ resumo diário
    @app.get('/resumo/previa', response_class=HTMLResponse)
    def resumo_previa(request: Request):
        u, r = exigir(request)
        if r: return r
        return pagina(request, 'resumo_previa.html', {'r': motor.resumo_montar(), 'tela': 'boxe'}, user=u)

    @app.post('/resumo/salvar')
    def resumo_salvar(request: Request, destino: str = Form(''), ligar: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse(_msg('/boxe', 'erro', 'A página expirou.'), status_code=303)
        d = destino.strip()
        if ligar and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', d): return RedirectResponse(_msg('/boxe', 'erro', 'Informe o e-mail que vai receber o resumo.'), status_code=303)
        c = motor.resumo_cfg(); c['destino'] = d; c['ativo'] = bool(ligar); motor.salvar_cfg(); log(u, 'RESUMO_DIARIO', 'ligado' if ligar else 'desligado')
        aviso = '' if motor.boxe_pronto() or not ligar else ' Atenção: falta configurar o e-mail de envio abaixo; o resumo só sai depois disso.'
        return RedirectResponse(_msg('/boxe', 'ok', ('Resumo diário ligado.' if ligar else 'Resumo diário desligado.') + aviso), status_code=303)

    @app.post('/resumo/enviar')
    async def resumo_enviar(request: Request, csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse('/boxe', status_code=303)
        res = await run_in_threadpool(motor.enviar_resumo, True)
        if res['enviado']: return RedirectResponse(_msg('/boxe', 'ok', 'Resumo enviado para ' + str(motor.resumo_cfg().get('destino')) + '.'), status_code=303)
        msg = {'sem_destino': 'Informe o e-mail que vai receber o resumo e clique em Guardar.', 'sem_email': 'Configure primeiro o e-mail de envio (servidor, usuário e senha).'}.get(res['motivo'], res.get('erro') or 'Não consegui enviar agora.')
        return RedirectResponse(_msg('/boxe', 'erro', msg), status_code=303)

    # ------------------------------------------------------------ manifestação do destinatário
    @app.get('/manifestacao', response_class=HTMLResponse)
    def manifestacao_tela(request: Request, ok: str = '', erro: str = ''):
        u, r = exigir(request)
        if r: return r
        cont = motor.manifestador.contagem(); cfgm = motor.manif_cfg(); nomes = {e['cnpj']: e for e in empresas_lista()}
        linhas = [{'cnpj': c, 'nome': (nomes.get(c) or {}).get('nome') or c, 'cnpj_fmt': core._format_cnpj(c), 'pendentes': n, 'auto': bool(cfgm['auto'].get(c)), 'a1': bool(motor.certificado_para(c))} for c, n in sorted(cont.items(), key=lambda x: -x[1])]
        for e in nomes.values():
            if e['cnpj'] not in cont: linhas.append({'cnpj': e['cnpj'], 'nome': e['nome'], 'cnpj_fmt': e['cnpj_fmt'], 'pendentes': 0, 'auto': bool(cfgm['auto'].get(e['cnpj'])), 'a1': bool(motor.certificado_para(e['cnpj']))})
        return pagina(request, 'manifestacao.html', {'linhas': linhas, 'hist': motor.manifestador.historico(60), 'homolog': bool(cfgm.get('homologacao')), 'ok': ok, 'erro': erro, 'limite': manif.LIMITE_PADRAO, 'tela': 'manifestacao'}, user=u)

    @app.post('/manifestacao/agora')
    async def manifestacao_agora(request: Request, empresa: str = Form(''), confirmo: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if not csrf_ok(request, csrf): return RedirectResponse(_msg('/manifestacao', 'erro', 'A página expirou.'), status_code=303)
        d = re.sub(r'\D', '', empresa)
        if len(d) != 14: return RedirectResponse(_msg('/manifestacao', 'erro', 'Escolha a empresa.'), status_code=303)
        if not confirmo: return RedirectResponse(_msg('/manifestacao', 'erro', 'Marque a confirmação: a Ciência da Operação é registrada na SEFAZ em nome da empresa.'), status_code=303)
        res = await run_in_threadpool(motor.manifestar, d, manif.LIMITE_PADRAO, u.get('email', ''))
        log(u, 'MANIFESTACAO_CIENCIA', f"{d} registradas={res['registradas']} erros={len(res['erros'])}")
        partes = [f"{res['registradas']} ciência(s) registrada(s)"] + ([f"{res['ja']} já estavam registradas"] if res['ja'] else []) + ([f"{res['restantes']} ainda pendentes (clique de novo)"] if res['restantes'] else [])
        if res['erros']: return RedirectResponse(_msg('/manifestacao', 'erro', ' • '.join(partes) + ' • ' + ' | '.join(res['erros'][:3])), status_code=303)
        return RedirectResponse(_msg('/manifestacao', 'ok', ' • '.join(partes) + '. O XML completo chega na próxima busca.'), status_code=303)

    @app.post('/manifestacao/auto')
    def manifestacao_auto(request: Request, empresa: str = Form(''), ligar: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        d = re.sub(r'\D', '', empresa)
        if csrf_ok(request, csrf) and len(d) == 14:
            motor.manif_cfg()['auto'][d] = (ligar == '1'); motor.salvar_cfg(); log(u, 'MANIFESTACAO_AUTO', f'{d} {ligar}')
        return RedirectResponse('/manifestacao', status_code=303)

    @app.post('/manifestacao/ambiente')
    def manifestacao_ambiente(request: Request, homolog: str = Form(''), csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if csrf_ok(request, csrf): motor.manif_cfg()['homologacao'] = (homolog == '1'); motor.salvar_cfg(); log(u, 'MANIFESTACAO_AMBIENTE', 'homologação' if homolog == '1' else 'produção')
        return RedirectResponse('/manifestacao', status_code=303)

    return app


def app_producao():
    """Fábrica usada pelo servidor: igual ao site de teste, mas com o agendador da busca automática ligado."""
    return criar_app(iniciar_agendador=True)
