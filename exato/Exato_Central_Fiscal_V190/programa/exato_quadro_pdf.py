"""Quadro "Autorizadas x Canceladas" para os relatórios de NF-e, NFC-e e CT-e (V179). Sem Tkinter.

O relatório principal (núcleo protegido) não é alterado: este quadro vira UMA PÁGINA a mais no fim do mesmo PDF, com as notas autorizadas e as canceladas em
linhas separadas (quantidade e valor), por tipo e por movimentação, e o total de cada grupo. Assim ninguém confunde o que vale com o que foi cancelado.

`normalizar_eventos`: o aviso de cancelamento que a SEFAZ entrega ao destinatário (resumo do evento) não traz o código de situação que o relatório
principal procura; para ESTE relatório (só na memória, nada é gravado) ele é tratado como cancelamento registrado, pois só existe com protocolo.
"""
import re
from datetime import datetime
from decimal import Decimal
from html import escape

TIPOS = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e'}
_RESUMO = re.compile(rb'^\s*(?:<\?xml[^>]*\?>\s*)?(?:<!--.*?-->\s*)*<(?:[A-Za-z_][\w.-]*:)?resEvento\b', re.S)
_TP = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?tpEvento\s*>\s*(\d+)\s*<')
_CH = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?ch(?:NFe|CTe)\s*>\s*(\d{44})\s*<')
_PROT = re.compile(rb'<(?:[A-Za-z_][\w.-]*:)?nProt\s*>\s*\d{10,}\s*<')


def _bytes(x):
    if isinstance(x, memoryview): return x.tobytes()
    if isinstance(x, (bytes, bytearray)): return bytes(x)
    return str(x or '').encode('utf-8', errors='replace')


def normalizar_eventos(docs):
    """Lista nova de documentos em que cada resumo de cancelamento (com protocolo) ganha a situação 'registrado' (cStat 135), só na memória."""
    saida = []
    for d in docs or []:
        try:
            if str(d.get('status') or '') == 'Evento' or str(d.get('tipo') or '') == 'Evento':
                raw = _bytes(d.get('xml'))
                if _RESUMO.match(raw[:600]):
                    tp = _TP.search(raw); ch = _CH.search(raw)
                    if tp and tp.group(1) in (b'110111', b'110112') and ch and _PROT.search(raw):
                        novo = dict(d.items())
                        novo['xml'] = raw + b'<retEvento><infEvento><cStat>135</cStat><tpEvento>' + tp.group(1) + b'</tpEvento><chNFe>' + ch.group(1) + b'</chNFe></infEvento></retEvento>'
                        d = novo
        except Exception:
            pass
        saida.append(d)
    return saida


def _valor(d):
    try: return Decimal(str(d.get('valor') if d.get('valor') not in (None, '') else 0))
    except Exception: return Decimal('0.00')


def quadro(docs):
    """[(familia, movimentação, aut_notas, aut_valor, canc_notas, canc_valor)] a partir dos documentos (situação do banco: Autorizado / Cancelado)."""
    grupos = {}
    for d in docs or []:
        st = str(d.get('status') or '')
        fam = str(d.get('family') or '')
        if st not in ('Autorizado', 'Cancelado') or fam not in TIPOS: continue
        mov = 'Entrada' if str(d.get('direcao') or '') == 'Entrada' else 'Saída'
        g = grupos.setdefault((fam, mov), {'an': 0, 'av': Decimal('0.00'), 'cn': 0, 'cv': Decimal('0.00')})
        if st == 'Cancelado': g['cn'] += 1; g['cv'] += _valor(d)
        else: g['an'] += 1; g['av'] += _valor(d)
    ordem = list(TIPOS)
    return [(f, m, g['an'], g['av'], g['cn'], g['cv']) for (f, m), g in sorted(grupos.items(), key=lambda kv: (ordem.index(kv[0][0]), kv[0][1]))]


def _money(v):
    return 'R$ ' + f'{Decimal(str(v)):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _doc(d):
    d = re.sub(r'\D', '', str(d or ''))
    return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}' if len(d) == 14 else (d or '—')


def gerar_quadro_pdf(caminho, docs, empresa='', cnpj='', periodo=''):
    """Uma página (A4 em pé) com o quadro. Devolve o caminho, ou None se não há nota autorizada/cancelada."""
    linhas = quadro(docs)
    if not linhas: return None
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    ink = colors.HexColor('#0F172A'); muted = colors.HexColor('#64748B'); line = colors.HexColor('#E6EAF1'); red = colors.HexColor('#E11D2E'); soft = colors.HexColor('#EEF2F7'); rubro = colors.HexColor('#B91C1C')
    st = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=st['Title'], fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=ink, alignment=0, spaceAfter=2)
    small = ParagraphStyle('small', parent=st['BodyText'], fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=muted)
    cell = ParagraphStyle('cell', parent=st['BodyText'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=ink)
    cellr = ParagraphStyle('cellr', parent=cell, alignment=2)
    ruim = ParagraphStyle('ruim', parent=cellr, textColor=rubro)
    hd = ParagraphStyle('hd', parent=cell, fontName='Helvetica-Bold', textColor=colors.white); hdr = ParagraphStyle('hdr', parent=hd, alignment=2)
    bold = ParagraphStyle('bold', parent=cell, fontName='Helvetica-Bold'); boldr = ParagraphStyle('boldr', parent=bold, alignment=2)
    doc = SimpleDocTemplate(str(caminho), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title='Autorizadas e canceladas')
    dados = [[Paragraph(x, h) for x, h in (('Tipo', hd), ('Movimentação', hd), ('Autorizadas (notas)', hdr), ('Autorizadas (valor)', hdr), ('Canceladas (notas)', hdr), ('Canceladas (valor)', hdr))]]
    tn = tc = 0; tv = tcv = Decimal('0.00')
    for fam, mov, an, av, cn, cv in linhas:
        dados.append([Paragraph(TIPOS[fam], cell), Paragraph(mov, cell), Paragraph(str(an), cellr), Paragraph(_money(av), cellr), Paragraph(str(cn), ruim if cn else cellr), Paragraph(_money(cv), ruim if cn else cellr)])
        tn += an; tv += av; tc += cn; tcv += cv
    dados.append([Paragraph('Total', bold), '', Paragraph(str(tn), boldr), Paragraph(_money(tv), boldr), Paragraph(str(tc), boldr), Paragraph(_money(tcv), boldr)])
    t = Table(dados, colWidths=[22 * mm, 28 * mm, 30 * mm, 36 * mm, 30 * mm, 36 * mm], repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), red), ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]), ('BACKGROUND', (0, -1), (-1, -1), soft),
                           ('GRID', (0, 0), (-1, -1), 0.3, line), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story = [Paragraph('Autorizadas e canceladas', h1), Paragraph(f'<b>{escape(empresa or "Empresa")}</b>  •  CNPJ {escape(_doc(cnpj))}' + (f'  •  {escape(periodo)}' if periodo else ''), small), Spacer(1, 4 * mm), t, Spacer(1, 3 * mm),
             Paragraph(f'<b>Autorizadas:</b> {tn} nota(s) • {_money(tv)}', cell), Paragraph(f'<b>Canceladas:</b> {tc} nota(s) • {_money(tcv)} (não somadas nas autorizadas)', cell), Spacer(1, 3 * mm),
             Paragraph('Este quadro soma as notas autorizadas e as canceladas SEPARADAMENTE. Os valores do relatório acima que dizem respeito a entradas, saídas e totais consideram só as autorizadas.', small)]
    def rodape(canvas, d):
        canvas.saveState(); canvas.setFont('Helvetica', 8); canvas.setFillColor(muted)
        canvas.drawString(14 * mm, 9 * mm, f"Exato Central Fiscal • gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"); canvas.restoreState()
    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return str(caminho)


def acrescentar_quadro(pdf_principal, docs, empresa='', cnpj='', periodo=''):
    """Junta o quadro como última página do PDF principal. Devolve True se juntou. Nunca levanta erro por causa do quadro (o relatório principal fica como está)."""
    import os, tempfile
    tmp = None
    try:
        import pypdf
        fd, tmp = tempfile.mkstemp(suffix='.pdf', prefix='exato_quadro_'); os.close(fd)
        if not gerar_quadro_pdf(tmp, docs, empresa, cnpj, periodo): return False
        w = pypdf.PdfWriter()
        for origem in (pdf_principal, tmp):
            for pg in pypdf.PdfReader(str(origem)).pages: w.add_page(pg)
        novo = str(pdf_principal) + '.novo'
        with open(novo, 'wb') as f: w.write(f)
        os.replace(novo, str(pdf_principal))
        return True
    except Exception:
        return False
    finally:
        if tmp:
            try: os.remove(tmp)
            except OSError: pass
