"""Diagnóstico para o suporte: um ZIP pequeno com o que ajuda a entender um problema, SEM nenhum dado sensível.

Entra: versão, computador, espaço em disco, tamanhos das pastas, contagens (empresas e notas), resultado das últimas buscas, estado da cópia de segurança, configurações
(sem segredos) e o final dos registros do site. NUNCA entra: XML de nota, certificado, senha, cofre, banco de dados, código do celular, cookies.
Por padrão CNPJ, CPF, e-mail e nome de usuário do Windows saem mascarados (a pessoa pode desmarcar)."""
import io, json, os, platform, re, shutil, sqlite3, sys, zipfile
from datetime import datetime
from pathlib import Path

from . import config

LIMITE_REGISTRO = 400 * 1024          # final de cada registro
RX_CNPJ = re.compile(r'\b(\d{2})\.?(\d{3})\.?(\d{3})/?(\d{4})-?(\d{2})\b')
RX_CPF = re.compile(r'\b(\d{3})\.(\d{3})\.(\d{3})-(\d{2})\b')
RX_EMAIL = re.compile(r'\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b')
RX_USUARIO = re.compile(r'(?i)(Users[\\/])([^\\/\s"\']+)')


def mascarar(texto):
    """Esconde CNPJ (fica o começo e o fim), CPF, e-mail e o nome do usuário do Windows nos caminhos."""
    t = str(texto or '')
    t = RX_CNPJ.sub(lambda m: f'{m.group(1)}.***.***/****-{m.group(5)}', t)
    t = RX_CPF.sub(lambda m: f'***.***.***-{m.group(4)}', t)
    t = RX_EMAIL.sub(lambda m: f'{m.group(1)}***@{m.group(2)}', t)
    return RX_USUARIO.sub(lambda m: m.group(1) + '<usuario>', t)


def _tamanho_pasta(p):
    total = 0
    try:
        for raiz, _d, nomes in os.walk(p):
            for n in nomes:
                try: total += (Path(raiz) / n).stat().st_size
                except OSError: pass
    except OSError: pass
    return total


def _mb(b): return f'{b / 1048576:.1f} MB' if b < 1024 ** 3 else f'{b / 1024 ** 3:.2f} GB'


def _final(arquivo, limite=LIMITE_REGISTRO):
    try:
        with open(arquivo, 'rb') as f:
            f.seek(0, 2); n = f.tell(); f.seek(max(0, n - limite)); dados = f.read()
        return dados.decode('utf-8', errors='replace')
    except OSError: return ''


def _versao():
    for p in (config.RAIZ / 'VERSAO.txt',):
        try: return p.read_text(encoding='utf-8-sig').splitlines()[0].strip()
        except Exception: pass
    return 'desconhecida'


def _secao(titulo, f):
    try: corpo = f()
    except Exception as e: corpo = f'(não foi possível obter: {type(e).__name__})'
    return f'== {titulo} ==\n{corpo}\n'


def resumo(core, motor, agora=None):
    """Texto legível com o estado do Exato (sem segredos)."""
    agora = agora or datetime.now(); dados = Path(config.DADOS); partes = []
    partes.append(_secao('Exato Web', lambda: f"Versão: {_versao()}\nGerado em: {agora:%d/%m/%Y %H:%M:%S}\nHTTPS no site: {'sim' if config.HTTPS else 'não'}\nCódigo do celular obrigatório: {'sim' if config.EXIGIR_2FA else 'não'}"))
    partes.append(_secao('Computador', lambda: f"Sistema: {platform.platform()}\nMáquina: {platform.machine()}\nPython: {sys.version.split()[0]}"))
    def disco():
        out = []
        for rot, p in (('Dados do Exato', dados), ('Cópias de XML', Path(config.ARQUIVOS))):
            try: u = shutil.disk_usage(str(p)); out.append(f'{rot}: livre {_mb(u.free)} de {_mb(u.total)} ({str(p)})')
            except OSError: out.append(f'{rot}: pasta não acessível ({p})')
        return '\n'.join(out)
    partes.append(_secao('Disco', disco))
    def pastas():
        linhas = []
        try:
            for p in sorted(dados.iterdir(), key=lambda x: x.name.lower()):
                linhas.append(f'{p.name}: {_mb(_tamanho_pasta(p) if p.is_dir() else p.stat().st_size)}')
        except OSError: pass
        return '\n'.join(linhas) or '(vazio)'
    partes.append(_secao('Tamanho das pastas de dados', pastas))
    def contagens():
        con = sqlite3.connect(f'file:{core.DB_PATH}?mode=ro', uri=True, timeout=10)
        try:
            emp = con.execute('SELECT COUNT(*) FROM companies').fetchone()[0]
            linhas = [f'Empresas: {emp}']
            for fam, st, n in con.execute("SELECT family, COALESCE(status,''), COUNT(*) FROM documents GROUP BY family, status ORDER BY family, status").fetchall(): linhas.append(f'  {fam} / {st or "sem situação"}: {n}')
            return '\n'.join(linhas)
        finally: con.close()
    partes.append(_secao('Empresas e notas guardadas', contagens))
    def buscas():
        con = sqlite3.connect(f'file:{core.DB_PATH}?mode=ro', uri=True, timeout=10)
        try:
            linhas = [f'{q} | {c} | {t} | {r} | {cod} | {str(d or "")[:200]}' for q, c, t, r, cod, d in con.execute('SELECT quando, cnpj, tipo, resultado, codigo, detalhe FROM busca_ocorrencias ORDER BY id DESC LIMIT 120').fetchall()]
            return 'quando | empresa | tipo | resultado | causa | detalhe\n' + ('\n'.join(linhas) or '(nenhuma ocorrência)')
        finally: con.close()
    partes.append(_secao('Últimas buscas (por empresa e tipo)', buscas))
    def estado():
        e = motor.estado; a = motor.and_foto()
        return f"Busca em andamento: {'sim' if e.get('rodando') else 'não'}\nÚltima busca: {e.get('ultimo') or '—'}\nBusca automática: {'ligada' if motor.cfg.get('web_auto', True) is not False else 'desligada'}\nÚltima rodada automática: {motor.cfg.get('auto_round_last') or '—'}"
    partes.append(_secao('Estado da busca', estado))
    def copia():
        from . import backup
        c = backup.cfg_de(motor.cfg)
        return f"Cópia de segurança: {'ligada' if c.get('ativo') else 'desligada'}\nHora: {c.get('hora')}\nÚltima tentativa: {c.get('ultimo') or '—'} ({c.get('ultimo_estado') or '—'})\nÚltima boa: {c.get('ultimo_ok') or '—'}\nMensagem: {c.get('ultimo_msg') or '—'}"
    partes.append(_secao('Cópia de segurança', copia))
    def certificados():
        try: n = len(list(Path(config.DADOS, 'cofre').glob('*.json')))
        except OSError: n = 0
        return f'Certificados guardados (quantidade): {n}'
    partes.append(_secao('Certificados', certificados))
    def configuracao():
        cfg = motor.cfg; segura = {}
        for k in ('web_auto', 'auto_round_last'): segura[k] = cfg.get(k)
        segura['repositorio_web_auto'] = (cfg.get('repositorio_web') or {}).get('auto'); segura['fechamento'] = {k: v for k, v in (cfg.get('fechamento') or {}).items() if k in ('ativo', 'dias')}
        segura['boxe'] = {'ativo': (cfg.get('boxe') or {}).get('ativo'), 'servidor': (cfg.get('boxe') or {}).get('servidor'), 'porta': (cfg.get('boxe') or {}).get('porta'), 'seguranca': (cfg.get('boxe') or {}).get('seguranca')}
        segura['manifestacao_homologacao'] = (cfg.get('manifestacao') or {}).get('homologacao'); segura['resumo_diario_ativo'] = (cfg.get('resumo_diario') or {}).get('ativo')
        return json.dumps(segura, ensure_ascii=False, indent=1, default=str)
    partes.append(_secao('Configurações (sem senhas)', configuracao))
    return '\n'.join(partes)


def montar_zip(core, motor, ocultar=True, agora=None):
    """Devolve os bytes do ZIP do diagnóstico."""
    agora = agora or datetime.now(); ocultar_f = mascarar if ocultar else (lambda x: x); buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr('LEIA-ME.txt', 'Diagnóstico do Exato Web, gerado em ' + agora.strftime('%d/%m/%Y às %H:%M') + '.\r\n\r\n'
                   'Serve para o suporte entender um problema. NÃO contém notas (XML), certificados, senhas, códigos do celular nem os dados do Exato.\r\n'
                   + ('CNPJ, CPF, e-mails e o nome do usuário do Windows foram escondidos.\r\n' if ocultar else 'Atenção: CNPJ, CPF e e-mails NÃO foram escondidos neste diagnóstico.\r\n')
                   + '\r\nEnvie este arquivo ao suporte e diga o que você estava fazendo, o dia e a hora do problema.\r\n')
        z.writestr('resumo.txt', ocultar_f(resumo(core, motor, agora)))
        logs = Path(config.DADOS) / 'logs'
        for nome, arq in (('registro_do_site.txt', logs / 'servidor_saida.log'), ('registro_do_site_anterior.txt', logs / 'servidor_saida.log.1')):
            t = _final(arq)
            if t: z.writestr(nome, ocultar_f(t))
        try:
            t = _final(Path(core.LOG_DIR) / 'exato.log')
            if t: z.writestr('registro_do_exato.txt', ocultar_f(t))
        except Exception: pass
    return buf.getvalue()


def nome_arquivo(agora=None): return f"Diagnostico_Exato_{(agora or datetime.now()):%Y%m%d_%H%M}.zip"


class DiagnosticoErro(Exception): pass


def enviar_por_email(motor, destino, dados_zip, nome):
    """Manda o diagnóstico ao suporte usando o e-mail de envio já configurado (tela Box-e). Levanta DiagnosticoErro em português."""
    from email.message import EmailMessage
    from . import nucleo
    boxe = nucleo.modulo('exato_boxe'); cfg = motor.boxe_cfg_envio()
    if not boxe.configurado(cfg): raise DiagnosticoErro('Para enviar por e-mail, configure antes o e-mail de envio na tela Box-e. Você também pode baixar o arquivo e mandá-lo por onde preferir.')
    if len(dados_zip) > 12 * 1024 * 1024: raise DiagnosticoErro('O diagnóstico ficou grande demais para e-mail. Baixe o arquivo e envie por outro meio.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', str(destino or '')): raise DiagnosticoErro('Informe o e-mail do suporte.')
    msg = EmailMessage(); msg['From'] = cfg['remetente']; msg['To'] = destino; msg['Subject'] = 'Diagnóstico do Exato Web'
    msg.set_content('Diagnóstico do Exato Web em anexo (sem notas, certificados nem senhas).\r\nDescreva abaixo o que aconteceu, o dia e a hora.\r\n')
    msg.add_attachment(dados_zip, maintype='application', subtype='zip', filename=nome)
    try:
        smtp = (motor.boxe_conectar or boxe._conectar)(cfg)
        try: smtp.send_message(msg)
        finally:
            try: smtp.quit()
            except Exception: pass
    except DiagnosticoErro: raise
    except Exception as exc: raise DiagnosticoErro(boxe.erro_amigavel(exc))
