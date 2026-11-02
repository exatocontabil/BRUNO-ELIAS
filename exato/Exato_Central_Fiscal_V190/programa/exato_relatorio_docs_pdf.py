"""Relatório em PDF da tela Documentos fiscais (V181). Sem Tkinter, sem os núcleos protegidos.

Estrutura (definida pelo usuário): o relatório é dividido em SEÇÕES por tipo e movimentação, sempre separando os dois lados:
NF-e (SAÍDA) / NF-e (ENTRADA), NFC-e (SAÍDA) / NFC-e (ENTRADA), NFS-e (PRESTADOS) / NFS-e (TOMADOS), CT-e (PRESTADOS) / CT-e (TOMADOS).
FATURAMENTO = NF-e saída + NFC-e saída + NFS-e prestados + CT-e prestados; todo o resto é DESPESA. A análise (quadros, gráficos, resultado)
compara sempre faturamento com despesa. NÃO existe "total geral de autorizadas": cada seção tem só os totais dela, com autorizadas e
canceladas separadas, e nenhum total soma entrada com saída. Cancelada nunca entra no valor das autorizadas.

Linha normalizada (dict): familia ('nfe'|'nfce'|'cte'|'nfse'), movimentacao ('Entrada'|'Saída'|'Prestado'|'Tomado'), numero, serie, data (AAAA-MM-DD), valor,
situacao ('Autorizada'|'Cancelada'|outra), exportada, chave, parte (nome da outra parte), doc, empresa, cnpj e, só NFS-e, aliquota, iss, iss_retido, iss_fora, municipio.
"""
import re
from datetime import datetime
import exato_numeracao as numeracao
from decimal import Decimal
from html import escape, unescape

TIPOS = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}
ORDEM = ('nfe', 'nfce', 'nfse', 'cte')
COR_TIPO = {'nfe': '#2563EB', 'nfce': '#D97706', 'cte': '#16A34A', 'nfse': '#7C3AED'}
VERMELHO = '#E11D2E'; TINTA = '#0F172A'; MUDO = '#64748B'; LINHA = '#E6EAF1'; SUAVE = '#EEF2F7'; ALERTA = '#B91C1C'
COR_FAT = '#16A34A'; COR_DESP = '#E11D2E'
ZERO = Decimal('0.00')
W = 269                     # largura útil da página (mm)


def _dec(v):
    try: return Decimal(str(v)) if v not in (None, '') else ZERO
    except Exception: return ZERO


def money(v):
    try: d = Decimal(str(v if v not in (None, '') else 0))
    except Exception: return str(v)
    return ('-' if d < 0 else '') + 'R$ ' + f'{abs(d):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _doc(d):
    d = re.sub(r'\D', '', str(d or ''))
    if len(d) == 14: return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}'
    if len(d) == 11: return f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}'
    return d or '—'


def _br(data):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(data or ''))
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m else (str(data or '') or '—')


def _mes(chave):
    m = re.match(r'(\d{4})-(\d{2})', str(chave or ''))
    nomes = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
    return f'{nomes[int(m.group(2)) - 1]}/{m.group(1)[2:]}' if m and 1 <= int(m.group(2)) <= 12 else 'sem data'


def ajustar(texto, largura_mm, fonte='Helvetica', tamanho=7.6, folga_pt=14):
    """Corta o texto pela LARGURA REAL (não por caracteres) para caber na coluna de `largura_mm`, com '…'. Nunca passa da borda."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    texto = str(texto or ''); limite = largura_mm * 72.0 / 25.4 - folga_pt
    if stringWidth(texto, fonte, tamanho) <= limite: return texto
    while texto and stringWidth(texto + '…', fonte, tamanho) > limite: texto = texto[:-1]
    return texto.rstrip() + '…'


def _cancelada(r):
    return str(r.get('situacao') or '') == 'Cancelada'


def _autorizada(r):
    return str(r.get('situacao') or '') == 'Autorizada'


def _saida(r):
    return str(r.get('movimentacao') or '') in ('Saída', 'Prestado')


def lado_da(familia, saida):
    """'faturamento' (NF-e/NFC-e saída, NFS-e/CT-e prestados) ou 'despesa' (o resto)."""
    return 'faturamento' if saida else 'despesa'


def rotulo_secao(familia, saida):
    """Ex.: 'NF-e (SAÍDA)', 'NFS-e (TOMADOS)', 'CT-e (PRESTADOS)'."""
    if familia in ('nfse', 'cte'): lado = 'PRESTADOS' if saida else 'TOMADOS'
    else: lado = 'SAÍDA' if saida else 'ENTRADA'
    return f'{TIPOS[familia]} ({lado})'


def normalizar(rows_db, extras=None):
    """Linhas do banco (`db_list_documents`) -> linhas do relatório. `extras`: {doc_id: dict com parte/doc/aliquota/iss/... lido do XML}."""
    extras = extras or {}; saida = []
    for r in rows_db or []:
        fam = str(r.get('family') or '').lower()
        if fam not in TIPOS: continue
        ex = extras.get(r.get('doc_id')) or {}
        st = str(r.get('status') or '')
        sit = 'Cancelada' if st == 'Cancelado' else ('Autorizada' if st == 'Autorizado' else (st or '—'))
        mov = ex.get('movimentacao') or r.get('direction') or ''
        if fam == 'cte': mov = {'Saída': 'Prestado', 'Entrada': 'Tomado'}.get(mov, mov)
        saida.append({'familia': fam, 'movimentacao': mov, 'numero': str(r.get('number') or ''), 'serie': str(r.get('series') or ''), 'data': str(r.get('issued_at') or '')[:10],
                      'valor': _dec(r.get('value')), 'situacao': sit, 'exportada': bool(r.get('exported_any')), 'chave': str(r.get('access_key') or ''),
                      'parte': unescape(str(ex.get('parte', '') or '')), 'doc': ex.get('doc', ''), 'empresa': str(r.get('company_name') or r.get('cnpj') or ''), 'cnpj': str(r.get('cnpj') or ''),
                      'optante': ex.get('optante'), 'credito': ex.get('credito'), 'cred_valor': ex.get('cred_valor'), 'cred_aliq': ex.get('cred_aliq'),
                      'aliquota': ex.get('aliquota'), 'iss': ex.get('iss'), 'iss_retido': ex.get('iss_retido'), 'iss_fora': ex.get('iss_fora'), 'municipio': ex.get('municipio')})
    return saida


_RE_BLOCO = {'dest': re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?dest\b.*?</(?:[A-Za-z_][\w.-]*:)?dest>', re.S), 'emit': re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?emit\b.*?</(?:[A-Za-z_][\w.-]*:)?emit>', re.S)}
_RE_NOME = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?xNome\s*>\s*([^<]*?)\s*<')
_RE_DOC = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?(CNPJ|CPF)\s*>\s*(\d+)\s*<')


def outra_parte(xml, direcao):
    """Nome e documento da outra parte de uma NF-e/NFC-e/CT-e, lidos do XML (Saída = destinatário; Entrada = emitente). `&amp;` e afins viram o caractere. Nunca levanta erro."""
    try:
        data = bytes(xml or b'')
        bloco = _RE_BLOCO['emit' if direcao == 'Entrada' else 'dest'].search(data)
        if not bloco: return {'parte': '', 'doc': ''}
        b = bloco.group(0); n = _RE_NOME.search(b); d = _RE_DOC.search(b)
        return {'parte': unescape(n.group(1).decode('utf-8', 'replace')) if n else '', 'doc': d.group(2).decode('ascii') if d else ''}
    except Exception:
        return {'parte': '', 'doc': ''}


_RE_CRT = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?CRT\s*>\s*(\d)\s*<')
_RE_CSOSN = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?CSOSN\s*>\s*(\d{3})\s*<')
_RE_VCRED = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?vCredICMSSN\s*>\s*([\d.,]+)\s*<')
_RE_PCRED = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?pCredSN\s*>\s*([\d.,]+)\s*<')
_RE_INFCPL = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?infCpl\s*>(.*?)</(?:[A-Za-z_][\w.-]*:)?infCpl>', re.S)
_CSOSN_COM_CREDITO = {'101', '201'}          # tributada pelo Simples Nacional COM permissão de crédito (sem e com substituição tributária)


def simples_credito(xml):
    """V187 (compras): o fornecedor é optante pelo Simples Nacional? e a nota PERMITE o aproveitamento do crédito de ICMS?
    Lê do XML da NF-e: CRT do emitente (1, 2 ou 4 = Simples/MEI; 3 = regime normal), CSOSN 101/201 (permissão de crédito), `vCredICMSSN`/`pCredSN` e, na falta deles,
    a frase das informações complementares ("permite o aproveitamento do crédito de ICMS"). Devolve {'optante': 'Sim'|'Não'|'—', 'credito': 'Sim'|'Não'|'—',
    'cred_valor': Decimal|None, 'cred_aliq': Decimal|None}. Sem dado no XML = '—' (nunca 'Não'). Nunca levanta erro."""
    vazio = {'optante': '—', 'credito': '—', 'cred_valor': None, 'cred_aliq': None}
    try:
        data = bytes(xml or b''); em = _RE_BLOCO['emit'].search(data); crt = _RE_CRT.search(em.group(0) if em else data)
        if not crt: return vazio
        regime = crt.group(1).decode('ascii')
        if regime not in ('1', '2', '3', '4'): return vazio
        if regime == '3': return dict(vazio, optante='Não')          # regime normal: o crédito vem do ICMS destacado, não desta regra
        csosn = {m.group(1).decode('ascii') for m in _RE_CSOSN.finditer(data)}
        valores = [_dec(m.group(1).decode('ascii').replace(',', '.')) for m in _RE_VCRED.finditer(data)]
        total = sum((v for v in valores if v > 0), ZERO)
        aliqs = [_dec(m.group(1).decode('ascii').replace(',', '.')) for m in _RE_PCRED.finditer(data)]; aliq = max(aliqs) if aliqs and max(aliqs) > 0 else None
        cpl = _RE_INFCPL.search(data); texto = unescape(cpl.group(1).decode('utf-8', 'replace')).lower() if cpl else ''
        frase = 'aproveitamento' in texto and ('crédito' in texto or 'credito' in texto)
        if total > 0 or (csosn & _CSOSN_COM_CREDITO) or (not csosn and frase) or ('900' in csosn and frase):
            return {'optante': 'Sim', 'credito': 'Sim', 'cred_valor': total if total > 0 else None, 'cred_aliq': aliq}
        return {'optante': 'Sim', 'credito': 'Não' if csosn else '—', 'cred_valor': None, 'cred_aliq': None}
    except Exception:
        return vazio


def secoes(linhas):
    """{(familia, saida?): {'itens': [...], 'an','av','cn','cv','exp_canc'}} só do que existe, com os dois lados de cada tipo presente."""
    por = {}
    for r in linhas:
        k = (r['familia'], _saida(r))
        g = por.setdefault(k, {'itens': [], 'an': 0, 'av': ZERO, 'cn': 0, 'cv': ZERO, 'exp_canc': 0})
        g['itens'].append(r)
        if _cancelada(r):
            g['cn'] += 1; g['cv'] += r['valor']
            if r.get('exportada'): g['exp_canc'] += 1
        elif _autorizada(r):
            g['an'] += 1; g['av'] += r['valor']
    for fam in {k[0] for k in por}:          # os dois lados de cada tipo, sempre
        for lado in (True, False): por.setdefault((fam, lado), {'itens': [], 'an': 0, 'av': ZERO, 'cn': 0, 'cv': ZERO, 'exp_canc': 0})
    return por


def ordem_secoes(por):
    """Faturamento primeiro (NF-e, NFC-e, NFS-e, CT-e) e depois despesa, na mesma ordem."""
    return [(f, s) for s in (True, False) for f in ORDEM if (f, s) in por]


def analise(linhas):
    """Faturamento x despesa (só autorizadas): totais, por mês, por tipo e principais clientes/fornecedores. Nada de total geral de documentos."""
    fat = ZERO; desp = ZERO; meses = {}; tipo_fat = {}; tipo_desp = {}; clientes = {}; fornec = {}
    for r in linhas:
        if not _autorizada(r): continue
        v = r['valor']; saida = _saida(r)
        k = str(r.get('data') or '')[:7] if re.match(r'\d{4}-\d{2}', str(r.get('data') or '')) else 'sem data'
        m = meses.setdefault(k, {'fat': ZERO, 'desp': ZERO})
        nome = (r.get('parte') or '').strip() or '—'
        if saida:
            fat += v; m['fat'] += v; tipo_fat[r['familia']] = tipo_fat.get(r['familia'], ZERO) + v; clientes[nome] = clientes.get(nome, ZERO) + v
        else:
            desp += v; m['desp'] += v; tipo_desp[r['familia']] = tipo_desp.get(r['familia'], ZERO) + v; fornec[nome] = fornec.get(nome, ZERO) + v
    top = lambda d: sorted(((n, v) for n, v in d.items() if n != '—'), key=lambda x: -x[1])[:5]
    return {'faturamento': fat, 'despesa': desp, 'resultado': fat - desp, 'meses': meses, 'tipo_fat': tipo_fat, 'tipo_desp': tipo_desp, 'clientes': top(clientes), 'fornecedores': top(fornec)}


def gerar(linhas, caminho, empresa='', cnpj='', periodo='Todo o período', filtros=None, logo=None, progresso=None):
    """Gera o PDF. `empresa`/`cnpj`: da empresa filtrada (vazio = várias). `filtros`: textos em português. Devolve o caminho."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rlcanvas
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, CondPageBreak, KeepTogether
    from reportlab.graphics.shapes import Drawing, String, Rect, Line
    from reportlab.graphics.charts.barcharts import VerticalBarChart

    hx = colors.HexColor
    st = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=st['Title'], fontName='Helvetica-Bold', fontSize=24, leading=28, textColor=hx(TINTA), alignment=0, spaceAfter=3)
    h2 = ParagraphStyle('h2', parent=st['Heading2'], fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=hx(TINTA), spaceBefore=6, spaceAfter=3)
    peq = ParagraphStyle('peq', parent=st['BodyText'], fontName='Helvetica', fontSize=9, leading=12, textColor=hx(MUDO))
    corpo = ParagraphStyle('corpo', parent=st['BodyText'], fontName='Helvetica', fontSize=9, leading=12, textColor=hx(TINTA))
    cel = ParagraphStyle('cel', parent=corpo, fontSize=8.6, leading=11)
    celr = ParagraphStyle('celr', parent=cel, alignment=2)
    cab = ParagraphStyle('cab', parent=cel, fontName='Helvetica-Bold', textColor=colors.white)
    cabr = ParagraphStyle('cabr', parent=cab, alignment=2)
    neg = ParagraphStyle('neg', parent=cel, fontName='Helvetica-Bold')
    negr = ParagraphStyle('negr', parent=neg, alignment=2)
    kv = ParagraphStyle('kv', parent=corpo, fontName='Helvetica-Bold', fontSize=15, leading=19)
    kt = ParagraphStyle('kt', parent=peq, fontName='Helvetica-Bold', fontSize=7.5, leading=10)

    class _Numerada(rlcanvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); self._estados = []
        def showPage(self):
            self._estados.append(dict(self.__dict__)); self._startPage()
        def save(self):
            total = len(self._estados)
            for estado in self._estados:
                self.__dict__.update(estado); self._rodape(total); super().showPage()
            super().save()
        def _rodape(self, total):
            self.setFont('Helvetica', 8); self.setFillColor(hx(MUDO))
            self.drawString(14 * mm, 8 * mm, f"Exato Central Fiscal • gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            self.drawRightString(landscape(A4)[0] - 14 * mm, 8 * mm, f'Página {self._pageNumber} de {total}')
            if self._pageNumber > 1:
                self.setFont('Helvetica', 8); self.drawString(14 * mm, landscape(A4)[1] - 9 * mm, ajustar(f"Documentos fiscais • {empresa or 'Várias empresas'}" + (f' • CNPJ {_doc(cnpj)}' if cnpj else '') + f' • {periodo}', 250, 'Helvetica', 8, 0))
                self.setStrokeColor(hx(VERMELHO)); self.setLineWidth(1.2); self.line(14 * mm, landscape(A4)[1] - 11 * mm, landscape(A4)[0] - 14 * mm, landscape(A4)[1] - 11 * mm)

    doc = SimpleDocTemplate(str(caminho), pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=15 * mm, bottomMargin=16 * mm, title='Relatório de documentos fiscais')
    story = []
    por = secoes(linhas); ordem = ordem_secoes(por); ana = analise(linhas)
    varias = len({r.get('cnpj') for r in linhas if r.get('cnpj')}) > 1
    base = [('GRID', (0, 0), (-1, -1), 0.3, hx(LINHA)), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]

    # ------------------------------------------------------------------ capa
    if logo:
        try:
            img = Image(str(logo), hAlign='LEFT'); sc = min((42 * mm) / img.imageWidth, (13 * mm) / img.imageHeight); img.drawWidth = img.imageWidth * sc; img.drawHeight = img.imageHeight * sc; story += [img, Spacer(1, 4 * mm)]
        except Exception: pass
    story += [Paragraph('Relatório de documentos fiscais', h1),
              Paragraph(f'<b>{escape(empresa or "Várias empresas")}</b>' + (f'  •  CNPJ {escape(_doc(cnpj))}' if cnpj else ''), corpo),
              Paragraph(f'Período: {escape(periodo)}  •  {len(linhas):,} documento(s)'.replace(',', '.'), peq)]
    if filtros: story.append(Paragraph('Filtros: ' + escape('  •  '.join(filtros)), peq))
    story.append(Spacer(1, 5 * mm))

    def cartao(titulo, valor, sub, cor):
        t = Table([[Paragraph(titulo, kt)], [Paragraph(f'<font color="{cor}">{escape(valor)}</font>', kv)], [Paragraph(escape(sub), peq)]], colWidths=[85 * mm])
        t.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, hx(LINHA)), ('BACKGROUND', (0, 0), (-1, -1), hx('#F8FAFC')), ('LINEBEFORE', (0, 0), (0, -1), 3, hx(cor)),
                               ('LEFTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        return t
    res = ana['resultado']
    cartoes = Table([[cartao('FATURAMENTO', money(ana['faturamento']), 'NF-e e NFC-e saída • NFS-e e CT-e prestados', COR_FAT), cartao('DESPESA', money(ana['despesa']), 'NF-e e NFC-e entrada • NFS-e e CT-e tomados', COR_DESP),
                      cartao('FATURAMENTO − DESPESA', money(res), 'análise do período (não é total de documentos)', '#2563EB' if res >= 0 else ALERTA)]], colWidths=[W / 3 * mm] * 3, hAlign='LEFT')
    cartoes.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 4)]))
    story += [cartoes, Spacer(1, 5 * mm)]

    def quadro(titulo, cor, saida):
        linhas_q = [[Paragraph(titulo, cab), Paragraph('Notas', cabr), Paragraph('Valor', cabr), Paragraph('Canceladas', cabr)]]; tn = 0; tv = ZERO
        for fam, s in ordem:
            if s != saida: continue
            g = por[(fam, s)]
            linhas_q.append([Paragraph(f'<font color="{COR_TIPO[fam]}"><b>■</b></font> {escape(rotulo_secao(fam, s))}', cel), Paragraph(str(g['an']), celr), Paragraph(money(g['av']), celr),
                             Paragraph(f'<font color="{ALERTA}">{g["cn"]} • {money(g["cv"])}</font>' if g['cn'] else '—', celr)])
            tn += g['an']; tv += g['av']
        if len(linhas_q) == 1: linhas_q.append([Paragraph('Nenhum documento.', cel), '', '', ''])
        linhas_q.append([Paragraph('Total do lado', neg), Paragraph(str(tn), negr), Paragraph(money(tv), negr), ''])
        t = Table(linhas_q, colWidths=[52 * mm, 16 * mm, 33 * mm, 31 * mm], repeatRows=1)
        t.setStyle(TableStyle(base + [('BACKGROUND', (0, 0), (-1, 0), hx(cor)), ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, hx('#F8FAFC')]), ('BACKGROUND', (0, -1), (-1, -1), hx(SUAVE)), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        return t
    dois = Table([[quadro('FATURAMENTO (saídas / prestados)', COR_FAT, True), quadro('DESPESA (entradas / tomados)', COR_DESP, False)]], colWidths=[W / 2 * mm] * 2, hAlign='LEFT')
    dois.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story += [dois, Spacer(1, 2 * mm),
              Paragraph('Os valores são das notas AUTORIZADAS; as canceladas aparecem à parte e nunca entram nos valores. Faturamento e despesa nunca são somados entre si. Cada tipo de documento tem uma seção para cada lado, a partir da próxima página.', peq)]
    exp_total = sum(g['exp_canc'] for g in por.values())
    if exp_total: story += [Spacer(1, 2 * mm), Paragraph(f'<font color="{ALERTA}"><b>Atenção:</b> {exp_total} nota(s) cancelada(s) já foram exportadas. Confira na Domínio.</font>', corpo)]

    # ------------------------------------------------------------------ análise: faturamento x despesa
    meses = ana['meses']; chaves = sorted(meses)[-12:]
    if chaves and (ana['faturamento'] > 0 or ana['despesa'] > 0):
        story += [PageBreak(), Paragraph('Faturamento x despesa', h2), Spacer(1, 2 * mm)]

        def barras(titulo, series, cores, nomes, largura=135, altura=50):
            d = Drawing(largura * mm, altura * mm); d.add(String(0, (altura - 5) * mm, titulo, fontName='Helvetica-Bold', fontSize=9, fillColor=hx(TINTA)))
            bc = VerticalBarChart(); bc.x = 14 * mm; bc.y = 9 * mm; bc.width = (largura - 18) * mm; bc.height = (altura - 22) * mm
            bc.data = series; bc.categoryAxis.categoryNames = [_mes(m) for m in chaves]; bc.categoryAxis.labels.fontSize = 7; bc.valueAxis.labels.fontSize = 7
            topo = max((max(abs(x) for x in s) for s in series if s), default=0)
            baixo = min((min(x) for x in series if x), default=0); alto = max((max(x) for x in series if x), default=0)
            bc.valueAxis.valueMin = min(0, baixo * 1.12); bc.valueAxis.valueMax = max(0, alto * 1.12) or 1; bc.categoryAxis.joinAxisMode = 'bottom'
            bc.valueAxis.labelTextFormat = (lambda v: f'{v / 1000:.0f} mil') if topo >= 10000 else (lambda v: f'{v:.0f}')
            bc.bars.strokeColor = None; bc.groupSpacing = 6; bc.barSpacing = 1; bc.valueAxis.gridStrokeColor = hx(LINHA); bc.valueAxis.visibleGrid = 1
            for i, c in enumerate(cores): bc.bars[i].fillColor = hx(c)
            d.add(bc)
            for i, n in enumerate(nomes): d.add(String((largura - 40 + i * 0) * mm - len(nomes) * 0, (altura - 5 - 5 * i) * mm, f'■ {n}', fontName='Helvetica-Bold', fontSize=7.5, fillColor=hx(cores[i])))
            return d
        fat_m = [float(meses[m]['fat']) for m in chaves]; des_m = [float(meses[m]['desp']) for m in chaves]
        g1 = barras('Faturamento x despesa por mês', [fat_m, des_m], [COR_FAT, COR_DESP], ['Faturamento', 'Despesa'])
        g2 = barras('Resultado do mês (faturamento − despesa)', [[a - b for a, b in zip(fat_m, des_m)]], ['#2563EB'], ['Resultado'])
        gt = Table([[g1, g2]], colWidths=[135 * mm, 134 * mm], hAlign='LEFT'); gt.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [gt, Spacer(1, 3 * mm)]

        # participação de cada tipo, lado a lado: faturamento | despesa
        def particao(titulo, dados, cor, total):
            linhas_p = [[Paragraph(titulo, cab), Paragraph('Valor', cabr), Paragraph('% do lado', cabr)]]
            for fam in ORDEM:
                if fam not in dados: continue
                v = dados[fam]; pct = (v / total * 100) if total else ZERO
                linhas_p.append([Paragraph(f'<font color="{COR_TIPO[fam]}"><b>■</b></font> {TIPOS[fam]}', cel), Paragraph(money(v), celr), Paragraph(f'{pct:.1f}%'.replace('.', ','), celr)])
            if len(linhas_p) == 1: linhas_p.append([Paragraph('—', cel), '', ''])
            t = Table(linhas_p, colWidths=[50 * mm, 45 * mm, 35 * mm]); t.setStyle(TableStyle(base + [('BACKGROUND', (0, 0), (-1, 0), hx(cor)), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
            return t
        pp = Table([[particao('Composição do FATURAMENTO', ana['tipo_fat'], COR_FAT, ana['faturamento']), particao('Composição da DESPESA', ana['tipo_desp'], COR_DESP, ana['despesa'])]], colWidths=[W / 2 * mm] * 2, hAlign='LEFT')
        pp.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [pp, Spacer(1, 3 * mm)]

        # quadro mensal
        md = [[Paragraph(x, h) for x, h in (('Mês', cab), ('Faturamento', cabr), ('Despesa', cabr), ('Faturamento − despesa', cabr), ('Despesa / faturamento', cabr))]]
        for m in sorted(meses):
            f_, d_ = meses[m]['fat'], meses[m]['desp']
            md.append([Paragraph(_mes(m), cel), Paragraph(money(f_), celr), Paragraph(money(d_), celr), Paragraph(f'<font color="{ALERTA if f_ - d_ < 0 else TINTA}">{money(f_ - d_)}</font>', celr),
                       Paragraph((f'{d_ / f_ * 100:.0f}%' if f_ else '—'), celr)])
        mt = Table(md, colWidths=[40 * mm, 55 * mm, 55 * mm, 60 * mm, 59 * mm], repeatRows=1, hAlign='LEFT')
        mt.setStyle(TableStyle(base + [('BACKGROUND', (0, 0), (-1, 0), hx(TINTA)), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, hx('#F8FAFC')]), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        story.append(KeepTogether([mt]))

        # maiores clientes (faturamento) e fornecedores (despesa)
        def top(titulo, lista, cor):
            linhas_t = [[Paragraph(titulo, cab), Paragraph('Valor', cabr)]]
            for n, v in lista: linhas_t.append([Paragraph(escape(ajustar(n, 90, 'Helvetica', 8.6)), cel), Paragraph(money(v), celr)])
            if len(linhas_t) == 1: linhas_t.append([Paragraph('—', cel), ''])
            t = Table(linhas_t, colWidths=[92 * mm, 40 * mm]); t.setStyle(TableStyle(base + [('BACKGROUND', (0, 0), (-1, 0), hx(cor)), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
            return t
        if ana['clientes'] or ana['fornecedores']:
            tp = Table([[top('Maiores CLIENTES (faturamento)', ana['clientes'], COR_FAT), top('Maiores FORNECEDORES (despesa)', ana['fornecedores'], COR_DESP)]], colWidths=[W / 2 * mm] * 2, hAlign='LEFT')
            tp.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story += [CondPageBreak(32 * mm), Spacer(1, 3 * mm), tp]

    # ------------------------------------------------------------------ uma seção para cada tipo e lado (sempre separados)
    feitos = 0
    for fam, saida in ordem:
        g = por[(fam, saida)]; itens = g['itens']; fat = lado_da(fam, saida) == 'faturamento'
        cor = COR_TIPO[fam]; rotulo = rotulo_secao(fam, saida)
        story += [PageBreak() if itens else CondPageBreak(45 * mm), Spacer(1, 0 if itens else 4 * mm)]          # lado sem documentos: só a faixa e o aviso, sem página própria
        faixa = Table([[Paragraph(f'<font color="white"><b>{escape(rotulo)}</b></font>', ParagraphStyle('faixa', parent=h1, fontSize=17, leading=21, textColor=colors.white)),
                        Paragraph(f'<font color="white">{"FATURAMENTO" if fat else "DESPESA"}  •  {len(itens)} documento(s)</font>', ParagraphStyle('faixad', parent=corpo, alignment=2, textColor=colors.white, fontSize=10))]], colWidths=[150 * mm, 119 * mm])
        faixa.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), hx(cor)), ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        story += [faixa, Spacer(1, 3 * mm)]
        if not itens:
            story += [Paragraph('Nenhum documento deste tipo e movimentação neste filtro.', corpo)]
            continue
        itens = sorted(itens, key=lambda r: (str(r.get('data') or ''), str(r.get('numero') or '').zfill(12)))
        aut = [r for r in itens if _autorizada(r)]; can = [r for r in itens if _cancelada(r)]
        va = g['av']; vc = g['cv']
        qd = [[Paragraph(x, h) for x, h in (('Autorizadas (notas)', cabr), ('Autorizadas (valor)', cabr), ('Canceladas (notas)', cabr), ('Canceladas (valor)', cabr))]]
        qd.append([Paragraph(str(len(aut)), negr), Paragraph(money(va), negr), Paragraph(f'<font color="{ALERTA}">{len(can)}</font>' if can else '0', negr), Paragraph(f'<font color="{ALERTA}">{money(vc)}</font>' if can else money(vc), negr)])
        qt = Table(qd, colWidths=[W / 4 * mm] * 4, hAlign='LEFT')
        qt.setStyle(TableStyle(base + [('BACKGROUND', (0, 0), (-1, 0), hx(TINTA)), ('BACKGROUND', (0, 1), (-1, 1), hx(SUAVE))]))
        story.append(qt)
        exp_c = [r for r in can if r.get('exportada')]
        if exp_c: story += [Spacer(1, 2 * mm), Paragraph(f'<font color="{ALERTA}"><b>{len(exp_c)} nota(s) cancelada(s) já exportada(s):</b> confira na Domínio.</font>', corpo)]
        if fam == 'nfse':
            fora = [r for r in aut if r.get('iss_fora') == 'SIM']
            iss_a = sum((_dec(r.get('iss')) for r in aut), ZERO); iss_f = sum((_dec(r.get('iss')) for r in fora), ZERO); iss_r = sum((_dec(r.get('iss')) for r in aut if r.get('iss_retido') == 'Sim'), ZERO)
            story += [Spacer(1, 2 * mm), Paragraph(f'ISS das autorizadas: <b>{money(iss_a)}</b>  •  ISS retido: <b>{money(iss_r)}</b>  •  ISS pago fora do município do prestador: <b>{money(iss_f)}</b> ({len(fora)} nota(s))', corpo)]
        if fam in ('nfe', 'nfce') and saida:          # V182: números que não existem na sequência de cada série (conferir: nota que não chegou ou número inutilizado)
            for serie, faixas in numeracao.lacunas(itens).items():
                story += [Spacer(1, 2 * mm), Paragraph(f'<font color="{ALERTA}"><b>Numeração faltando</b></font> (série {escape(serie)}, {numeracao.total_faltando(faixas)} número(s)): {escape(numeracao.texto_faixas(faixas, 30))}. '
                                                       'Se o número foi inutilizado na SEFAZ, é normal faltar.', corpo)]
        story.append(Spacer(1, 4 * mm))
        if fam == 'nfse':
            titulos = ['Nº', 'Emissão', 'Outra parte', 'CNPJ / CPF', 'Valor', 'Alíq.', 'ISS', 'Retido', 'ISS fora?', 'Município', 'Situação', 'Exp.']
            larg = [15, 18, 60, 31, 22, 12, 19, 15, 14, 31, 20, 12]; direita = {4, 5, 6}; vi = 4; i_parte = 2; i_mun = 9
        elif fam == 'nfe' and not saida:          # V187: compras de NF-e: o fornecedor é do Simples Nacional? a nota permite aproveitar o crédito de ICMS?
            titulos = ['Nº', 'Série', 'Emissão', 'Outra parte', 'Chave de acesso', 'Valor', 'Optante pelo Simples Nacional?', 'Permite aproveitamento?', 'Situação', 'Exp.']
            larg = [14, 12, 18, 46, 66, 24, 22, 38, 18, 11]; direita = {5}; vi = 5; i_parte = 3; i_mun = None
            cred_ok = [r for r in aut if r.get('credito') == 'Sim']; cred_total = sum((_dec(r.get('cred_valor')) for r in cred_ok), ZERO)
            story += [Paragraph(f'Fornecedores do Simples Nacional que permitem o aproveitamento do crédito de ICMS: <b>{len(cred_ok)}</b> nota(s) autorizada(s)'
                                + (f', crédito informado de <b>{money(cred_total)}</b>' if cred_total > 0 else '') + '. Quem não é optante do Simples só pode aproveitar esse crédito quando o fornecedor o informa na nota '
                                '(CSOSN 101 ou 201 e a frase nas informações complementares). "—" = a nota não traz a informação.', corpo), Spacer(1, 2 * mm)]
        else:
            titulos = ['Nº', 'Série', 'Emissão', 'Outra parte', 'Chave de acesso', 'Valor', 'Situação', 'Exp.']
            larg = [16, 12, 19, 80, 83, 27, 20, 12]; direita = {5}; vi = 5; i_parte = 3; i_mun = None
        assert abs(sum(larg) - W) <= 1, sum(larg)
        if varias: titulos[i_parte] = 'Empresa / outra parte'
        corpo_t = [[Paragraph(x, cabr if i in direita else cab) for i, x in enumerate(titulos)]]; estilos = []
        for i, r in enumerate(itens, 1):
            parte = ajustar(((r['empresa'] + ' / ') if varias else '') + (r.get('parte') or '—'), larg[i_parte])
            exp = 'Sim' if r.get('exportada') else '—'
            if fam == 'nfse':
                lin = [ajustar(r['numero'], larg[0]), _br(r['data']), parte, _doc(r.get('doc')), money(r['valor']), (f"{_dec(r['aliquota']):.2f}".replace('.', ',') + '%') if r.get('aliquota') not in (None, '') else '—',
                       money(r['iss']) if r.get('iss') not in (None, '') else '—', r.get('iss_retido') or '—', r.get('iss_fora') or '—', ajustar(r.get('municipio') or '—', larg[i_mun]), r['situacao'], exp]
            elif fam == 'nfe' and not saida:
                cred = r.get('credito') or '—'
                if cred == 'Sim': cred = 'Sim' + (f" • {money(r['cred_valor'])}" if r.get('cred_valor') else '') + ((f" • {_dec(r['cred_aliq']):.2f}".replace('.', ',') + '%') if r.get('cred_aliq') else '')
                lin = [ajustar(r['numero'], larg[0]), r['serie'] or '—', _br(r['data']), parte, r['chave'] or '—', money(r['valor']), r.get('optante') or '—', ajustar(cred, larg[7]), r['situacao'], exp]
            else:
                lin = [ajustar(r['numero'], larg[0]), r['serie'] or '—', _br(r['data']), parte, r['chave'] or '—', money(r['valor']), r['situacao'], exp]
            corpo_t.append(lin)
            if _cancelada(r): estilos.append(('TEXTCOLOR', (0, i), (-1, i), hx(ALERTA)))
            if _cancelada(r) and r.get('exportada'): estilos.append(('BACKGROUND', (0, i), (-1, i), hx('#FEE2E2')))
            feitos += 1
            if progresso and feitos % 500 == 0:
                try: progresso(feitos, len(linhas))
                except Exception: pass
        corpo_t.append(['Total das autorizadas'] + [''] * (vi - 1) + [money(va)] + [''] * (len(titulos) - vi - 1)); corpo_t.append(['Total das canceladas'] + [''] * (vi - 1) + [money(vc)] + [''] * (len(titulos) - vi - 1))
        n = len(corpo_t)
        tb = Table(corpo_t, colWidths=[w * mm for w in larg], repeatRows=1, hAlign='LEFT')
        alinha = [('ALIGN', (c, 1), (c, -1), 'RIGHT') for c in direita]
        tb.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), hx(cor)), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTSIZE', (0, 0), (-1, -1), 7.6),
                                ('GRID', (0, 0), (-1, -1), 0.25, hx(LINHA)), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 2.2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
                                ('ROWBACKGROUNDS', (0, 1), (-1, n - 3), [colors.white, hx('#F8FAFC')]), ('BACKGROUND', (0, n - 2), (-1, n - 1), hx(SUAVE)), ('FONTNAME', (0, n - 2), (-1, n - 1), 'Helvetica-Bold'),
                                ('SPAN', (0, n - 2), (vi - 1, n - 2)), ('SPAN', (0, n - 1), (vi - 1, n - 1)), ('TEXTCOLOR', (0, n - 1), (-1, n - 1), hx(ALERTA))] + alinha + estilos))
        story.append(tb)
    if not linhas:
        story += [PageBreak(), Paragraph('Nenhum documento neste filtro.', h2)]
    doc.build(story, canvasmaker=_Numerada)
    return str(caminho)
