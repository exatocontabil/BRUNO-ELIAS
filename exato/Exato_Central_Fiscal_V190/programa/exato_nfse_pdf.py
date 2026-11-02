"""NFS-e: representação em PDF (uma página por nota), no papel que o DANFE tem para a NF-e.

Gerada a partir do XML. Não substitui o DANFSe oficial do Emissor Nacional (a nota diz isso no rodapé).
"""
import re
from datetime import datetime
from decimal import Decimal
from html import escape

import exato_nfse as nfse


def _money(v):
    if v is None or v == '':
        return '—'
    try:
        d = Decimal(str(v))
    except Exception:
        return str(v)
    s = f'{d:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {s}'


def _aliq(v):
    """Alíquota em % (2,00%); '—' quando a nota não informa."""
    if v is None or v == '':
        return '—'
    try:
        return f'{Decimal(str(v)):.2f}'.replace('.', ',') + '%'
    except Exception:
        return str(v)


def _dec(v):
    try:
        return Decimal(str(v)) if v not in (None, '') else None
    except Exception:
        return None


def _doc(d):
    d = re.sub(r'\D', '', str(d or ''))
    if len(d) == 14: return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}'
    if len(d) == 11: return f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}'
    return d or '—'


def _date(v):
    v = str(v or '')
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?', v)
    if not m: return v or '—'
    out = f'{m.group(3)}/{m.group(2)}/{m.group(1)}'
    return out + (f' {m.group(4)}:{m.group(5)}' if m.group(4) else '')


def _key_groups(key):
    key = re.sub(r'\D', '', str(key or ''))
    return ' '.join(key[i:i + 5] for i in range(0, len(key), 5)) or '—'


def _fmt_cep(v):
    d = re.sub(r'\D', '', str(v or ''))
    return f'{d[:5]}-{d[5:]}' if len(d) == 8 else str(v or '')


def _fmt_fone(v):
    d = re.sub(r'\D', '', str(v or ''))
    if len(d) == 11: return f'({d[:2]}) {d[2:7]}-{d[7:]}'
    if len(d) == 10: return f'({d[:2]}) {d[2:6]}-{d[6:]}'
    return str(v or '')


def _addr_text(a):
    if not a: return '—'
    parts = [a.get('logradouro'), a.get('numero'), a.get('complemento'), a.get('bairro')]
    line = ', '.join(p for p in parts if p)
    city = ' - '.join(p for p in (a.get('municipio'), a.get('uf')) if p)
    cep = f"CEP {_fmt_cep(a['cep'])}" if a.get('cep') else ''
    contact = ' • '.join(p for p in (f"Tel. {_fmt_fone(a['fone'])}" if a.get('fone') else '', a.get('email') or '') if p)
    return ' • '.join(p for p in (line, city, cep, contact) if p) or '—'


def build_pages(items, story_builder):
    """items: dicts com 'xml', 'cnpj' (empresa consultada) e opcionalmente 'situacao' ('Cancelada')."""
    for i, it in enumerate(items):
        try:
            d = nfse.parse_nfse_details(it['xml'], it.get('cnpj', ''))
        except Exception:
            d = None
        story_builder(i, d, it)


def generate_nfse_pdf(items, output_path, company_name='', logo_path=None):
    """Um PDF com uma página por NFS-e (ou um PDF individual, se houver só um item)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    ink = colors.HexColor('#0F172A'); muted = colors.HexColor('#64748B'); line = colors.HexColor('#CBD5E1'); red = colors.HexColor('#E11D2E')
    st = getSampleStyleSheet()
    lab = ParagraphStyle('lab', parent=st['BodyText'], fontName='Helvetica', fontSize=6.8, leading=8, textColor=muted)
    val = ParagraphStyle('val', parent=st['BodyText'], fontName='Helvetica-Bold', fontSize=8.8, leading=10.5, textColor=ink)
    txt = ParagraphStyle('txt', parent=st['BodyText'], fontName='Helvetica', fontSize=8.6, leading=11, textColor=ink)
    title = ParagraphStyle('title', parent=st['Title'], fontName='Helvetica-Bold', fontSize=14, leading=17, textColor=ink, alignment=0, spaceAfter=0)
    sub = ParagraphStyle('sub', parent=st['BodyText'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=muted)
    sec = ParagraphStyle('sec', parent=st['BodyText'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)
    W = 182 * mm

    def cell(label, value, style=val):
        return [Paragraph(escape(label.upper()), lab), Paragraph(escape(str(value if value not in (None, '') else '—')), style)]

    def box(rows, widths):
        t = Table(rows, colWidths=widths)
        t.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, line), ('INNERGRID', (0, 0), (-1, -1), 0.3, line), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        return t

    def section(name):
        t = Table([[Paragraph(escape(name.upper()), sec)]], colWidths=[W])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), ink), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
        return t

    def fields(pairs, widths):
        return box([[cell(l, v) for l, v in pairs]], widths)

    story = []
    cancelled_pages = set()
    for index, it in enumerate(items):
        try:
            d = nfse.parse_nfse_details(it['xml'], it.get('cnpj', ''))
        except Exception:
            d = None
        if index: story.append(PageBreak())
        head = [Paragraph('DANFSe — Documento Auxiliar da NFS-e', title), Paragraph('Nota Fiscal de Serviço Eletrônica • Padrão Nacional', sub)]
        logo = None
        if logo_path:
            try:
                logo = Image(str(logo_path)); sc = min((38 * mm) / logo.imageWidth, (12 * mm) / logo.imageHeight); logo.drawWidth = logo.imageWidth * sc; logo.drawHeight = logo.imageHeight * sc
            except Exception:
                logo = None
        top = Table([[head, logo or '']], colWidths=[W - 42 * mm, 42 * mm])
        top.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (1, 0), (1, 0), 'RIGHT'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
        story += [top, Spacer(1, 3 * mm)]
        if d is None:
            story += [Paragraph('Não foi possível ler este XML como NFS-e do padrão nacional.', txt)]
            continue
        if it.get('situacao') == 'Cancelada': cancelled_pages.add(index + 1)
        story.append(box([[cell('Chave de acesso', _key_groups(d['chave']))]], [W]))
        story.append(fields([('Número da NFS-e', d['numero']), ('Série / DPS', ' / '.join(x for x in (d['serie'], d['numero_dps']) if x) or '—'), ('Emissão', _date(d['data'])),
                             ('Competência', _date(d['competencia'])), ('Situação', 'CANCELADA' if it.get('situacao') == 'Cancelada' else 'Autorizada')], [34 * mm, 32 * mm, 42 * mm, 34 * mm, 40 * mm]))
        story.append(fields([('Local de emissão', d['local_emissao']), ('Local da prestação', d['local_prestacao'] or d['local_emissao']), ('Processamento', _date(d['processamento']))], [66 * mm, 66 * mm, 50 * mm]))
        story += [Spacer(1, 2 * mm), section('Prestador do serviço')]
        story.append(fields([('Nome / Razão social', d['prestador']['nome']), ('CNPJ / CPF', _doc(d['prestador']['doc'])), ('Inscrição municipal', d['prestador_im'])], [96 * mm, 46 * mm, 40 * mm]))
        story.append(box([[cell('Endereço', _addr_text(d['prestador_end']))]], [W]))
        story += [Spacer(1, 2 * mm), section('Tomador do serviço')]
        story.append(fields([('Nome / Razão social', d['tomador']['nome']), ('CNPJ / CPF', _doc(d['tomador']['doc'])), ('Inscrição municipal', d['tomador_im'])], [96 * mm, 46 * mm, 40 * mm]))
        story.append(box([[cell('Endereço', _addr_text(d['tomador_end']))]], [W]))
        if d['intermediario']['doc'] or d['intermediario']['nome']:
            story.append(fields([('Intermediário', d['intermediario']['nome']), ('CNPJ / CPF', _doc(d['intermediario']['doc']))], [136 * mm, 46 * mm]))
        story += [Spacer(1, 2 * mm), section('Serviço prestado')]
        story.append(fields([('Código de tributação nacional', d['servico_codigo_formatado'] or d['servico_codigo']), ('Código municipal', d['servico_codigo_municipal']), ('Município de incidência', d['local_incidencia'])], [70 * mm, 50 * mm, 62 * mm]))
        if d['servico_trib_nacional'] or d['servico_nbs']:
            nac = d['servico_trib_nacional']; nac = (nac[:230] + '…') if len(nac) > 232 else nac
            story.append(box([[[Paragraph('ATIVIDADE (TRIBUTAÇÃO NACIONAL) / NBS', lab), Paragraph(escape(' • '.join(x for x in (nac, ('NBS: ' + d['servico_nbs']) if d['servico_nbs'] else '') if x)), txt)]]], [W]))
        story.append(box([[[Paragraph('DESCRIÇÃO DO SERVIÇO', lab), Paragraph(escape(d['servico_descricao'] or d['servico_trib_nacional'] or '—'), txt)]]], [W]))
        if d['info_complementar']:
            story.append(box([[[Paragraph('INFORMAÇÕES COMPLEMENTARES', lab), Paragraph(escape(d['info_complementar']), txt)]]], [W]))
        story += [Spacer(1, 2 * mm), section('Valores')]
        story.append(fields([('Valor do serviço', _money(d['valor_servico'] if d['valor_servico'] is not None else d['valor'])), ('Desconto', _money(d['valor_desconto'])), ('Base de cálculo', _money(d['valor_base'])),
                             ('Alíquota ISS', (d['aliquota'] + '%') if d['aliquota'] else '—'), ('ISS apurado', _money(d['valor_iss']))], [40 * mm, 34 * mm, 38 * mm, 32 * mm, 38 * mm]))
        story.append(fields([('Retenções', _money(d['valor_retido'])), ('Valor líquido', _money(d['valor_liquido'])), ('ISS retido', nfse.retencao_iss_texto(d['retencao_iss']) or '—')], [60 * mm, 60 * mm, 62 * mm]))
        if d['regime_texto'] or d['tributos_aprox_sn']:
            story.append(fields([('Regime do prestador', d['regime_texto']), ('Tributos aproximados (Simples Nacional)', (d['tributos_aprox_sn'].replace('.', ',') + '%') if d['tributos_aprox_sn'] else '—')], [100 * mm, 82 * mm]))
        if d['ambiente_dps'] == 'Homologação':
            story.append(Paragraph('<b>NOTA EMITIDA EM AMBIENTE DE HOMOLOGAÇÃO (TESTE) — SEM VALIDADE FISCAL.</b>', sub))
        story += [Spacer(1, 4 * mm), Paragraph('Representação gráfica gerada pelo Exato Central Fiscal a partir do XML da NFS-e. Não substitui o DANFSe oficial do Emissor Nacional.', sub)]

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7.5); canvas.setFillColor(muted)
        canvas.drawString(14 * mm, 8 * mm, f"Exato Central Fiscal • {company_name or ''} • gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        canvas.drawRightString(A4[0] - 14 * mm, 8 * mm, f'Página {doc.page}')
        if doc.page in cancelled_pages:
            canvas.translate(A4[0] / 2, A4[1] / 2); canvas.rotate(35); canvas.setFont('Helvetica-Bold', 70); canvas.setFillColor(colors.Color(0.88, 0.11, 0.18, alpha=0.18))
            canvas.drawCentredString(0, 0, 'CANCELADA')
        canvas.restoreState()

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=14 * mm, title='DANFSe')
    doc.build(story or [Paragraph('Nenhuma NFS-e.', txt)], onFirstPage=decorate, onLaterPages=decorate)
    return str(output_path)


def monthly_summary(rows):
    """rows: dicts com data (AAAA-MM-DD...), tipo ('Prestado'/'Tomado'), valor, situacao ('Cancelada'/'Autorizada') e, quando houver, iss e iss_retido.

    Devolve lista ordenada por mês: {'mes','prest_qtd','prest_valor','prest_iss','tom_qtd','tom_valor','tom_iss','iss_retido','canc_qtd','canc_valor'}.
    Canceladas não entram nos valores nem no ISS de prestados/tomados (ficam à parte, por tipo). `iss_retido` soma o ISS das notas com retenção ('Sim').
    V179: `iss_fora`/`fora_qtd` = ISS (e quantas notas autorizadas) cujo município de incidência não é o do prestador.
    """
    months = {}
    zero = Decimal('0.00')
    for r in rows:
        key = str(r.get('data') or '')[:7] if re.match(r'\d{4}-\d{2}', str(r.get('data') or '')) else 'Sem data'
        m = months.setdefault(key, {'mes': key, 'prest_qtd': 0, 'prest_valor': zero, 'prest_iss': zero, 'tom_qtd': 0, 'tom_valor': zero, 'tom_iss': zero, 'iss_retido': zero, 'prest_iss_retido': zero, 'tom_iss_retido': zero,
                                    'canc_qtd': 0, 'canc_valor': zero, 'prest_canc_qtd': 0, 'prest_canc_valor': zero, 'tom_canc_qtd': 0, 'tom_canc_valor': zero, 'iss_fora': zero, 'fora_qtd': 0})
        v = Decimal(str(r.get('valor') or 0)); iss = _dec(r.get('iss')) or zero
        if r.get('situacao') == 'Cancelada':
            m['canc_qtd'] += 1; m['canc_valor'] += v
            pre = 'prest' if r.get('tipo') == 'Prestado' else 'tom'
            m[pre + '_canc_qtd'] += 1; m[pre + '_canc_valor'] += v
            continue
        if r.get('iss_fora') == 'SIM':
            m['fora_qtd'] += 1; m['iss_fora'] += iss
        if r.get('tipo') == 'Prestado':
            m['prest_qtd'] += 1; m['prest_valor'] += v; m['prest_iss'] += iss
        else:
            m['tom_qtd'] += 1; m['tom_valor'] += v; m['tom_iss'] += iss
        if r.get('iss_retido') == 'Sim':
            m['iss_retido'] += iss
            m['prest_iss_retido' if r.get('tipo') == 'Prestado' else 'tom_iss_retido'] += iss
    return [months[k] for k in sorted(months)]


def month_label(key):
    names = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
    m = re.match(r'(\d{4})-(\d{2})$', key or '')
    return f'{names[int(m.group(2)) - 1]}/{m.group(1)}' if m and 1 <= int(m.group(2)) <= 12 else (key or 'Sem data')


_RESUMO_W = [28, 21, 28, 22, 22, 21, 28, 22, 22, 24, 31]          # soma 269 mm


def _resumo_tabela(summary, hd, hdr, cell, cellr, bold, boldr, vazio_texto):
    """Linhas da tabela do resumo por mês (V179: ISS pago fora do município e canceladas com valor, à parte das autorizadas). Devolve (linhas, totais)."""
    from reportlab.platypus import Paragraph
    head = [Paragraph(x, h) for x, h in (('Mês', hd), ('Prestados (notas)', hdr), ('Prestados (valor)', hdr), ('ISS prestados', hdr), ('ISS retido (prestados)', hdr), ('Tomados (notas)', hdr), ('Tomados (valor)', hdr),
                                          ('ISS tomados', hdr), ('ISS retido (tomados)', hdr), ('ISS pago fora', hdr), ('Canceladas (à parte)', hdr))]
    data = [head]; z = Decimal('0.00')
    tot = {'pq': 0, 'pv': z, 'pi': z, 'tq': 0, 'tv': z, 'ti': z, 'ri': z, 'rp': z, 'rt': z, 'cq': 0, 'cv': z, 'pcq': 0, 'pcv': z, 'tcq': 0, 'tcv': z, 'fi': z, 'fq': 0}
    canc = lambda q, v: Paragraph(f'{q} nota(s)<br/>{_money(v)}', cellr)
    for m in summary:
        data.append([Paragraph(escape(month_label(m['mes'])), cell), Paragraph(str(m['prest_qtd']), cellr), Paragraph(_money(m['prest_valor']), cellr), Paragraph(_money(m['prest_iss']), cellr), Paragraph(_money(m['prest_iss_retido']), cellr),
                     Paragraph(str(m['tom_qtd']), cellr), Paragraph(_money(m['tom_valor']), cellr), Paragraph(_money(m['tom_iss']), cellr), Paragraph(_money(m['tom_iss_retido']), cellr),
                     Paragraph(_money(m['iss_fora']) if m['fora_qtd'] else '—', cellr), canc(m['canc_qtd'], m['canc_valor'])])
        for k, k2 in (('pq', 'prest_qtd'), ('pv', 'prest_valor'), ('pi', 'prest_iss'), ('tq', 'tom_qtd'), ('tv', 'tom_valor'), ('ti', 'tom_iss'), ('ri', 'iss_retido'), ('rp', 'prest_iss_retido'), ('rt', 'tom_iss_retido'),
                      ('cq', 'canc_qtd'), ('cv', 'canc_valor'), ('pcq', 'prest_canc_qtd'), ('pcv', 'prest_canc_valor'), ('tcq', 'tom_canc_qtd'), ('tcv', 'tom_canc_valor'), ('fi', 'iss_fora'), ('fq', 'fora_qtd')):
            tot[k] += m[k2]
    if len(data) == 1:
        data.append([Paragraph(vazio_texto, cell)] + [''] * 10)
    data.append([Paragraph('Total', bold), Paragraph(str(tot['pq']), boldr), Paragraph(_money(tot['pv']), boldr), Paragraph(_money(tot['pi']), boldr), Paragraph(_money(tot['rp']), boldr), Paragraph(str(tot['tq']), boldr),
                 Paragraph(_money(tot['tv']), boldr), Paragraph(_money(tot['ti']), boldr), Paragraph(_money(tot['rt']), boldr), Paragraph(_money(tot['fi']) if tot['fq'] else '—', boldr),
                 Paragraph(f'{tot["cq"]} nota(s)<br/>{_money(tot["cv"])}', boldr)])
    return data, tot


def generate_monthly_summary_pdf(summary, output_path, company_name='', cnpj='', period_label='Todo o período', logo_path=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    ink = colors.HexColor('#0F172A'); muted = colors.HexColor('#64748B'); line = colors.HexColor('#E6EAF1'); red = colors.HexColor('#E11D2E')
    st = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=st['Title'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=ink, alignment=0, spaceAfter=2)
    small = ParagraphStyle('small', parent=st['BodyText'], fontName='Helvetica', fontSize=9, leading=12, textColor=muted)
    c = ParagraphStyle('c', parent=st['BodyText'], fontName='Helvetica', fontSize=8.6, leading=11, textColor=ink)
    cr = ParagraphStyle('cr', parent=c, alignment=2)
    hd = ParagraphStyle('hd', parent=c, fontName='Helvetica-Bold', textColor=colors.white)
    hdr = ParagraphStyle('hdr', parent=hd, alignment=2)
    bold = ParagraphStyle('bold', parent=c, fontName='Helvetica-Bold')
    boldr = ParagraphStyle('boldr', parent=bold, alignment=2)
    doc = SimpleDocTemplate(str(output_path), pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=16 * mm, title='Resumo mensal de NFS-e')
    story = []
    if logo_path:
        try:
            img = Image(str(logo_path), hAlign='LEFT'); sc = min((42 * mm) / img.imageWidth, (13 * mm) / img.imageHeight); img.drawWidth = img.imageWidth * sc; img.drawHeight = img.imageHeight * sc; story += [img, Spacer(1, 3 * mm)]
        except Exception:
            pass
    story += [Paragraph('Resumo mensal de NFS-e', h1), Paragraph(f'<b>{escape(company_name or "Empresa")}</b>  •  CNPJ {escape(_doc(cnpj))}', small),
              Paragraph(f'Período: {escape(period_label)}', small), Spacer(1, 5 * mm)]
    data, tot = _resumo_tabela(summary, hd, hdr, c, cr, bold, boldr, 'Nenhuma NFS-e neste filtro.')
    t = Table(data, colWidths=[w * mm for w in _RESUMO_W], repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), red), ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EEF2F7')),
                           ('GRID', (0, 0), (-1, -1), 0.3, line), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story += [t, Spacer(1, 4 * mm), Paragraph(_NOTA_RESUMO, small)]
    def footer(canvas, d):
        canvas.saveState(); canvas.setFont('Helvetica', 8); canvas.setFillColor(muted)
        canvas.drawString(14 * mm, 8 * mm, f"Exato Central Fiscal • gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"); canvas.drawRightString(landscape(A4)[0] - 14 * mm, 8 * mm, f'Página {d.page}'); canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return str(output_path)


_NOTA_RESUMO = ('Notas CANCELADAS ficam à parte (coluna "Canceladas"): não entram nos valores nem no ISS de prestados e tomados. "ISS retido" soma o ISS das notas em que o ISS é retido. '
                '"ISS pago fora" soma o ISS das notas autorizadas cujo município de incidência não é o do prestador.')


def _iso_to_br(value):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(value or ''))
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m else str(value or '')


def monthly_report_sections(rows):
    """Agrupa as notas em seções por mês e tipo: [(mês 'AAAA-MM', 'Prestado'|'Tomado', [notas], totais)].

    Cada seção traz todas as notas do mês daquele tipo; o total soma só as autorizadas (canceladas ficam à parte).
    """
    groups = {}
    for r in rows:
        key = str(r.get('data') or '')[:7] if re.match(r'\d{4}-\d{2}', str(r.get('data') or '')) else 'Sem data'
        groups.setdefault((key, 'Tomado' if r.get('tipo') == 'Tomado' else 'Prestado'), []).append(r)
    out = []
    for (month, kind) in sorted(groups, key=lambda k: (k[0], 0 if k[1] == 'Prestado' else 1)):
        items = sorted(groups[(month, kind)], key=lambda r: (str(r.get('data') or ''), str(r.get('numero') or '').zfill(12)))
        ok = [r for r in items if r.get('situacao') != 'Cancelada']; bad = [r for r in items if r.get('situacao') == 'Cancelada']
        add = lambda xs: sum((Decimal(str(r.get('valor') or 0)) for r in xs), Decimal('0.00'))
        add_iss = lambda xs: sum(((_dec(r.get('iss')) or Decimal('0.00')) for r in xs), Decimal('0.00'))
        out.append((month, kind, items, {'qtd': len(ok), 'valor': add(ok), 'canc_qtd': len(bad), 'canc_valor': add(bad), 'iss': add_iss(ok), 'iss_retido': add_iss([r for r in ok if r.get('iss_retido') == 'Sim']),
                                    'fora_qtd': len([r for r in ok if r.get('iss_fora') == 'SIM']), 'iss_fora': add_iss([r for r in ok if r.get('iss_fora') == 'SIM'])}))
    return out


_LISTA_W = [12, 22, 52, 36, 24, 14, 22, 14, 14, 32, 27]          # soma 269 mm


def generate_monthly_report_pdf(rows, output_path, company_name='', cnpj='', period_label='Todo o período', logo_path=None, title='Relatório mensal de NFS-e'):
    """Relatório mensal em lote: resumo por mês e, para cada mês e tipo (Prestados/Tomados), a lista de todas as notas com o total.

    V154: a lista do primeiro mês começa logo abaixo do resumo (sem página vazia); cada mês novo começa em página nova;
    tabelas da mesma largura e mesma cor; letra maior; empresa e CNPJ repetidos no alto das páginas seguintes;
    totais do período no fim.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether, CondPageBreak
    ink = colors.HexColor('#0F172A'); muted = colors.HexColor('#64748B'); line = colors.HexColor('#E6EAF1'); red = colors.HexColor('#E11D2E'); soft = colors.HexColor('#EEF2F7')
    st = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=st['Title'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=ink, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle('h2', parent=st['Heading2'], fontName='Helvetica-Bold', fontSize=12.5, leading=16, textColor=ink, spaceBefore=10, spaceAfter=2, keepWithNext=1)
    small = ParagraphStyle('small', parent=st['BodyText'], fontName='Helvetica', fontSize=9, leading=12, textColor=muted)
    smallk = ParagraphStyle('smallk', parent=small, keepWithNext=1)
    cell = ParagraphStyle('cell', parent=st['BodyText'], fontName='Helvetica', fontSize=9, leading=11.5, textColor=ink)
    cellr = ParagraphStyle('cellr', parent=cell, alignment=2)
    hd = ParagraphStyle('hd', parent=cell, fontName='Helvetica-Bold', textColor=colors.white)
    hdr = ParagraphStyle('hdr', parent=hd, alignment=2)
    bold = ParagraphStyle('bold', parent=cell, fontName='Helvetica-Bold')
    boldr = ParagraphStyle('boldr', parent=bold, alignment=2)
    W = 269  # largura útil da página (mm): igual em todas as tabelas
    sections = monthly_report_sections(rows)
    summary = monthly_summary(rows)
    doc = SimpleDocTemplate(str(output_path), pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=16 * mm, title=title)
    story = []
    if logo_path:
        try:
            img = Image(str(logo_path), hAlign='LEFT'); sc = min((42 * mm) / img.imageWidth, (13 * mm) / img.imageHeight); img.drawWidth = img.imageWidth * sc; img.drawHeight = img.imageHeight * sc; story += [img, Spacer(1, 3 * mm)]
        except Exception:
            pass
    story += [Paragraph(escape(title), h1), Paragraph(f'<b>{escape(company_name or "Empresa")}</b>  •  CNPJ {escape(_doc(cnpj))}', small),
              Paragraph(f'Período: {escape(period_label)}  •  {len(rows)} nota(s)', small), Spacer(1, 4 * mm)]
    base_style = [('BACKGROUND', (0, 0), (-1, 0), red), ('GRID', (0, 0), (-1, -1), 0.3, line), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    # resumo por mês (V173: com o ISS de prestados e tomados e o ISS retido)
    data, tot = _resumo_tabela(summary, hd, hdr, cell, cellr, bold, boldr, 'Nenhuma NFS-e neste período.')
    t = Table(data, colWidths=[w * mm for w in _RESUMO_W], repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle(base_style + [('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0, -1), (-1, -1), soft)]))
    story += [t, Spacer(1, 2 * mm), Paragraph('Notas canceladas aparecem na lista, em vermelho, mas ' + _NOTA_RESUMO[len('Notas CANCELADAS '):], small)]
    # listas: o primeiro mês segue o resumo; cada mês novo começa em página nova
    last_month = None
    for month, kind, items, totals in sections:
        if last_month is not None and month != last_month:
            story.append(PageBreak())
        last_month = month
        plural = 'Prestados' if kind == 'Prestado' else 'Tomados'
        story += [CondPageBreak(45 * mm), Paragraph(f'{escape(month_label(month).capitalize())} — serviços {plural.lower()}', h2),
                  Paragraph(f'<b>Autorizadas:</b> {totals["qtd"]} nota(s) • {_money(totals["valor"])} • ISS {_money(totals["iss"])}' + (f' (retido: {_money(totals["iss_retido"])})' if totals['iss_retido'] else '')
                            + (f' • <b>ISS pago fora:</b> {totals["fora_qtd"]} nota(s), {_money(totals["iss_fora"])}' if totals['fora_qtd'] else ''), smallk),
                  Paragraph(f'<b>Canceladas:</b> {totals["canc_qtd"]} nota(s) • {_money(totals["canc_valor"])} (não somadas nas autorizadas)', smallk), Spacer(1, 1.5 * mm)]
        rows_t = [[Paragraph('Nº', hd), Paragraph('Emissão', hd), Paragraph('Prestador' if kind == 'Tomado' else 'Tomador', hd), Paragraph('CNPJ / CPF', hd), Paragraph('Valor', hdr),
                   Paragraph('Alíq.', hdr), Paragraph('ISS', hdr), Paragraph('ISS retido', hd), Paragraph('ISS fora?', hd), Paragraph('Município de incidência', hd), Paragraph('Situação', hd)]]
        for r in items:
            bad = r.get('situacao') == 'Cancelada'
            c = ParagraphStyle('c', parent=cell, textColor=colors.HexColor('#B91C1C') if bad else ink); cr = ParagraphStyle('cr', parent=c, alignment=2)
            rows_t.append([Paragraph(escape(str(r.get('numero') or '')), c), Paragraph(escape(_iso_to_br(r.get('data'))), c), Paragraph(escape(str(r.get('nome') or '—')), c),
                           Paragraph(escape(_doc(r.get('doc'))), c), Paragraph(_money(r.get('valor') or 0), cr), Paragraph(_aliq(r.get('aliquota')), cr), Paragraph(_money(r.get('iss')), cr),
                           Paragraph(escape(str(r.get('iss_retido') or '—')), c), Paragraph(escape(str(r.get('iss_fora') or '—')), c), Paragraph(escape(str(r.get('municipio') or '—')), c),
                           Paragraph(escape(str(r.get('situacao') or '')), c)])
        rows_t.append([Paragraph('Total do mês (autorizadas)', bold), '', '', '', Paragraph(_money(totals['valor']), boldr), '', Paragraph(_money(totals['iss']), boldr), '', '', '', Paragraph(f'{totals["qtd"]} nota(s)', bold)])
        tb = Table(rows_t, colWidths=[w * mm for w in _LISTA_W], repeatRows=1, hAlign='LEFT')
        tb.setStyle(TableStyle(base_style + [('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0, -1), (-1, -1), soft), ('SPAN', (0, -1), (3, -1))]))
        story.append(tb)
    # totais do período
    aq = tot['pq'] + tot['tq']; av = tot['pv'] + tot['tv']
    fin = [[Paragraph('Totais do período', hd), Paragraph('Notas', hdr), Paragraph('Valor', hdr), Paragraph('ISS', hdr)],
           [Paragraph('Serviços prestados — autorizadas', cell), Paragraph(str(tot['pq']), cellr), Paragraph(_money(tot['pv']), cellr), Paragraph(_money(tot['pi']), cellr)],
           [Paragraph('Serviços tomados — autorizadas', cell), Paragraph(str(tot['tq']), cellr), Paragraph(_money(tot['tv']), cellr), Paragraph(_money(tot['ti']), cellr)],
           [Paragraph('TOTAL AUTORIZADAS', bold), Paragraph(str(aq), boldr), Paragraph(_money(av), boldr), Paragraph(_money(tot['pi'] + tot['ti']), boldr)],
           [Paragraph('Serviços prestados — canceladas', cell), Paragraph(str(tot['pcq']), cellr), Paragraph(_money(tot['pcv']), cellr), Paragraph('—', cellr)],
           [Paragraph('Serviços tomados — canceladas', cell), Paragraph(str(tot['tcq']), cellr), Paragraph(_money(tot['tcv']), cellr), Paragraph('—', cellr)],
           [Paragraph('TOTAL CANCELADAS (não somadas acima)', bold), Paragraph(str(tot['cq']), boldr), Paragraph(_money(tot['cv']), boldr), Paragraph('—', boldr)],
           [Paragraph('ISS retido (dentro do ISS acima)', cell), '', '', Paragraph(_money(tot['ri']), cellr)],
           [Paragraph('ISS pago fora do município do prestador (dentro do ISS acima)', cell), Paragraph(str(tot['fq']), cellr), '', Paragraph(_money(tot['fi']), cellr)]]
    ft = Table(fin, colWidths=[110 * mm, 25 * mm, 50 * mm, 45 * mm], hAlign='LEFT')
    ft.setStyle(TableStyle(base_style + [('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0, 3), (-1, 3), soft), ('BACKGROUND', (0, 6), (-1, 6), soft)]))
    story += [Spacer(1, 6 * mm), KeepTogether([ft])]
    def footer(canvas, d):
        canvas.saveState(); canvas.setFont('Helvetica', 8); canvas.setFillColor(muted)
        canvas.drawString(14 * mm, 8 * mm, f"Exato Central Fiscal • gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"); canvas.drawRightString(landscape(A4)[0] - 14 * mm, 8 * mm, f'Página {d.page}')
        if d.page > 1:
            canvas.drawString(14 * mm, landscape(A4)[1] - 9 * mm, f"{title} • {company_name or 'Empresa'} • CNPJ {_doc(cnpj)} • {period_label}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return str(output_path)


def report_row_from_xml(xml_bytes, cnpj='', situacao='Autorizada'):
    """Linha do relatório mensal a partir do XML da nota."""
    meta = nfse.parse_nfse(xml_bytes, cnpj)
    tomado = meta['direcao'] == 'Entrada'
    party = meta['prestador'] if tomado else meta['tomador']
    trib = nfse.parse_nfse_tributos(xml_bytes); mun = nfse.parse_nfse_municipio(xml_bytes)
    return {'numero': meta['numero'], 'data': str(meta['data'])[:10], 'tipo': 'Tomado' if tomado else 'Prestado', 'nome': party['nome'] or party['doc'], 'doc': party['doc'],
            'valor': meta['valor'], 'situacao': situacao, 'chave': meta['chave'], 'aliquota': trib['aliquota'], 'iss': trib['valor_iss'], 'iss_retido': trib['iss_retido'],
            'iss_fora': mun['fora'] or '—', 'municipio': mun['incid_nome'] or mun['incid_cod'] or '—'}
