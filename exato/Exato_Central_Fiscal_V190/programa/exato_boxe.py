"""Envio automático de NFS-e para o Box-e da Domínio (V168).

Sempre que surge NFS-e nova, o Exato manda o XML por e-mail para o endereço do Box-e do escritório; o Box-e alimenta a Domínio.
Regras:
- NUNCA reenvia a mesma nota: cada nota tem uma linha em `boxe_envios` (neste computador) e uma MARCA na pasta compartilhada do servidor
  (`<pasta>\\Box-e\\<CNPJ>\\<chave>.json`), criada de forma atômica ANTES de enviar. A mesma NFS-e chega a vários computadores pela Central;
  quem cria a marca primeiro envia, os outros pulam. Sem acesso à pasta do servidor, espera (não envia sem a marca, para não duplicar).
- falha de envio: a marca é devolvida e a nota volta para a fila (nova tentativa depois de uma pausa);
- marca "enviando" esquecida (programa fechado no meio) é retomada depois de 30 minutos;
- só NFS-e Prestadas (Saída) por padrão; Tomadas só se pedido; eventos de cancelamento das notas seguem junto;
- sem Tkinter; o servidor de e-mail é injetável (testes usam um servidor falso).
"""
from __future__ import annotations
import json, os, re, smtplib, socket, sqlite3, ssl, time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import exato_repositorio as repo

DESTINO_PADRAO = 'exatoara@dominioboxe.com.br'
SUBPASTA_MARCAS = 'Box-e'
MAX_ARQUIVOS = 20                   # XMLs por e-mail
MAX_BYTES = 8 * 1024 * 1024         # tamanho máximo dos anexos por e-mail
PAUSA_ERRO = timedelta(minutes=30)  # depois de uma falha, só tenta a mesma nota de novo após esta pausa
PRAZO_MARCA = timedelta(minutes=30)  # marca "enviando" parada além disto pode ser retomada


def preparar_banco(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS boxe_envios(
        doc_id TEXT PRIMARY KEY, chave TEXT, tipo TEXT, estado TEXT, enviado_em TEXT, enviado_por TEXT,
        tentativas INTEGER DEFAULT 0, erro TEXT, ultima_tentativa TEXT)""")
    conn.commit()


def configurado(cfg):
    return bool(cfg and cfg.get('destino') and cfg.get('servidor') and cfg.get('usuario') and cfg.get('senha') and cfg.get('remetente'))


def _nome(texto, limite=80):
    t = re.sub(r'[\\/:*?"<>|\s]+', '_', str(texto or '')).strip('_.')
    return (t[:limite]) or 'sem_nome'


# ------------------------------------------------------------------ itens a enviar
def itens_pendentes(db_path, incluir_tomadas=False, limite=2000, desde=''):
    """NFS-e (e eventos de cancelamento das notas) que ainda não foram enviadas, mais antigas primeiro.
    `desde` (AAAA-MM-DDTHH:MM:SS): só entra o que o Exato guardou a partir desse momento (o histórico anterior não é reenviado)."""
    conn = sqlite3.connect(db_path, timeout=30); conn.row_factory = sqlite3.Row
    try:
        preparar_banco(conn)
        agora = datetime.now()
        corte = (agora - PAUSA_ERRO).isoformat(timespec='seconds')
        direcoes = ('Saída', 'Entrada') if incluir_tomadas else ('Saída',)
        marcas = ','.join('?' * len(direcoes))
        desde = str(desde or '')
        filtro_n = " AND COALESCE(d.first_seen_at,'')>=?" if desde else ''
        filtro_e = " AND COALESCE(e.first_seen_at,'')>=?" if desde else ''
        extra = (desde,) if desde else ()
        notas = conn.execute(
            f"""SELECT d.doc_id,d.cnpj,d.access_key,d.issued_at,d.status,d.xml,COALESCE(c.name,'') AS empresa,'nota' AS tipo
                FROM documents d LEFT JOIN companies c ON c.cnpj=d.cnpj LEFT JOIN boxe_envios b ON b.doc_id=d.doc_id
                WHERE d.family='nfse' AND d.status IN ('Autorizado','Cancelado') AND d.direction IN ({marcas}){filtro_n}
                  AND (b.doc_id IS NULL OR (b.estado<>'enviado' AND (b.ultima_tentativa IS NULL OR b.ultima_tentativa<?)))
                ORDER BY COALESCE(d.issued_at,''), d.doc_id LIMIT ?""", (*direcoes, *extra, corte, int(limite))).fetchall()
        eventos = conn.execute(
            f"""SELECT e.doc_id,e.cnpj,e.access_key,n.issued_at AS issued_at,e.status,e.xml,COALESCE(c.name,'') AS empresa,'evento' AS tipo
                FROM documents e JOIN documents n ON n.cnpj=e.cnpj AND n.access_key=e.access_key AND n.status IN ('Autorizado','Cancelado') AND n.family='nfse'
                LEFT JOIN companies c ON c.cnpj=e.cnpj LEFT JOIN boxe_envios b ON b.doc_id=e.doc_id
                WHERE e.family='nfse' AND e.status='Evento' AND n.direction IN ({marcas}){filtro_e}
                  AND EXISTS(SELECT 1 FROM documents x WHERE x.cnpj=e.cnpj AND x.access_key=e.access_key AND x.status='Cancelado')
                  AND (b.doc_id IS NULL OR (b.estado<>'enviado' AND (b.ultima_tentativa IS NULL OR b.ultima_tentativa<?)))
                LIMIT ?""", (*direcoes, *extra, corte, int(limite))).fetchall()
        return [dict(r) for r in list(notas) + list(eventos)]
    finally:
        conn.close()


def resumo(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        preparar_banco(conn)
        env = int(conn.execute("SELECT COUNT(*) FROM boxe_envios WHERE estado='enviado'").fetchone()[0] or 0)
        err = int(conn.execute("SELECT COUNT(*) FROM boxe_envios WHERE estado<>'enviado' AND COALESCE(erro,'')<>''").fetchone()[0] or 0)
        ultimo = conn.execute("SELECT MAX(enviado_em) FROM boxe_envios WHERE estado='enviado'").fetchone()[0] or ''
        return {'enviadas': env, 'com_erro': err, 'ultimo_envio': ultimo}
    finally:
        conn.close()


# ------------------------------------------------------------------ marcas compartilhadas (exatamente um envio por nota)
def _caminho_marca(base, cnpj, chave_ou_id):
    return Path(str(base)) / SUBPASTA_MARCAS / (re.sub(r'\D', '', str(cnpj or '')) or 'sem_cnpj') / (_nome(chave_ou_id) + '.json')


def _escrever(caminho, dados):
    os.makedirs(repo._longo(Path(caminho).parent), exist_ok=True)
    tmp = Path(str(caminho) + f'.{os.getpid()}.tmp')
    with open(repo._longo(tmp), 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False)
    os.replace(repo._longo(tmp), repo._longo(caminho))


def _reivindicar(base, item, computador):
    """True = esta máquina pode enviar a nota agora; 'ja_enviada' = outra máquina já enviou; False = outra está enviando (tentar depois)."""
    caminho = _caminho_marca(base, item['cnpj'], item['access_key'] or item['doc_id'] if item['tipo'] == 'nota' else f"{item['access_key']}_{item['doc_id']}")
    dados = {'estado': 'enviando', 'por': computador, 'em': datetime.now().isoformat(timespec='seconds'), 'doc_id': item['doc_id']}
    os.makedirs(repo._longo(Path(caminho).parent), exist_ok=True)
    try:
        fd = os.open(repo._longo(caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False)
        return caminho
    except FileExistsError:
        try:
            with open(repo._longo(caminho), 'r', encoding='utf-8') as f:
                atual = json.load(f)
        except Exception:
            return False
        if atual.get('estado') == 'enviado':
            return 'ja_enviada'
        try:
            parado = datetime.now() - datetime.fromisoformat(atual.get('em'))
        except Exception:
            parado = PRAZO_MARCA + timedelta(seconds=1)
        if parado > PRAZO_MARCA:          # quem reivindicou sumiu (programa fechado no meio): retoma
            _escrever(caminho, dados); return caminho
        return False


def _liberar(caminho):
    try: os.remove(repo._longo(caminho))
    except OSError: pass


# ------------------------------------------------------------------ e-mail
def erro_amigavel(exc):
    """Mensagem em português claro para falhas de e-mail (sem nomes técnicos). Separa o que deu errado: nome do servidor, porta
    bloqueada, conexão que caiu, segurança, usuário/senha (V169; antes tudo virava "não consegui conectar")."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return 'O servidor de e-mail não aceitou o usuário ou a senha. No Gmail e no Microsoft 365 é preciso usar uma "senha de aplicativo" (a senha normal da conta não funciona).'
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return 'O servidor de e-mail recusou o endereço de destino. Confira o e-mail do Box-e.'
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return 'O servidor de e-mail recusou o remetente. Confira se o e-mail de envio é o mesmo da conta.'
    if isinstance(exc, (ssl.SSLError, smtplib.SMTPNotSupportedError)):
        return 'A conexão segura com o servidor de e-mail não funcionou. Tente trocar a segurança (STARTTLS ou SSL) e a porta (587 com STARTTLS, ou 465 com SSL).'
    if isinstance(exc, socket.gaierror):
        return 'Não achei o servidor de e-mail com esse nome. Confira se o campo "Servidor" está certo (Gmail: smtp.gmail.com; Outlook: smtp.office365.com) e se o computador está com internet.'
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return 'O servidor de e-mail não respondeu a tempo. A rede do escritório ou o antivírus pode estar bloqueando essa porta: tente a porta 465 com segurança SSL.'
    if isinstance(exc, (ConnectionRefusedError, PermissionError)) or getattr(exc, 'errno', None) in (111, 10061, 13, 10013):
        return 'A conexão foi recusada. A rede do escritório, o firewall ou o antivírus está bloqueando essa porta. Tente a porta 465 com segurança SSL, ou peça a quem cuida da rede para liberar a saída de e-mail.'
    if isinstance(exc, (ConnectionError, smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError)):
        return 'A conexão com o servidor de e-mail caiu no meio do envio. Tente de novo; se repetir, troque a porta/segurança ou verifique o antivírus.'
    if isinstance(exc, OSError):
        return 'Não consegui falar com o servidor de e-mail. Confira o servidor, a porta e a internet.'
    return 'O envio por e-mail não foi concluído.'


# Servidores comuns: preenchem sozinhos o servidor, a porta e a segurança a partir do e-mail de envio.
SERVIDORES = {
    'gmail.com': ('smtp.gmail.com', 587, 'STARTTLS'), 'googlemail.com': ('smtp.gmail.com', 587, 'STARTTLS'),
    'outlook.com': ('smtp.office365.com', 587, 'STARTTLS'), 'hotmail.com': ('smtp.office365.com', 587, 'STARTTLS'),
    'live.com': ('smtp.office365.com', 587, 'STARTTLS'), 'office365.com': ('smtp.office365.com', 587, 'STARTTLS'),
}


def servidor_sugerido(email):
    """(servidor, porta, segurança) para o e-mail, ou None se o provedor não for um dos conhecidos."""
    m = re.fullmatch(r'[^@\s]+@([^@\s]+)', str(email or '').strip().lower())
    return SERVIDORES.get(m.group(1)) if m else None


def conferir_servidor(servidor):
    """Texto de alerta se o campo "Servidor" não parece um servidor (por exemplo, se colocaram o e-mail ali); '' se está tudo bem."""
    s = str(servidor or '').strip()
    if '@' in s:
        sug = servidor_sugerido(s)
        return 'No campo "Servidor" vai o endereço do servidor de e-mail' + (f' (para esse e-mail: {sug[0]})' if sug else ' (por exemplo smtp.gmail.com)') + ', não o e-mail. O e-mail vai no campo "Usuário".'
    if s and (' ' in s or '/' in s or ':' in s):
        return 'O servidor deve ser só o endereço, sem espaços, "http://" ou porta (por exemplo smtp.gmail.com). A porta tem campo próprio.'
    return ''


def testar_conexao(cfg, rede=None):
    """Confere o caminho do e-mail por etapas e devolve [(etapa, ok, texto)]; para na primeira que falhar.
    Etapas: achar o servidor, abrir a porta, segurança, usuário e senha. Não envia e-mail."""
    etapas = []
    servidor, porta = str(cfg.get('servidor') or '').strip(), int(cfg.get('porta') or 587); seg = str(cfg.get('seguranca') or 'STARTTLS').upper()
    aviso = conferir_servidor(servidor)
    if not servidor or aviso:
        etapas.append(('Endereço do servidor', False, aviso or 'Falta preencher o servidor de e-mail.')); return etapas
    try:
        socket.getaddrinfo(servidor, porta)
        etapas.append(('Achar o servidor', True, f'{servidor} encontrado.'))
    except Exception as exc:
        etapas.append(('Achar o servidor', False, erro_amigavel(exc if isinstance(exc, socket.gaierror) else socket.gaierror(str(exc))))); return etapas
    try:
        if seg == 'SSL':
            smtp = smtplib.SMTP_SSL(servidor, porta, timeout=20, context=ssl.create_default_context())
        else:
            smtp = smtplib.SMTP(servidor, porta, timeout=20); smtp.ehlo()
        etapas.append(('Abrir a porta ' + str(porta), True, 'A rede deixou chegar no servidor.'))
    except ssl.SSLError as exc:
        etapas.append(('Abrir a porta ' + str(porta), False, erro_amigavel(exc))); return etapas
    except Exception as exc:
        etapas.append(('Abrir a porta ' + str(porta), False, erro_amigavel(exc))); return etapas
    try:
        try:
            if seg == 'STARTTLS':
                smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
            etapas.append(('Conexão segura', True, 'Segurança aceita.'))
        except Exception as exc:
            etapas.append(('Conexão segura', False, erro_amigavel(exc))); return etapas
        if cfg.get('usuario') and cfg.get('senha'):
            try:
                smtp.login(cfg['usuario'], cfg['senha'])
                etapas.append(('Usuário e senha', True, 'Aceitos pelo servidor.'))
            except Exception as exc:
                etapas.append(('Usuário e senha', False, erro_amigavel(exc))); return etapas
        else:
            etapas.append(('Usuário e senha', False, 'Falta preencher o usuário e a senha.'))
    finally:
        try: smtp.quit()
        except Exception: pass
    return etapas


def _conectar(cfg):
    servidor, porta = cfg['servidor'], int(cfg.get('porta') or 587); seg = str(cfg.get('seguranca') or 'STARTTLS').upper()
    if seg == 'SSL':
        smtp = smtplib.SMTP_SSL(servidor, porta, timeout=40, context=ssl.create_default_context())
    else:
        smtp = smtplib.SMTP(servidor, porta, timeout=40)
        smtp.ehlo()
        if seg == 'STARTTLS':
            smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
    if cfg.get('usuario') and cfg.get('senha'):
        smtp.login(cfg['usuario'], cfg['senha'])
    return smtp


def _montar_email(cfg, itens):
    cnpj = re.sub(r'\D', '', str(itens[0]['cnpj'] or '')); empresa = itens[0].get('empresa') or cnpj
    mes = str(itens[0].get('issued_at') or '')[:7] or 'sem data'
    msg = EmailMessage()
    msg['From'] = cfg['remetente']; msg['To'] = cfg['destino']
    msg['Subject'] = f'NFS-e {cnpj} {empresa} {mes} ({len(itens)} arquivo(s))'[:200]
    msg.set_content(f'Segue(m) {len(itens)} arquivo(s) XML de NFS-e da empresa {empresa} (CNPJ {cnpj}), referente(s) a {mes}.\n\n'
                    'Enviado automaticamente pelo Exato Central Fiscal.')
    for it in itens:
        nome = _nome(it['access_key'] or it['doc_id']) + ('' if it['tipo'] == 'nota' else '_evento') + '.xml'
        msg.add_attachment(bytes(it['xml'] or b''), maintype='application', subtype='xml', filename=nome)
    return msg


def enviar_teste(cfg, para=None):
    """E-mail de teste (sem anexo) para o próprio remetente: confere servidor, porta, usuário e senha sem incomodar o Box-e."""
    msg = EmailMessage(); msg['From'] = cfg['remetente']; msg['To'] = para or cfg['remetente']; msg['Subject'] = 'Teste do Exato Central Fiscal (Box-e)'
    msg.set_content('Este é um teste. Se você recebeu esta mensagem, o envio de e-mail do Exato está funcionando.')
    smtp = _conectar(cfg)
    try: smtp.send_message(msg)
    finally:
        try: smtp.quit()
        except Exception: pass


def _lotes(itens):
    """Agrupa por empresa e mês; cada e-mail leva até MAX_ARQUIVOS arquivos e MAX_BYTES de anexos."""
    grupos = {}
    for it in itens:
        grupos.setdefault((it['cnpj'], str(it.get('issued_at') or '')[:7]), []).append(it)
    for _, lista in sorted(grupos.items()):
        atual, tam = [], 0
        for it in lista:
            t = len(it['xml'] or b'')
            if atual and (len(atual) >= MAX_ARQUIVOS or tam + t > MAX_BYTES):
                yield atual; atual, tam = [], 0
            atual.append(it); tam += t
        if atual: yield atual


_SQL_OK = ("INSERT INTO boxe_envios(doc_id,chave,tipo,estado,enviado_em,enviado_por,tentativas,erro,ultima_tentativa) VALUES(?,?,?,?,?,?,1,'',?) "
           "ON CONFLICT(doc_id) DO UPDATE SET estado=excluded.estado,enviado_em=excluded.enviado_em,enviado_por=excluded.enviado_por,erro='',ultima_tentativa=excluded.ultima_tentativa")
_SQL_ERRO = ("INSERT INTO boxe_envios(doc_id,chave,tipo,estado,tentativas,erro,ultima_tentativa) VALUES(?,?,?,'erro',1,?,?) "
             "ON CONFLICT(doc_id) DO UPDATE SET estado='erro',erro=excluded.erro,tentativas=tentativas+1,ultima_tentativa=excluded.ultima_tentativa")


def _gravar(conn, fila):
    for tentativa in range(6):
        try:
            for sql, params in fila: conn.execute(sql, params)
            conn.commit(); fila.clear(); return
        except sqlite3.OperationalError:
            try: conn.rollback()
            except Exception: pass
            time.sleep(0.4 * (tentativa + 1))
    fila.clear()


def enviar_pendentes(db_path, cfg, base_servidor, cancelar=None, computador=None, incluir_tomadas=False, conectar=None, maximo_emails=None, desde=''):
    """Envia o que falta. Devolve {'ok','motivo','enviadas','puladas_outro_pc','emails','erros','erro'}."""
    res = {'ok': True, 'motivo': '', 'enviadas': 0, 'puladas_outro_pc': 0, 'emails': 0, 'erros': 0, 'erro': ''}
    if not configurado(cfg):
        res.update(ok=False, motivo='sem_configuracao'); return res
    if not repo.pasta_acessivel(base_servidor):
        res.update(ok=False, motivo='servidor'); return res          # sem a marca compartilhada não envia (evita duplicar)
    pc = computador or socket.gethostname()
    itens = itens_pendentes(db_path, incluir_tomadas, desde=desde)
    if not itens:
        return res
    conn = sqlite3.connect(db_path, timeout=30)
    conectar = conectar or _conectar
    try:
        preparar_banco(conn); fila = []
        for lote in _lotes(itens):
            if cancelar and cancelar(): res['motivo'] = 'cancelado'; break
            if maximo_emails is not None and res['emails'] >= maximo_emails: break
            agora = datetime.now().isoformat(timespec='seconds')
            meus = []; marcas = {}
            for it in lote:
                r = _reivindicar(base_servidor, it, pc)
                if r == 'ja_enviada':
                    fila.append((_SQL_OK, (it['doc_id'], it['access_key'], it['tipo'], 'enviado', agora, 'outro computador', agora))); res['puladas_outro_pc'] += 1
                elif r:
                    meus.append(it); marcas[it['doc_id']] = r
            if not meus:
                _gravar(conn, fila); continue
            try:
                smtp = conectar(cfg)
                try: smtp.send_message(_montar_email(cfg, meus))
                finally:
                    try: smtp.quit()
                    except Exception: pass
            except Exception as exc:
                for it in meus:
                    _liberar(marcas[it['doc_id']])                      # devolve a vez: outra tentativa (ou outro computador) pode enviar
                    fila.append((_SQL_ERRO, (it['doc_id'], it['access_key'], it['tipo'], str(exc)[:200], agora)))
                res['erros'] += len(meus); res['erro'] = erro_amigavel(exc); _gravar(conn, fila)
                res.update(ok=False, motivo='falha'); return res
            fim = datetime.now().isoformat(timespec='seconds')
            for it in meus:
                for _t in range(4):          # a marca "enviado" é o que impede outro computador de reenviar: insiste um pouco
                    try: _escrever(marcas[it['doc_id']], {'estado': 'enviado', 'por': pc, 'em': fim, 'doc_id': it['doc_id']}); break
                    except Exception: time.sleep(0.2 * (_t + 1))
                fila.append((_SQL_OK, (it['doc_id'], it['access_key'], it['tipo'], 'enviado', fim, pc, fim)))
            res['enviadas'] += len([i for i in meus if i['tipo'] == 'nota']); res['emails'] += 1
            _gravar(conn, fila)
        _gravar(conn, fila)
        return res
    finally:
        conn.close()
