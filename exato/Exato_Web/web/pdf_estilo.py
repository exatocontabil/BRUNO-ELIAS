"""Estilo visual comum dos relatórios em PDF do Exato Web (só apresentação: nenhum número é calculado aqui).

Peças: página com capa escura (logo, título, empresa, período), cabeçalho fino e rodapé "Página x de y", cartões arredondados com faixa de cor,
faixas de seção, tabelas com cabeçalho colorido, listras suaves e linhas finas, selos de situação e gráficos (barras e rosca).
Só fontes embutidas do PDF (Helvetica), para abrir igual em qualquer computador. Texto de tabela é cortado pela largura real (`ajustar`)."""
import re
from datetime import datetime
from decimal import Decimal
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rlcanvas
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

hx = colors.HexColor
MARINHO = '#0B1220'; MARINHO2 = '#16264A'; VERMELHO = '#E11D2E'; TINTA = '#0F172A'; MUDO = '#64748B'; LINHA = '#E6EAF1'; FUNDO = '#F6F8FB'; SUAVE = '#EEF2F7'
VERDE = '#15A34A'; AMBAR = '#D97706'; AZUL = '#2563EB'; ROXO = '#7C3AED'; ALERTA = '#B91C1C'; ROSA = '#FEE2E2'
COR_TIPO = {'nfe': AZUL, 'nfce': AMBAR, 'cte': VERDE, 'nfse': ROXO}
PAGINA = landscape(A4); LARG = PAGINA[0] / mm - 28          # largura útil (mm) com margens de 14 mm
ZERO = Decimal('0.00')


def dinheiro(v):
    try: d = Decimal(str(v if v not in (None, '') else 0))
    except Exception: return str(v)
    return ('-' if d < 0 else '') + 'R$ ' + f'{abs(d):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def cnpj_fmt(d):
    d = re.sub(r'\D', '', str(d or ''))
    if len(d) == 14: return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}'
    if len(d) == 11: return f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}'
    return d or '—'


def data_br(data):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(data or ''))
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m else (str(data or '') or '—')


def mes_curto(chave):
    m = re.match(r'(\d{4})-(\d{2})', str(chave or ''))
    nomes = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
    return f'{nomes[int(m.group(2)) - 1]}/{m.group(1)[2:]}' if m and 1 <= int(m.group(2)) <= 12 else 'sem data'


def ajustar(texto, largura_mm, fonte='Helvetica', tamanho=7.8, folga_pt=12):
    """Corta o texto pela largura real da coluna, com '…'."""
    texto = str(texto or ''); limite = largura_mm * 72.0 / 25.4 - folga_pt
    if stringWidth(texto, fonte, tamanho) <= limite: return texto
    while texto and stringWidth(texto + '…', fonte, tamanho) > limite: texto = texto[:-1]
    return texto.rstrip() + '…'


def estilos():
    base = getSampleStyleSheet()['BodyText']
    def e(nome, **k):
        d = dict(parent=base, fontName='Helvetica', fontSize=9, leading=12, textColor=hx(TINTA)); d.update(k); return ParagraphStyle(nome, **d)
    return {'corpo': e('corpo'), 'mudo': e('mudo', textColor=hx(MUDO)), 'peq': e('peq', fontSize=8, leading=10.5, textColor=hx(MUDO)),
            'h2': e('h2', fontName='Helvetica-Bold', fontSize=14, leading=18, spaceBefore=4, spaceAfter=3),
            'cel': e('cel', fontSize=8.2, leading=10.4), 'celr': e('celr', fontSize=8.2, leading=10.4, alignment=TA_RIGHT),
            'cab': e('cab', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white), 'cabr': e('cabr', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=TA_RIGHT),
            'neg': e('neg', fontSize=8.4, leading=10.8, fontName='Helvetica-Bold'), 'negr': e('negr', fontSize=8.4, leading=10.8, fontName='Helvetica-Bold', alignment=TA_RIGHT)}


ST = estilos()


def selo(situacao):
    """Texto de situação com bolinha colorida (em Paragraph)."""
    s = str(situacao or '—'); cor = {'Autorizada': VERDE, 'Cancelada': ALERTA}.get(s, MUDO)
    return f'<font color="{cor}"><b>•</b> {escape(s)}</font>'


# ---------------------------------------------------------------------------------------------- peças desenhadas
class Cartao(Flowable):
    """Cartão arredondado com barra de cor: título pequeno, valor grande e uma linha de apoio."""
    def __init__(self, titulo, valor, sub, cor, largura_mm, altura_mm=24):
        super().__init__(); self.t, self.v, self.s, self.cor = titulo, valor, sub, cor; self.w = largura_mm * mm; self.h = altura_mm * mm
    def wrap(self, *a): return self.w, self.h
    def draw(self):
        c = self.canv; c.saveState()
        c.setFillColor(hx('#FFFFFF')); c.setStrokeColor(hx(LINHA)); c.setLineWidth(0.8); c.roundRect(0, 0, self.w, self.h, 3.2 * mm, stroke=1, fill=1)
        c.setFillColor(hx(self.cor)); c.roundRect(0, 0, 2.4 * mm, self.h, 1.2 * mm, stroke=0, fill=1)
        c.setFillColor(hx(self.cor)); c.setFillAlpha(0.10); c.circle(self.w - 7 * mm, self.h - 7 * mm, 9 * mm, stroke=0, fill=1); c.setFillAlpha(1)
        c.setFillColor(hx(MUDO)); c.setFont('Helvetica-Bold', 7.4); c.drawString(6 * mm, self.h - 7 * mm, self.t.upper())
        c.setFillColor(hx(self.cor)); tam = 16
        while stringWidth(self.v, 'Helvetica-Bold', tam) > self.w - 10 * mm and tam > 9: tam -= 1
        c.setFont('Helvetica-Bold', tam); c.drawString(6 * mm, self.h - 14.8 * mm, self.v)
        c.setFillColor(hx(MUDO)); c.setFont('Helvetica', 7.4); c.drawString(6 * mm, 3.6 * mm, ajustar(self.s, self.w / mm - 8, 'Helvetica', 7.4, 0))
        c.restoreState()


class Faixa(Flowable):
    """Faixa arredondada de título de seção, com um texto à direita."""
    def __init__(self, titulo, direita, cor, largura_mm=LARG, altura_mm=11):
        super().__init__(); self.t, self.d, self.cor = titulo, direita, cor; self.w = largura_mm * mm; self.h = altura_mm * mm
    def wrap(self, *a): return self.w, self.h
    def draw(self):
        c = self.canv; c.saveState(); c.setFillColor(hx(self.cor)); c.roundRect(0, 0, self.w, self.h, 3 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 13.5); c.drawString(5 * mm, self.h / 2 - 1.6 * mm, self.t)
        c.setFont('Helvetica', 8.8); c.drawRightString(self.w - 5 * mm, self.h / 2 - 1.2 * mm, self.d); c.restoreState()


def tabela(linhas, larguras_mm, cor_cab=MARINHO, direita=(), repetir=1, extra=(), zebra=True, tam=8.2):
    """Tabela moderna: cabeçalho colorido de cantos redondos, listras suaves e só linhas horizontais finas."""
    t = Table(linhas, colWidths=[w * mm for w in larguras_mm], repeatRows=repetir, hAlign='LEFT')
    est = [('BACKGROUND', (0, 0), (-1, 0), hx(cor_cab)), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LINEBELOW', (0, 1), (-1, -1), 0.25, hx(LINHA)),
           ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
           ('FONTSIZE', (0, 0), (-1, -1), tam), ('ROUNDEDCORNERS', [4, 4, 4, 4])]
    if zebra: est.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, hx(FUNDO)]))
    est += [('ALIGN', (c, 0), (c, -1), 'RIGHT') for c in direita]
    t.setStyle(TableStyle(est + list(extra))); return t


def lado_a_lado(esq, dir_, larg_esq_mm, larg_dir_mm, folga_mm=6):
    t = Table([[esq, '', dir_]], colWidths=[larg_esq_mm * mm, folga_mm * mm, larg_dir_mm * mm], hAlign='LEFT')
    t.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0), ('VALIGN', (0, 0), (-1, -1), 'TOP')])); return t


def barras(titulo, categorias, series, cores, nomes, largura_mm=132, altura_mm=56):
    from reportlab.graphics.shapes import Drawing, String, Rect
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    d = Drawing(largura_mm * mm, altura_mm * mm); d.add(String(0, (altura_mm - 5) * mm, titulo, fontName='Helvetica-Bold', fontSize=9.5, fillColor=hx(TINTA)))
    bc = VerticalBarChart(); bc.x = 15 * mm; bc.y = 9 * mm; bc.width = (largura_mm - 19) * mm; bc.height = (altura_mm - 24) * mm
    bc.data = series; bc.categoryAxis.categoryNames = categorias; bc.categoryAxis.labels.fontSize = 7; bc.categoryAxis.labels.fillColor = hx(MUDO); bc.valueAxis.labels.fontSize = 7; bc.valueAxis.labels.fillColor = hx(MUDO)
    baixo = min((min(x) for x in series if x), default=0); alto = max((max(x) for x in series if x), default=0); topo = max(abs(baixo), abs(alto))
    bc.valueAxis.valueMin = min(0, baixo * 1.12); bc.valueAxis.valueMax = max(0, alto * 1.12) or 1; bc.categoryAxis.joinAxisMode = 'bottom'
    bc.valueAxis.labelTextFormat = (lambda v: f'{v / 1000:.0f} mil') if topo >= 10000 else (lambda v: f'{v:.0f}')
    bc.bars.strokeColor = None; bc.groupSpacing = 7; bc.barSpacing = 1.2; bc.valueAxis.gridStrokeColor = hx(LINHA); bc.valueAxis.visibleGrid = 1; bc.valueAxis.strokeColor = None; bc.categoryAxis.strokeColor = hx(LINHA)
    for i, c in enumerate(cores): bc.bars[i].fillColor = hx(c)
    d.add(bc); x = largura_mm - 36 * len(nomes) / 1.0 if len(nomes) > 1 else largura_mm - 26
    for i, n in enumerate(nomes):
        d.add(Rect(x * mm + i * 31 * mm, (altura_mm - 5.6) * mm, 2.6 * mm, 2.6 * mm, fillColor=hx(cores[i]), strokeColor=None, rx=0.8 * mm, ry=0.8 * mm)); d.add(String(x * mm + i * 31 * mm + 4 * mm, (altura_mm - 5) * mm, n, fontName='Helvetica', fontSize=7.6, fillColor=hx(MUDO)))
    return d


def rosca(titulo, partes, centro, largura_mm=132, altura_mm=52):
    """Rosca com a participação de cada tipo. `partes`: [(rótulo, valor, cor)]; `centro`: texto no meio."""
    from reportlab.graphics.shapes import Drawing, String, Circle, Rect
    from reportlab.graphics.charts.piecharts import Pie
    d = Drawing(largura_mm * mm, altura_mm * mm); d.add(String(0, (altura_mm - 5) * mm, titulo, fontName='Helvetica-Bold', fontSize=9.5, fillColor=hx(TINTA)))
    total = sum(float(v) for _, v, _ in partes)
    if total <= 0:
        d.add(String(0, (altura_mm - 20) * mm, 'Sem valores neste período.', fontName='Helvetica', fontSize=8.5, fillColor=hx(MUDO))); return d
    r = 16 * mm; cx = 22 * mm; cy = (altura_mm - 9) * mm - r
    p = Pie(); p.x = cx - r; p.y = cy - r; p.width = p.height = 2 * r; p.data = [float(v) for _, v, _ in partes]; p.labels = None; p.slices.strokeColor = colors.white; p.slices.strokeWidth = 1.4
    for i, (_, _, c) in enumerate(partes): p.slices[i].fillColor = hx(c)
    d.add(p); d.add(Circle(cx, cy, r * 0.58, fillColor=colors.white, strokeColor=None))
    d.add(String(cx, cy - 1 * mm, centro, fontName='Helvetica-Bold', fontSize=7, fillColor=hx(TINTA), textAnchor='middle'))
    y = cy + 8 * mm
    for rot, v, c in partes:
        pct = float(v) / total * 100
        d.add(Rect(50 * mm, y - 0.4 * mm, 3 * mm, 3 * mm, fillColor=hx(c), strokeColor=None, rx=0.8 * mm, ry=0.8 * mm)); d.add(String(55 * mm, y, f'{rot}', fontName='Helvetica-Bold', fontSize=8.2, fillColor=hx(TINTA)))
        d.add(String(largura_mm * mm - 1 * mm, y, f'{dinheiro(v)}  •  {pct:.0f}%', fontName='Helvetica', fontSize=8, fillColor=hx(MUDO), textAnchor='end')); y -= 6.2 * mm
    return d


# ---------------------------------------------------------------------------------------------- página
def _numerada(meta):
    """Canvas que desenha a capa na primeira página, o cabeçalho fino nas outras e o rodapé "Página x de y" em todas."""
    class _N(rlcanvas.Canvas):
        def __init__(self, *a, **k): super().__init__(*a, **k); self._est = []
        def showPage(self): self._est.append(dict(self.__dict__)); self._startPage()
        def save(self):
            n = len(self._est)
            for e in self._est: self.__dict__.update(e); self._moldura(n); super().showPage()
            super().save()
        def _moldura(self, n):
            L, A = PAGINA; ml = 14 * mm
            if self._pageNumber == 1: self._capa(L, A)
            else:
                self.setFillColor(hx(MARINHO)); self.rect(0, A - 9 * mm, L, 9 * mm, stroke=0, fill=1); self.setFillColor(hx(VERMELHO)); self.rect(0, A - 9.7 * mm, L, 0.7 * mm, stroke=0, fill=1)
                self.setFillColor(colors.white); self.setFont('Helvetica-Bold', 8.2); self.drawString(ml, A - 6 * mm, meta['titulo'])
                self.setFont('Helvetica', 8); self.drawRightString(L - ml, A - 6 * mm, ajustar(meta.get('empresa_linha', ''), 170, 'Helvetica', 8, 0))
            self.setStrokeColor(hx(LINHA)); self.setLineWidth(0.6); self.line(ml, 12 * mm, L - ml, 12 * mm)
            self.setFont('Helvetica', 7.8); self.setFillColor(hx(MUDO)); self.drawString(ml, 7.6 * mm, f"Exato Central Fiscal  •  gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
            self.drawRightString(L - ml, 7.6 * mm, f'Página {self._pageNumber} de {n}')
        def _capa(self, L, A):
            h = 50 * mm; self.saveState(); p = self.beginPath(); p.rect(0, A - h, L, h); self.clipPath(p, stroke=0, fill=0); self.setFillColor(hx(MARINHO)); self.rect(0, A - h, L, h, stroke=0, fill=1)
            self.setFillColor(hx(MARINHO2)); self.setFillAlpha(0.9); self.circle(L - 20 * mm, A - 8 * mm, 46 * mm, stroke=0, fill=1)
            self.setFillColor(hx(VERMELHO)); self.setFillAlpha(0.35); self.circle(L - 4 * mm, A - h + 6 * mm, 30 * mm, stroke=0, fill=1); self.setFillAlpha(1); self.restoreState()
            self.setFillColor(hx(VERMELHO)); self.rect(0, A - h - 1.2 * mm, L, 1.2 * mm, stroke=0, fill=1)
            x = 14 * mm; logo = meta.get('logo')
            if logo:
                try:
                    from reportlab.lib.utils import ImageReader
                    im = ImageReader(str(logo)); iw, ih = im.getSize(); esc = min(36 * mm / iw, 11 * mm / ih)
                    self.setFillColor(colors.white); self.roundRect(x, A - 19 * mm, iw * esc + 6 * mm, ih * esc + 4 * mm, 2.4 * mm, stroke=0, fill=1); self.drawImage(im, x + 3 * mm, A - 17 * mm, iw * esc, ih * esc, mask='auto')
                except Exception: pass
            self.setFillColor(colors.white); self.setFont('Helvetica-Bold', 25); self.drawString(x, A - 31 * mm, meta['titulo'])
            self.setFont('Helvetica-Bold', 11.5); self.drawString(x, A - 38.5 * mm, ajustar(meta.get('empresa_linha', ''), 230, 'Helvetica-Bold', 11.5, 0))
            self.setFillColor(hx('#B9C6E3')); self.setFont('Helvetica', 9.2); self.drawString(x, A - 44.5 * mm, ajustar(meta.get('sub', ''), 230, 'Helvetica', 9.2, 0))
    return _N


def montar(caminho, meta, story, titulo_pdf=''):
    """Monta o PDF paisagem. `meta`: titulo, empresa_linha, sub, logo. A primeira página reserva a faixa da capa."""
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(str(caminho), pagesize=PAGINA, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=15 * mm, bottomMargin=16 * mm, title=titulo_pdf or meta['titulo'], author='Exato Central Fiscal')
    doc.build([Spacer(1, 40 * mm)] + list(story), canvasmaker=_numerada(meta)); return str(caminho)
