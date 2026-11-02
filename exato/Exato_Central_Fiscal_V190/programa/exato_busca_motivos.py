"""Por que a busca não aconteceu (V177): causas em português claro, registro por empresa/tipo e relatório (tela e PDF). Sem Tkinter.

Cada tentativa de busca (NF-e, NFC-e, CT-e e NFS-e) deixa uma ocorrência: deu certo, deu certo mas sem notas novas, ou não foi possível — com a CAUSA
explicada para uma pessoa (não para um programador) e o que fazer para resolver. O texto técnico original fica só no detalhe e no exato.log.
"""
from __future__ import annotations
import re, sqlite3
from datetime import datetime

TIPOS = (('nfe', 'NF-e'), ('nfce', 'NFC-e'), ('cte', 'CT-e'), ('nfse', 'NFS-e'))
NOME_TIPO = dict(TIPOS)

# código: (título curto, explicação, o que fazer, gravidade 'erro' | 'aviso' | 'info')
CAUSAS = {
    'ok': ('Busca concluída', 'A busca terminou normalmente.', '', 'info'),
    'sem_novas': ('Nada de novo', 'A busca terminou e não havia notas novas.', '', 'info'),
    'sem_certificado': ('Falta escolher o certificado digital',
                        'Para buscar NF-e, NFC-e e CT-e o Exato precisa de um certificado digital instalado no Windows e escolhido na tela Buscar XML. Nenhum estava escolhido.',
                        'Abra o menu Certificado, escolha o certificado (da empresa, ou do escritório quando há procuração) e clique em Usar.', 'erro'),
    'certificado_vencido': ('O certificado digital está vencido',
                            'O certificado escolhido passou da validade e a SEFAZ não aceita mais esse certificado.',
                            'Instale o certificado novo da empresa no Windows e escolha-o no menu Certificado.', 'erro'),
    'certificado_senha': ('Não foi possível usar o certificado digital',
                          'O Windows não liberou o certificado (senha errada, certificado sem a chave privada ou removido deste computador).',
                          'Confira se o certificado está instalado neste computador, com a chave privada, e tente de novo. Se pedir senha, digite a correta.', 'erro'),
    'certificado_outra_empresa': ('O certificado não é desta empresa',
                                  'O certificado escolhido pertence a outro CNPJ e a empresa não deu procuração para ele na SEFAZ.',
                                  'Escolha o certificado da própria empresa, ou cadastre a procuração eletrônica no portal da SEFAZ.', 'erro'),
    'sem_certificado_empresa': ('Esta empresa não tem certificado neste computador',
                                'A busca de NFS-e por certificado só funciona para empresas que têm certificado digital instalado neste computador.',
                                'Instale o certificado da empresa no Windows, ou use a busca por usuário e senha do portal (tela NFS-e).', 'aviso'),
    'procuracao_a_tentar': ('Será buscada pelo certificado do escritório (procuração)',
                            'A empresa não tem certificado neste computador. O Exato vai tentar a busca de NFS-e com o certificado escolhido na tela NFS-e, usando a procuração eletrônica da Receita Federal.',
                            'Nada a fazer agora: na próxima busca de NFS-e o Exato tenta sozinho. Se o Emissor Nacional não aceitar, ele explica o motivo aqui.', 'aviso'),
    'procuracao_nao_aceita': ('O Emissor Nacional não aceitou a procuração',
                              'O certificado do escritório foi recusado para esta empresa. Costuma ser procuração eletrônica ainda não cadastrada, vencida ou que não vale para os serviços da NFS-e.',
                              'Na Receita Federal, confira se a procuração para o escritório está ativa e inclui a NFS-e. O Exato tenta de novo sozinho depois de algumas horas; para tentar já, use Buscar na tela NFS-e.', 'erro'),
    'so_portal': ('Esta empresa só pode ser buscada pelo portal',
                  'A empresa não tem certificado digital neste computador, mas tem usuário e senha do portal guardados. A busca pelo portal pode pedir uma confirmação de segurança (captcha) e por isso não roda sozinha.',
                  'Na tela NFS-e, escolha a empresa e clique em Buscar; se o portal pedir confirmação, resolva na janela que abrir.', 'aviso'),
    'sem_usuario_senha': ('Falta o usuário e a senha do portal da NFS-e',
                          'A busca pelo portal precisa do usuário e da senha da empresa no Emissor Nacional, e eles não estão informados.',
                          'Na tela NFS-e, informe a senha da empresa (e marque para lembrar, se quiser que o Exato busque sozinho).', 'erro'),
    'senha_recusada': ('O portal recusou o usuário ou a senha',
                       'O Emissor Nacional não aceitou o acesso: usuário ou senha incorretos, ou a senha foi trocada.',
                       'Confirme a senha entrando no portal pelo navegador e, se mudou, informe a nova na tela NFS-e.', 'erro'),
    'captcha': ('O portal pediu confirmação de segurança (captcha)',
                'O portal exige que uma pessoa confirme que não é um robô. O Exato nunca resolve isso sozinho.',
                'Quando a janela do portal abrir, resolva a confirmação; o Exato continua do ponto onde parou.', 'aviso'),
    'portal_bloqueio': ('O portal bloqueou o acesso',
                        'O portal da NFS-e recusou os pedidos do Exato (erro 403). Costuma ser bloqueio temporário por muitos acessos.',
                        'Tente de novo mais tarde, ou marque "Mostrar o navegador" no menu Mais. Se continuar, envie a pasta Dados\\Logs\\nfse_portal ao suporte.', 'erro'),
    'portal_fora': ('O portal da NFS-e não respondeu',
                    'O site do Emissor Nacional está fora do ar ou muito lento neste momento.',
                    'Nada a fazer agora: o Exato tenta de novo na próxima busca. Se for urgente, tente pelo navegador.', 'erro'),
    'navegador': ('Não foi possível abrir o navegador',
                  'A busca pelo portal usa o Microsoft Edge e ele não abriu (não instalado, ou o componente do Exato não está instalado).',
                  'Instale o Microsoft Edge e abra o arquivo INSTALAR_COMPONENTE_NFSE.bat na pasta ferramentas.', 'erro'),
    'sefaz_consumo': ('A SEFAZ bloqueou novas consultas por um tempo',
                      'A SEFAZ limita quantas vezes se pode consultar (consumo indevido, códigos 656/657). Depois de muitas consultas seguidas ela pede para esperar.',
                      'Aguarde cerca de 1 hora. O Exato tenta de novo sozinho e continua do ponto onde parou.', 'aviso'),
    'vinculo_pendente': ('A SEFAZ ainda não liberou o acesso a esta empresa',
                         'A SEFAZ respondeu que este certificado ainda não está autorizado a baixar as notas desta empresa. Acontece quando o vínculo com o contador foi feito há pouco (a SEFAZ pode levar horas ou até um dia para valer) ou foi feito para outro CPF/CNPJ.',
                         'Confira no portal da SEFAZ se o vínculo está ativo para o MESMO CPF/CNPJ do certificado escolhido. O Exato tenta de novo sozinho de hora em hora nos primeiros dias.', 'aviso'),
    'sefaz_rejeicao': ('A SEFAZ recusou a consulta',
                       'A SEFAZ respondeu que não aceita a consulta nesse momento e informou um código de rejeição.',
                       'Veja o detalhe abaixo. Se for um código de certificado ou de cadastro, corrija e repita; se for de instabilidade, tente mais tarde.', 'erro'),
    'sefaz_fora': ('A SEFAZ não respondeu',
                   'O serviço da SEFAZ ficou fora do ar ou demorou demais para responder.',
                   'Nada a fazer agora: o Exato tenta de novo na próxima busca.', 'erro'),
    'sem_internet': ('Sem conexão com a internet',
                     'O Exato não conseguiu falar com a internet (rede desligada, firewall ou proxy).',
                     'Confira a conexão deste computador e tente de novo.', 'erro'),
    'janela': ('Aguardando a próxima janela de consulta',
               'A SEFAZ só libera uma nova consulta depois de um tempo. O Exato guardou o ponto de continuação.',
               'Nada a fazer: a busca continua sozinha quando a SEFAZ liberar.', 'aviso'),
    'cancelada_pelo_usuario': ('Busca cancelada',
                               'Você cancelou a busca antes de terminar. O que já chegou foi guardado.',
                               'Clique em "Buscar o que falta" para continuar de onde parou.', 'aviso'),
    'cancelada_sem_evento': ('Nota cancelada sem o XML do cancelamento',
                             'O Exato sabe que a nota foi cancelada, mas não tem o XML completo do cancelamento (só o aviso), que a Domínio precisa para cancelar ao importar.',
                             'NFS-e: baixe o XML do cancelamento no portal da prefeitura e importe na tela NFS-e (Importar XMLs). NF-e de fornecedor: a SEFAZ só entrega o XML completo depois da "Ciência da Operação" no portal ou no sistema do emissor.', 'aviso'),
    'erro_desconhecido': ('Aconteceu um erro que o Exato não soube explicar',
                          'A busca falhou por um motivo que o Exato ainda não reconhece. O detalhe técnico foi guardado no registro de erros.',
                          'Tente de novo. Se repetir, abra Manutenção > Abrir registro de erros e envie o arquivo exato.log ao suporte.', 'erro'),
}

# (expressão no texto, código), do mais específico para o mais geral
_REGRAS = (
    (r'capcha|captcha|confirmação de segurança', 'captcha'),
    (r'\bvencid|\bvencimento|expirad|fora da validade', 'certificado_vencido'),
    (r'nenhum certificado|selecione.*certificado|certificado.*selecion', 'sem_certificado'),
    (r'procura[cç][aã]o|não pertence ao cnpj|não pertence a esta empresa|cnpj base|certificado.*outro cnpj|ator.*n[aã]o autorizado', 'certificado_outra_empresa'),
    (r'chave privada|senha do certificado|acesso negado ao certificado|cryptographic|keyset', 'certificado_senha'),
    (r'cstat\s*65[67]|65[67]\b|consumo indevido|bloquead.*sef|bloqueio.*sef', 'sefaz_consumo'),
    (r'próxima janela|proxima janela|aguardando.*hora|ficará disponível', 'janela'),
    (r'senha.*(incorret|recusad|inválid|invalid)|usu[aá]rio.*senha.*(incorret|recus)|login.*(recus|inválid)|credenciais', 'senha_recusada'),
    (r'informe a senha|sem senha|não há senha|falta.*senha', 'sem_usuario_senha'),
    (r'microsoft edge|componente adicional|playwright|navegador.*(não|abrir)', 'navegador'),
    (r'\b403\b|recusou.*(tentativa|pedido)|portal.*(recus|bloque)|não liberou o acesso|voltou para a tela de login', 'portal_bloqueio'),
    (r'n[aã]o autoriz|sem autoriza|n[aã]o vinculad|v[ií]nculo|contabilista|n[aã]o habilitad|sem permiss|n[aã]o cadastrad', 'vinculo_pendente'),
    (r'cstat\s*\d{3}|rejei', 'sefaz_rejeicao'),
    (r'timeout|timed out|tempo esgotado|demorou|não respondeu|indispon|fora do ar|serviço em reprocessamento|erro do serviço', 'sefaz_fora'),
    (r'sem conex|connection|getaddrinfo|network|proxy|internet|\brede\b', 'sem_internet'),
    (r'cancelad[ao] pel[ao] (usu|pessoa)|busca cancelada|cancelado pelo usu', 'cancelada_pelo_usuario'),
)


CSTAT_SUCESSO = {'117', '118', '137', '138'}          # respostas da distribuição que significam "consulta feita": com documentos (138), sem documentos (137) ou aguardar (117/118)


def resposta_sefaz(detalhe):
    """V188: do detalhe gravado ('cStat 137: Nenhum documento localizado') tira (cStat, motivo). ('', '') se não houver."""
    m = re.match(r'\s*cStat\s*(\d{3,4})\s*:?\s*(.*)', str(detalhe or ''), re.S | re.I)
    return (m.group(1), re.sub(r'\s+', ' ', m.group(2)).strip()) if m else ('', '')


def texto_resposta(cstat, motivo):
    """Frase curta e clara com o que a SEFAZ respondeu."""
    motivo = re.sub(r'\s+', ' ', str(motivo or '')).strip()
    base = {'137': 'nenhum documento localizado', '138': 'documentos localizados', '117': 'sem documentos agora', '118': 'lote de documentos'}.get(str(cstat), '')
    texto = motivo or base or 'sem explicação'
    return f"A SEFAZ respondeu: {texto[:90]}" + (f" ({cstat})" if cstat else '')


def classificar(texto='', cstat='', origem=''):
    """Código da causa a partir do que o Exato recebeu (texto de erro, cStat, motivo). `origem`: 'nfse' ajuda a escolher entre portal e SEFAZ."""
    base = ((f'cstat {cstat} ' if str(cstat or '').strip() else '') + str(texto or '')).lower()
    if not base.strip(): return 'erro_desconhecido'
    for padrao, codigo in _REGRAS:
        if re.search(padrao, base):
            if origem == 'nfse' and codigo == 'sefaz_fora': return 'portal_fora'
            if origem == 'nfse' and codigo == 'sefaz_rejeicao': return 'portal_bloqueio'
            return codigo
    return 'erro_desconhecido'


def explicar(codigo):
    t, e, a, g = CAUSAS.get(codigo, CAUSAS['erro_desconhecido'])
    return {'codigo': codigo if codigo in CAUSAS else 'erro_desconhecido', 'titulo': t, 'explicacao': e, 'acao': a, 'gravidade': g}


# ------------------------------------------------------------------ registro
def preparar(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS busca_ocorrencias(
        id INTEGER PRIMARY KEY AUTOINCREMENT, cnpj TEXT NOT NULL, tipo TEXT NOT NULL, quando TEXT NOT NULL,
        resultado TEXT NOT NULL, codigo TEXT NOT NULL, detalhe TEXT DEFAULT '')""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_busca_oc_cnpj ON busca_ocorrencias(cnpj, tipo, id)")


def registrar(db_path, cnpj, tipos, codigo, detalhe='', quando=None):
    """Grava uma ocorrência por tipo. NUNCA levanta erro nem trava (espera curta): o registro é um auxílio, a busca é mais importante."""
    cnpj = re.sub(r'\D', '', str(cnpj or ''))
    if len(cnpj) != 14: return False
    tipos = [tipos] if isinstance(tipos, str) else list(tipos)
    resultado = 'ok' if codigo in ('ok', 'sem_novas') else ('falha' if explicar(codigo)['gravidade'] == 'erro' else 'aviso')
    quando = quando or datetime.now().isoformat(timespec='seconds')
    try:
        conn = sqlite3.connect(db_path, timeout=2)
        try:
            preparar(conn)
            for t in tipos:
                if t in NOME_TIPO:
                    conn.execute("INSERT INTO busca_ocorrencias(cnpj,tipo,quando,resultado,codigo,detalhe) VALUES(?,?,?,?,?,?)", (cnpj, t, quando, resultado, codigo, str(detalhe or '')[:600]))
                    conn.execute("DELETE FROM busca_ocorrencias WHERE cnpj=? AND tipo=? AND id NOT IN (SELECT id FROM busca_ocorrencias WHERE cnpj=? AND tipo=? ORDER BY id DESC LIMIT 40)", (cnpj, t, cnpj, t))
            conn.commit()
        finally:
            conn.close()
        return True
    except sqlite3.Error:
        return False


def ultimas(db_path):
    """{(cnpj, tipo): ocorrência mais recente} (dicionários com explicação)."""
    saida = {}
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            preparar(conn)
            for cnpj, tipo, quando, resultado, codigo, detalhe in conn.execute(
                    "SELECT cnpj,tipo,quando,resultado,codigo,detalhe FROM busca_ocorrencias WHERE id IN (SELECT MAX(id) FROM busca_ocorrencias GROUP BY cnpj,tipo)").fetchall():
                saida[(cnpj, tipo)] = dict(explicar(codigo), cnpj=cnpj, tipo=tipo, quando=quando, resultado=resultado, detalhe=detalhe)
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return saida


def historico(db_path, cnpj, limite=30):
    cnpj = re.sub(r'\D', '', str(cnpj or '')); saida = []
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            preparar(conn)
            for tipo, quando, resultado, codigo, detalhe in conn.execute("SELECT tipo,quando,resultado,codigo,detalhe FROM busca_ocorrencias WHERE cnpj=? ORDER BY id DESC LIMIT ?", (cnpj, int(limite))).fetchall():
                saida.append(dict(explicar(codigo), cnpj=cnpj, tipo=tipo, quando=quando, resultado=resultado, detalhe=detalhe))
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return saida


def diagnosticar(contexto):
    """Causas já conhecidas ANTES de buscar, só pelo que está configurado. `contexto`: {'cert_escolhido': bool, 'cert_vencido': bool,
    'empresa_tem_cert': bool, 'portal_login': bool, 'procuracao': bool}. Devolve {'xml': código|None, 'nfse': código|None}."""
    xml = None
    if not contexto.get('cert_escolhido'): xml = 'sem_certificado'
    elif contexto.get('cert_vencido'): xml = 'certificado_vencido'
    nfse = None
    if not contexto.get('empresa_tem_cert'):
        nfse = 'procuracao_a_tentar' if contexto.get('procuracao') else ('so_portal' if contexto.get('portal_login') else 'sem_certificado_empresa')          # V190: com o certificado do escritório escolhido a empresa será tentada por procuração
    return {'xml': xml, 'nfse': nfse}


def quando_texto(iso):
    try: return datetime.fromisoformat(str(iso)).strftime('%d/%m/%Y %H:%M')
    except (TypeError, ValueError): return ''


# ------------------------------------------------------------------ relatório em PDF
def gerar_pdf(caminho, empresas, titulo='Relatório da busca', logo=None):
    """`empresas`: [{'nome','cnpj','itens': [{'tipo','estado','resumo','quando','titulo','explicacao','acao','detalhe','gravidade'}]}]."""
    from html import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    ink = colors.HexColor('#0F172A'); muted = colors.HexColor('#64748B'); red = colors.HexColor('#E11D2E')
    st = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=st['Title'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=ink, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle('h2', parent=st['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=ink, spaceBefore=10, spaceAfter=2)
    small = ParagraphStyle('small', parent=st['BodyText'], fontName='Helvetica', fontSize=9, leading=12, textColor=muted)
    txt = ParagraphStyle('txt', parent=st['BodyText'], fontName='Helvetica', fontSize=9.5, leading=13, textColor=ink)
    cores = {'erro': '#B91C1C', 'aviso': '#B45309', 'info': '#15803D'}
    doc = SimpleDocTemplate(str(caminho), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=16 * mm, title=titulo)
    story = []
    if logo:
        try:
            img = Image(str(logo), hAlign='LEFT'); sc = min((42 * mm) / img.imageWidth, (13 * mm) / img.imageHeight); img.drawWidth = img.imageWidth * sc; img.drawHeight = img.imageHeight * sc; story += [img, Spacer(1, 3 * mm)]
        except Exception: pass
    story += [Paragraph(escape(titulo), h1), Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} • {len(empresas)} empresa(s)", small), Spacer(1, 3 * mm)]
    if not empresas: story.append(Paragraph('Nenhuma empresa para mostrar.', txt))
    for emp in empresas:
        bloco = [Paragraph(f"{escape(emp.get('nome') or 'Empresa')} <font size=9 color='#64748B'>— CNPJ {escape(str(emp.get('cnpj') or ''))}</font>", h2)]
        linhas = []
        for it in emp.get('itens') or []:
            cor = cores.get(it.get('gravidade'), '#0F172A')
            texto = f"<b>{escape(NOME_TIPO.get(it.get('tipo'), it.get('tipo') or ''))}</b> — <font color='{cor}'><b>{escape(it.get('titulo') or '')}</b></font>"
            if it.get('resumo'): texto += f" <font color='#64748B'>({escape(it['resumo'])})</font>"
            partes = [texto]
            if it.get('explicacao') and it.get('gravidade') != 'info': partes.append(escape(it['explicacao']))
            if it.get('acao'): partes.append(f"<b>O que fazer:</b> {escape(it['acao'])}")
            if it.get('detalhe') and it.get('gravidade') != 'info': partes.append(f"<font size=8 color='#64748B'>Detalhe: {escape(str(it['detalhe'])[:300])}</font>")
            if it.get('quando'): partes.append(f"<font size=8 color='#64748B'>Última tentativa: {escape(quando_texto(it['quando']) or str(it['quando']))}</font>")
            linhas.append([Paragraph('<br/>'.join(partes), txt)])
        if linhas:
            t = Table(linhas, colWidths=[178 * mm]); t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#E6EAF1')), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LINEBEFORE', (0, 0), (0, -1), 2, red)]))
            bloco.append(t)
        else:
            bloco.append(Paragraph('Sem informações de busca ainda.', small))
        story.append(KeepTogether(bloco[:2]))
        story.extend(bloco[2:])
    def rodape(canvas, d):
        canvas.saveState(); canvas.setFont('Helvetica', 8); canvas.setFillColor(muted)
        canvas.drawString(16 * mm, 8 * mm, 'Exato Central Fiscal'); canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f'Página {d.page}'); canvas.restoreState()
    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return str(caminho)
