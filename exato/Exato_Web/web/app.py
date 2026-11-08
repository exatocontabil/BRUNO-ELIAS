"""Exato Web — site do escritório. Rotas, sessão e telas. A lógica fiscal vem do código do Exato (web.nucleo); aqui só há acesso, cofre e apresentação."""
import re, secrets, sqlite3, time
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, PlainTextResponse, FileResponse
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auditoria as aud, config, nucleo, relatorios as rel, seguranca
from .agendador import Agendador
from .busca import Motor
from .cofre import Cofre, CofreErro, carregar_chave_mestra

AQUI = Path(__file__).resolve().parent
ROTULOS_TIPO = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}


def criar_app(importador=None, iniciar_agendador=False, nfse_transport=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)          # sem página de documentação técnica exposta na internet
    app.mount('/static', StaticFiles(directory=str(AQUI / 'static')), name='static')
    tpl = Jinja2Templates(directory=str(AQUI / 'templates'))
    core = nucleo.core()
    pasta_cofre = config.DADOS / 'cofre'
    chave = carregar_chave_mestra(pasta_cofre)
    cofre = Cofre(pasta_cofre, chave, importador=importador)
    totp = seguranca.Totp(config.DADOS / 'web.db', chave)
    limite = seguranca.LimiteLogin(); sessoes = seguranca.Sessoes(config.DADOS / 'web.db')
    app.state.cofre, app.state.totp, app.state.limite, app.state.core, app.state.sessoes = cofre, totp, limite, core, sessoes
    motor = Motor(core, cofre, nfse_transport=nfse_transport); agendador = Agendador(motor); app.state.motor, app.state.agendador = motor, agendador
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
        sid = sessoes.criar(u['id'], config.SESSAO_HORAS * 3600)
        cookie(resp, 'exato_sessao', seguranca.assinar({'uid': u['id'], 'sid': sid}, config.SESSAO_HORAS * 3600), config.SESSAO_HORAS * 3600)
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
        d = seguranca.verificar(request.cookies.get('exato_sessao', ''))
        if d: sessoes.revogar(d.get('sid'))
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
        cfg = motor.cfg; oc = motivos.ultimas(str(core.DB_PATH)); linhas = situacao.linhas(str(core.DB_PATH), cfg, None, ocorrencias=oc, diagnostico={}, acessos=dict(cfg.get('nfse_acesso') or {}))
        for l in linhas: l['cnpj_fmt'] = core._format_cnpj(l['cnpj']); l['certificado'] = cofre.info(l['cnpj'])
        return pagina(request, 'situacao.html', {'linhas': linhas, 'totais': situacao.totais(linhas), 'tipos': situacao.TIPOS, 'tela': 'situacao', 'rodando': bool(motor.estado['rodando']), 'auto': agendador.ligado(), 'proxima': agendador.proxima()}, user=u)

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
        e = dict(motor.estado); e['progresso'] = core.busca_progresso_texto() if e.get('rodando') else ''; e['auto'] = agendador.ligado(); e['proxima'] = agendador.proxima()
        return Response(json.dumps(e, ensure_ascii=False), media_type='application/json', headers={'Cache-Control': 'no-store'})

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
        db = str(core.DB_PATH); res = repo.resumo(db); linhas = []
        for cnpj, nome, mes, docs, copiados in repo.por_empresa_mes(db)[:300]:
            linhas.append({'cnpj': cnpj, 'cnpj_fmt': core._format_cnpj(cnpj), 'nome': nome or cnpj, 'mes': mes, 'docs': docs, 'copiados': copiados, 'zip': bool(re.fullmatch(r'\d{4}-\d{2}', mes))})
        return pagina(request, 'repositorio.html', {'res': res, 'linhas': linhas, 'pasta': str(config.ARQUIVOS), 'copiando': bool(motor.estado_repo['copiando']), 'ultimo': motor.estado_repo.get('ultimo'), 'ok': ok, 'tela': 'repositorio'}, user=u)

    @app.post('/repositorio/copiar')
    def repositorio_copiar(request: Request, csrf: str = Form('')):
        u, r = exigir(request)
        if r: return r
        if csrf_ok(request, csrf) and not motor.estado_repo['copiando']:
            import threading; threading.Thread(target=motor.copiar_repositorio, kwargs={'ignorar_pausa': True}, daemon=True, name='repositorio').start(); log(u, 'REPOSITORIO_COPIAR', '')
        return RedirectResponse('/repositorio?ok=Copiando+os+XMLs+para+a+pasta+de+arquivos...', status_code=303)

    @app.get('/repositorio/zip')
    def repositorio_zip(request: Request, empresa: str = '', mes: str = '', tipo: str = ''):
        u, r = exigir(request)
        if r: return r
        d = re.sub(r'\D', '', empresa)
        if len(d) != 14 or not re.fullmatch(r'\d{4}-\d{2}', mes) or (tipo and tipo not in ROTULOS_TIPO): return PlainTextResponse('Pedido inválido.', status_code=400)
        import tempfile, zipfile
        from starlette.background import BackgroundTask
        tmp = tempfile.NamedTemporaryFile(prefix='exato_zip_', suffix='.zip', dir=str(config.DADOS), delete=False); tmp.close()
        con = sqlite3.connect(str(core.DB_PATH), timeout=30); n = 0
        try:
            sql = ("SELECT family, direction, number, access_key, status, xml, doc_id FROM documents WHERE cnpj=? AND substr(COALESCE(NULLIF(issued_at,''),first_seen_at),1,7)=?" + (' AND family=?' if tipo else ''))
            with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                for fam, direc, num, chave, status, xml, doc_id in con.execute(sql, (d, mes) + ((tipo,) if tipo else ())):
                    if not xml: continue
                    pasta = 'Eventos' if status == 'Evento' else f"{ROTULOS_TIPO.get(str(fam).lower(), fam)}/{'Entrada' if str(direc).lower().startswith('e') else 'Saida'}"
                    nome = re.sub(r'[^0-9A-Za-z_.-]', '_', f'{num or "s-n"}_{chave or doc_id}')[:90] + '.xml'
                    z.writestr(f'{pasta}/{nome}', bytes(xml)); n += 1
        finally:
            con.close()
        if not n:
            Path(tmp.name).unlink(missing_ok=True); return PlainTextResponse('Nenhum XML neste mês.', status_code=404)
        log(u, 'ZIP_BAIXADO', f'{d} {mes} {n}')
        return FileResponse(tmp.name, media_type='application/zip', filename=f'XML_{d}_{mes}.zip', background=BackgroundTask(lambda: Path(tmp.name).unlink(missing_ok=True)))

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

    return app


def app_producao():
    """Fábrica usada pelo servidor: igual ao site de teste, mas com o agendador da busca automática ligado."""
    return criar_app(iniciar_agendador=True)
