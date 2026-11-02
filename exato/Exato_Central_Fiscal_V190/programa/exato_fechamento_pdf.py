"""PDF do fechamento do mês (V174): resumo do mês de uma empresa e a lista de NF-e, NFC-e e CT-e (a NFS-e tem o relatório mensal próprio)."""
import re
from datetime import datetime
from decimal import Decimal
from html import escape

TIPOS = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}
ORDEM = ('nfe', 'nfce', 'cte', 'nfse')


def _money(v):
    try: d = Decimal(str(v if v not in (None, '') else 0))
    except Exception: return str(v)
    return 'R$ ' + f'{d:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _doc(d):
    d = re.sub(r'\D', '', str(d or ''))
    if len(d) == 14: return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}'
    return d or '—'


def _br(data):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(data or ''))
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m else (str(data or '') or '—')


def _mes_texto(mes):
    nomes = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
    m = re.match(r'(\d{4})-(\d{2})$', str(mes or ''))
    return f'{nomes[int(m.group(2)) - 1]}/{m.group(1)}' if m and 1 <= int(m.group(2)) <= 12 else str(mes)


def resumo(rows):
    """[(familia, direção, notas, valor, canceladas)] só do que existe; canceladas ficam fora do valor."""
    grupos = {}
    for r in rows:
        chave = (r.get('family'), r.get('direcao') or '—')
        g = grupos.setdefault(chave, {'n': 0, 'v': Decimal('0.00'), 'c': 0})
        if r.get('situacao') == 'Cancelada': g['c'] += 1
        else:
            g['n'] += 1
            try: g['v'] += Decimal(str(r.get('valor') or 0))
            except Exception: pass
    ordem = {f: i for i, f in enumerate(ORDEM)}
    return [(f, d, g['n'], g['v'], g['c']) for (f, d), g in sorted(grupos.items(), key=lambda kv: (ordem.get(kv[0][0], 9), kv[0][1]))]


def resumo_separado(rows):
    """V179: como `resumo`, mas com o valor das canceladas à parte: [(familia, direção, notas, valor, canceladas, valor_canceladas)]."""
    grupos = {}
    for r in rows:
        g = grupos.setdefault((r.get('family'), r.get('direcao') or '—'), {'n': 0, 'v': Decimal('0.00'), 'c': 0, 'cv': Decimal('0.00')})
        try: v = Decimal(str(r.get('valor') or 0))
        except Exception: v = Decimal('0.00')
        if r.get('situacao') == 'Cancelada': g['c'] += 1; g['cv'] += v
        else: g['n'] += 1; g['v'] += v
    ordem = {f: i for i, f in enumerate(ORDEM)}
    return [(f, d, g['n'], g['v'], g['c'], g['cv']) for (f, d), g in sorted(grupos.items(), key=lambda kv: (ordem.get(kv[0][0], 9), kv[0][1]))]


def gerar_fechamento_pdf(rows, caminho, empresa='', cnpj='', mes='', logo=None, revisao=0, motivo=''):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, CondPageBreak
    ink = colors.HexColor('#0F172A'); muted = colors.HexColor('#64748B'); line = colors.HexColor('#E6EAF1'); red = colors.HexColor('#E11D2E'); soft = colors.HexColor('#EEF2F7')
    st = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=st['Title'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=ink, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle('h2', parent=st['Heading2'], fontName='Helvetica-Bold', fontSize=12.5, leading=16, textColor=ink, spaceBefore=10, spaceAfter=2, keepWithNext=1)
    small = ParagraphStyle('small', parent=st['BodyText'], fontName='Helvetica', fontSize=9, leading=12, textColor=muted)
    cell = ParagraphStyle('cell', parent=st['BodyText'], fontName='Helvetica', fontSize=8.6, leading=11, textColor=ink)
    cellr = ParagraphStyle('cellr', parent=cell, alignment=2)
    hd = ParagraphStyle('hd', parent=cell, fontName='Helvetica-Bold', textColor=colors.white)
    hdr = ParagraphStyle('hdr', parent=hd, alignment=2)
    bold = ParagraphStyle('bold', parent=cell, fontName='Helvetica-Bold')
    boldr = ParagraphStyle('boldr', parent=bold, alignment=2)
    base = [('BACKGROUND', (0, 0), (-1, 0), red), ('GRID', (0, 0), (-1, -1), 0.3, line), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    doc = SimpleDocTemplate(str(caminho), pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=16 * mm, title=f'Fechamento {mes}')
    story = []
    if logo:
        try:
            img = Image(str(logo), hAlign='LEFT'); sc = min((42 * mm) / img.imageWidth, (13 * mm) / img.imageHeight); img.drawWidth = img.imageWidth * sc; img.drawHeight = img.imageHeight * sc; story += [img, Spacer(1, 3 * mm)]
        except Exception: pass
    titulo = f'Fechamento de {_mes_texto(mes)}' + (f' — revisão {revisao}' if revisao else '')
    story += [Paragraph(escape(titulo), h1), Paragraph(f'<b>{escape(empresa or "Empresa")}</b>  •  CNPJ {escape(_doc(cnpj))}', small),
              Paragraph('Mês encerrado pelo Exato: não chegaram mais notas deste mês nos últimos dias de conferência.' + (f' {escape(motivo)}' if motivo else ''), small), Spacer(1, 4 * mm)]
    # resumo por tipo e movimentação
    cab = [Paragraph('Tipo', hd), Paragraph('Movimentação', hd), Paragraph('Autorizadas (notas)', hdr), Paragraph('Autorizadas (valor)', hdr), Paragraph('Canceladas (notas)', hdr), Paragraph('Canceladas (valor)', hdr)]
    dados = [cab]; tn = 0; tv = Decimal('0.00'); tc = 0; tcv = Decimal('0.00')
    for fam, direc, n, v, c, cv in resumo_separado(rows):
        dados.append([Paragraph(TIPOS.get(fam, str(fam)), cell), Paragraph(escape(str(direc)), cell), Paragraph(str(n), cellr), Paragraph(_money(v), cellr), Paragraph(str(c), cellr), Paragraph(_money(cv), cellr)])
        tn += n; tv += v; tc += c; tcv += cv
    if len(dados) == 1: dados.append([Paragraph('Nenhum documento neste mês.', cell)] + [''] * 5)
    dados.append([Paragraph('Total', bold), '', Paragraph(str(tn), boldr), Paragraph(_money(tv), boldr), Paragraph(str(tc), boldr), Paragraph(_money(tcv), boldr)])
    t = Table(dados, colWidths=[35 * mm, 50 * mm, 40 * mm, 50 * mm, 40 * mm, 54 * mm], repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle(base + [('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0, -1), (-1, -1), soft)]))
    story += [t, Spacer(1, 2 * mm), Paragraph('Autorizadas e canceladas são somadas separadamente: as canceladas aparecem nas listas (em vermelho), mas não entram no valor das autorizadas. As NFS-e têm o relatório mensal próprio (com alíquota, ISS e ISS fora do município), na mesma pasta.', small)]
    # listas: NF-e, NFC-e e CT-e por movimentação
    listas = {}
    for r in rows:
        if r.get('family') in ('nfe', 'nfce', 'cte'): listas.setdefault((r['family'], r.get('direcao') or '—'), []).append(r)
    for (fam, direc) in sorted(listas, key=lambda k: (ORDEM.index(k[0]), k[1])):
        itens = sorted(listas[(fam, direc)], key=lambda r: (str(r.get('data') or ''), str(r.get('numero') or '').zfill(12)))
        ok = [r for r in itens if r.get('situacao') != 'Cancelada']
        soma = sum((Decimal(str(r.get('valor') or 0)) for r in ok), Decimal('0.00'))
        ruins = [r for r in itens if r.get('situacao') == 'Cancelada']; soma_c = sum((Decimal(str(r.get('valor') or 0)) for r in ruins), Decimal('0.00'))
        story += [CondPageBreak(40 * mm), Paragraph(f'{TIPOS[fam]} — {escape(str(direc))}', h2),
                  Paragraph(f'<b>Autorizadas:</b> {len(ok)} nota(s) • {_money(soma)}', small), Paragraph(f'<b>Canceladas:</b> {len(ruins)} nota(s) • {_money(soma_c)} (não somadas nas autorizadas)', small), Spacer(1, 1.5 * mm)]
        linhas = [[Paragraph('Nº', hd), Paragraph('Série', hd), Paragraph('Emissão', hd), Paragraph('Chave de acesso', hd), Paragraph('Valor', hdr), Paragraph('Situação', hd)]]
        for r in itens:
            ruim = r.get('situacao') == 'Cancelada'
            c = ParagraphStyle('c', parent=cell, textColor=colors.HexColor('#B91C1C') if ruim else ink); cr = ParagraphStyle('cr', parent=c, alignment=2)
            linhas.append([Paragraph(escape(str(r.get('numero') or '')), c), Paragraph(escape(str(r.get('serie') or '')), c), Paragraph(escape(_br(r.get('data'))), c), Paragraph(escape(str(r.get('chave') or '')), c),
                           Paragraph(_money(r.get('valor') or 0), cr), Paragraph(escape(str(r.get('situacao') or '')), c)])
        linhas.append([Paragraph('Total autorizadas', bold), '', '', '', Paragraph(_money(soma), boldr), Paragraph(f'{len(ok)} nota(s)', bold)])
        if ruins: linhas.append([Paragraph('Total canceladas', bold), '', '', '', Paragraph(_money(soma_c), boldr), Paragraph(f'{len(ruins)} nota(s)', bold)])
        tb = Table(linhas, colWidths=[22 * mm, 16 * mm, 26 * mm, 115 * mm, 40 * mm, 50 * mm], repeatRows=1, hAlign='LEFT')
        tb.setStyle(TableStyle(base + [('ROWBACKGROUNDS', (0, 1), (-1, -1 - (2 if ruins else 1) + 1), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0, -1 - (1 if ruins else 0)), (-1, -1), soft), ('SPAN', (0, -1), (3, -1))]
                                  + ([('SPAN', (0, -2), (3, -2))] if ruins else [])))
        story.append(tb)
    def rodape(canvas, d):
        canvas.saveState(); canvas.setFont('Helvetica', 8); canvas.setFillColor(muted)
        canvas.drawString(14 * mm, 8 * mm, f"Exato Central Fiscal • gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"); canvas.drawRightString(landscape(A4)[0] - 14 * mm, 8 * mm, f'Página {d.page}')
        if d.page > 1: canvas.drawString(14 * mm, landscape(A4)[1] - 9 * mm, f"{titulo} • {empresa or 'Empresa'} • CNPJ {_doc(cnpj)}")
        canvas.restoreState()
    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return str(caminho)
