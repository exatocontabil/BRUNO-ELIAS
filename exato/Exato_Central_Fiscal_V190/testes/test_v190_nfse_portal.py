"""Acesso por usuário e senha: roda o navegador de verdade contra um portal SIMULADO (não é o portal real)."""
import glob, os, sys, tempfile, threading, shutil
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'programa')); sys.path.insert(0,str(Path(__file__).parent))
import exato_nfse as n, exato_nfse_portal as portal
from test_v190_nfse_core import nfse_xml, chave, PREST, TOMA
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw: exe=pw.chromium.executable_path
    if not exe or not Path(exe).exists():
        found=sorted(glob.glob(os.path.join(os.environ.get('PLAYWRIGHT_BROWSERS_PATH','/opt/pw-browsers'),'chromium-*','chrome-linux*','chrome')))
        if not found: raise FileNotFoundError(exe)
        exe=found[-1]
except Exception as exc:
    print(f'V169 NFS-e portal: PULADO (sem Playwright/Chromium neste computador: {exc})'); sys.exit(0)

NOTAS={1:nfse_xml(1,dh='2026-09-10T10:00:00-03:00'),2:nfse_xml(2,dh='2026-09-20T10:00:00-03:00'),3:nfse_xml(3,dh='2026-01-05T10:00:00-03:00'),
       4:nfse_xml(4,prest='11111111000191',toma='22222222000191',dh='2026-09-12T10:00:00-03:00'),
       5:nfse_xml(5,prest='33333333000191',toma=PREST,dh='2026-09-15T10:00:00-03:00')}
EMITIDAS=[[1,2],[3,4]]; RECEBIDAS=[[5]]; DOWNLOADS=[]; LISTAS=[]; CAPTCHA=[False]; MODE=['normal']; HITS={}
def link(i): return f'<a href="/EmissorNacional/Notas/Download/NFSe/{chave(i)}">XML</a>'
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _send(self,code,body,ctype='text/html; charset=utf-8',headers=()):
        self.send_response(code); self.send_header('Content-Type',ctype)
        for k,v in headers: self.send_header(k,v)
        self.end_headers(); self.wfile.write(body if isinstance(body,bytes) else body.encode())
    def authed(self): return 'sid=ok' in (self.headers.get('Cookie') or '')
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=='/EmissorNacional/Login' and CAPTCHA[0]: return self._send(200,'<form method="post"><input type="text" name="Inscricao"><input type="password" name="Senha"><div class="g-recaptcha">captcha</div></form>')
        if u.path=='/EmissorNacional/Login': return self._send(200,'<form method="post" action="/EmissorNacional/Login"><input type="text" name="Inscricao"><input type="password" name="Senha"><button type="submit">Entrar</button></form>')
        if not self.authed(): return self._send(302,'',headers=[('Location','/EmissorNacional/Login')])
        if u.path=='/EmissorNacional/': return self._send(200,'<h1>Painel</h1>')
        if u.path.startswith('/EmissorNacional/Notas/Download/NFSe/'):
            k0=u.path.rsplit('/',1)[1]
            DOWNLOADS.append((self.headers.get('Sec-Fetch-Mode'),self.headers.get('Sec-Fetch-Dest'),bool(self.headers.get('Referer')),'HeadlessChrome' in (self.headers.get('User-Agent') or '')))
            # como o portal real: só atende navegação de verdade com a lista como origem (pedido solto/fetch leva 403)
            HITS[k0]=HITS.get(k0,0)+1
            if MODE[0]=='captcha' and HITS[k0]<=2: return self._send(200,'<html><head><meta http-equiv="refresh" content="1"></head><body><div class="h-captcha">Confirme que você é uma pessoa (captcha)</div></body></html>')
            if MODE[0]=='todos403' or self.headers.get('Sec-Fetch-Mode')!='navigate' or not self.headers.get('Referer') or (MODE[0]=='semjanela' and 'HeadlessChrome' in (self.headers.get('User-Agent') or '')):
                return self._send(403,'acesso negado',headers=[('Server','portal-teste')])
            k=u.path.rsplit('/',1)[1]; i=next((i for i in NOTAS if chave(i)==k),None)
            return self._send(200 if i else 404,NOTAS.get(i,b''),'application/xml',headers=([('Content-Disposition','attachment; filename="nota.xml"')] if MODE[0]=='anexo' else []))
        for name,pages in (('Emitidas',EMITIDAS),('Recebidas',RECEBIDAS)):
            if u.path==f'/EmissorNacional/Notas/{name}':
                LISTAS.append((name,q.get('datainicio',[''])[0],q.get('datafim',[''])[0]))
                pg=int(q.get('pg',['1'])[0]); rows=''.join(f'<tr><td>{i}</td><td>{link(i)}</td></tr>' for i in pages[pg-1]) if pg<=len(pages) else ''
                nxt=f'<a rel="next" href="/EmissorNacional/Notas/{name}?pg={pg+1}">Próxima</a>' if pg<len(pages) else ''
                return self._send(200,f'<table>{rows}</table>{nxt}')
        self._send(404,'nao')
    def do_POST(self):
        body=self.rfile.read(int(self.headers.get('Content-Length',0))).decode(); f=parse_qs(body)
        if f.get('Inscricao',[''])[0]==PREST and f.get('Senha',[''])[0]=='segredo': return self._send(302,'',headers=[('Location','/EmissorNacional/'),('Set-Cookie','sid=ok; Path=/')])
        self._send(200,'<form><input type="text" name="Inscricao"><input type="password" name="Senha"></form><p>Usuário ou senha inválidos</p>')
srv=ThreadingHTTPServer(('127.0.0.1',0),H); threading.Thread(target=srv.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{srv.server_port}'
P=dict(portal.PORTAL); P.update(login_url=base+'/EmissorNacional/Login', lists={'Emitidas':base+'/EmissorNacional/Notas/Emitidas','Recebidas':base+'/EmissorNacional/Notas/Recebidas'},
       xml_url=base+'/EmissorNacional/Notas/Download/NFSe/{chave}', login_wait_seconds=4, headless_login_seconds=4)
opts={'executable_path':exe,'headless':True,'args':['--no-sandbox'],'channel':None}
portal.TIMEOUTS.update(click_ms=1500,tab_wait_s=3,idle_s=3,retries=0,retry_pause_s=0)
logs=Path(tempfile.mkdtemp(prefix='exato_portal_logs_')); msgs=[]
_orig=portal.fetch_via_portal
portal.fetch_via_portal=lambda *a,**k:_orig(*a,**{'fallback_options':{'headless':True},**k})   # a janela visível de reserva também roda sem tela no teste
try:
    items,info=portal.fetch_via_portal('12.345.678/0001-95','segredo',PREST,date(2026,9,1),date(2026,9,30),logs,portal=P,progress=msgs.append,browser_options=opts)
    keys=sorted(i['chave'] for i in items)
    assert keys==sorted([chave(1),chave(2),chave(5)]),keys                      # 3 vem de janeiro (fora do período) e 4 é de outra empresa
    assert info['emitidas']==2 and info['recebidas']==1 and info['fora_periodo']==1 and info['outras_empresas']==1 and info['falhas']==0,info
    assert any('página 2' in m for m in msgs), 'percorreu a segunda página'
    assert all(i['tipo_documento']=='NFSE' and i['xml'].startswith(b'<?xml') for i in items)
    assert DOWNLOADS and all(d[0]=='navigate' and d[2] for d in DOWNLOADS),DOWNLOADS      # baixou como navegação de verdade, com a lista como origem
    # sessão guardada: a segunda busca entra sem senha
    saved=[]; items1,_=portal.fetch_via_portal(PREST,'segredo',PREST,date(2026,9,1),date(2026,9,30),logs,portal=P,browser_options=opts,on_session=saved.append)
    assert saved and 'sid' in saved[0]
    items2,info2=portal.fetch_via_portal(PREST,'',PREST,date(2026,9,1),date(2026,9,30),logs,portal=P,browser_options=opts,session_state=saved[0])
    assert info2['sessao_reaproveitada'] and len(items2)==3,info2
    # período maior que 30 dias é dividido em janelas
    LISTAS.clear(); portal.fetch_via_portal(PREST,'segredo',PREST,date(2026,7,1),date(2026,9,30),logs,portal=P,browser_options=opts)
    emit=[l for l in LISTAS if l[0]=='Emitidas' and l[1]]; assert len(emit)>=4 and emit[0][1]=='01/07/2026' and emit[-1][2]=='30/09/2026',emit
    wins=portal.period_windows(date(2026,7,1),date(2026,9,30)); assert all((b-a).days<=29 for a,b in wins) and wins[0][0]==date(2026,7,1) and wins[-1][1]==date(2026,9,30)
    assert portal.period_windows(None,None)==[(None,None)]
    # o arquivo vem como anexo (download do navegador): também funciona
    MODE[0]='anexo'; items3,info3=portal.fetch_via_portal(PREST,'segredo',PREST,date(2026,9,1),date(2026,9,30),logs,portal=P,browser_options=opts)
    assert len(items3)==3 and info3['falhas']==0,info3
    # o portal barra o navegador sem janela: repete com o navegador visível (aqui um segundo navegador "normal", sem 'Headless' no nome)
    MODE[0]='semjanela'; msgs.clear(); DOWNLOADS.clear()
    items4,info4=portal.fetch_via_portal(PREST,'segredo',PREST,date(2026,9,1),date(2026,9,30),logs,portal=P,progress=msgs.append,browser_options=opts,fallback_options={'headless':True,'args':['--no-sandbox','--user-agent=Mozilla/5.0 Chrome/120 Edg/120']})
    assert any('navegador visível' in m for m in msgs),msgs
    assert len(items4)==3 and info4.get('repetiu_com_janela'),info4
    # captcha na janela do download: o Exato espera e insiste na MESMA nota (errou/demorou duas vezes), sem pular
    MODE[0]='captcha'; HITS.clear(); msgs.clear(); Pc=dict(P); Pc['assume_visible']=True
    items6,info6=portal.fetch_via_portal(PREST,'segredo',PREST,date(2026,9,1),date(2026,9,30),logs,portal=Pc,progress=msgs.append,browser_options=opts)
    assert len(items6)==3 and info6['falhas']==0,info6
    assert any('Resolva a confirmação' in m and 'nota 1 de' in m for m in msgs),msgs
    assert all(v>=3 for v in HITS.values()) and len(HITS)>=3,HITS      # cada nota foi tentada até a 3ª vez antes de passar para a próxima
    # cancelar enquanto espera o captcha
    HITS.clear(); stop=[]; 
    def prog(m):
        msgs.append(m)
        if 'Resolva a confirmação' in m: stop.append(1)
    try: portal.fetch_via_portal(PREST,'segredo',PREST,date(2026,9,1),date(2026,9,30),logs,portal=Pc,progress=prog,cancelled=lambda:bool(stop),browser_options=opts)
    except n.NfseError: pass
    MODE[0]='normal'
    # o portal recusa tudo: erro com o que cada tentativa recebeu, guardado no diagnóstico
    MODE[0]='todos403'; shutil.rmtree(logs,ignore_errors=True); logs.mkdir()
    items5,info5=portal.fetch_via_portal(PREST,'segredo',PREST,date(2026,9,1),date(2026,9,30),logs,portal=P,browser_options=opts,fallback_options={'headless':True})
    assert items5==[] and info5['falhas']>=3,info5
    txt=''.join(p.read_text(errors='ignore') for p in logs.rglob('download_*.txt'))
    assert 'HTTP 403' in txt and 'aba:' in txt and 'clique:' in txt and 'página:' in txt and 'portal-teste' in txt and 'Navegador:' in txt and 'segredo' not in txt,txt
    MODE[0]='normal'
    # captcha: primeiro tenta sem janela e, se o portal pedir confirmação, repete com a janela (aqui simulada também sem janela)
    msgs.clear(); CAPTCHA[0]=True
    try: portal.fetch_via_portal(PREST,'segredo',PREST,None,None,logs,portal=P,progress=msgs.append,browser_options=opts,fallback_options={'headless':True})
    except n.NfseError: pass
    assert any('abrir a janela' in m for m in msgs),msgs
    CAPTCHA[0]=False
    # senha errada: erro amigável, sem a senha em lugar nenhum
    try: portal.fetch_via_portal(PREST,'errada',PREST,None,None,logs,portal=P,browser_options=opts); raise SystemExit('deveria falhar')
    except n.NfseError as e:
        assert 'não liberou o acesso' in str(e) and 'errada' not in str(e)
    txt=''.join(p.read_text(errors='ignore') for p in logs.rglob('*') if p.is_file() and p.suffix in ('.html','.txt'))
    assert 'errada' not in txt and 'segredo' not in txt, 'a senha não pode aparecer no diagnóstico'
    # tela de login diferente do esperado: diagnóstico guardado
    P2=dict(P); P2.update(user_selectors=['#nao_existe'],pass_selectors=['#nao_existe'])
    try: portal.fetch_via_portal(PREST,'segredo',PREST,None,None,logs,portal=P2,browser_options=opts); raise SystemExit('deveria falhar')
    except n.NfseError as e: assert 'campos de usuário e senha' in str(e) and 'nfse_portal' in str(e)
    assert list(logs.rglob('login_campos.png')) and list(logs.rglob('login_campos.html'))
    # cancelamento
    try: portal.fetch_via_portal(PREST,'segredo',PREST,None,None,logs,portal=P,cancelled=lambda:True,browser_options=opts)
    except n.NfseError: pass
finally:
    srv.shutdown(); shutil.rmtree(logs,ignore_errors=True)
print('V169 NFS-e portal (simulado): OK')
