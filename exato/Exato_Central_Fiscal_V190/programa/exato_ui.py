"""Exato Design: paleta clara/escura, tradução automática de cores para o tema escuro e componentes visuais modernos.

Tema escuro SEM reescrever as telas: o programa continua usando as cores claras de sempre; quando o tema escuro está ligado,
cada cor passada ao Tk (widgets, estilos, tags, itens de desenho) é traduzida na hora. Os PDFs e planilhas não são afetados
(não passam por aqui).
"""
import time
import tkinter as tk
from tkinter import ttk

_MODE = 'claro'

# ---- cores: (claro -> escuro). Fundos e textos têm tabelas separadas porque o branco é "superfície" num fundo e "tinta" num texto.
_BG_PAIRS = {
    '#FFFFFF': '#141C2B', '#F4F6FA': '#0D1320', '#F5F7FA': '#0D1320', '#F3F5F9': '#0D1320', '#F6F8FB': '#0D1320',
    '#F8FAFC': '#1A2436', '#FAFBFC': '#182234', '#FCFCFD': '#182234', '#FAFBFD': '#121A29',
    '#EEF2F7': '#1F2A3F', '#EEF2F6': '#1F2A3F', '#F1F5F9': '#1F2A3F', '#E2E8F0': '#2A3650',
    '#E6EAF1': '#26324A', '#DDE3EC': '#33415C', '#C5CEDB': '#44536F', '#EDF0F5': '#222D42', '#E8EDF4': '#222D42', '#F4F7FB': '#1D283D', '#E7EEF5': '#26324A', '#C8E4D1': '#1F4D37', '#CBD5E1': '#33415C', '#D9E2EC': '#2E3B55', '#D5DCE6': '#33415C', '#E4E7EC': '#2B3852', '#E5E7EB': '#2B3852', '#D9DDE3': '#2B3852', '#B8C2D1': '#44536F',
    '#FEF2F2': '#3A1B22', '#FEE2E2': '#3A1B22', '#FFF4F4': '#3A1B22', '#FFF1F2': '#3A1820', '#FFF0F1': '#3A1820', '#FECACA': '#5A2630', '#F2C5CA': '#5A2630',
    '#DCFCE7': '#12301F', '#ECFDF3': '#12301F', '#EDF9F2': '#12301F', '#ECF9F1': '#12301F', '#D1FAE5': '#12301F',
    '#FFFBEB': '#3A2C10', '#FEF3C7': '#3A2C10', '#FFF7E8': '#3A2C10', '#F2D29B': '#5A4418',
    '#E0F2FE': '#10283D', '#DBEAFE': '#10283D',
    # V180: claros que ficavam claros no tema escuro (ex.: botões de tipo de documento da Auditoria)
    '#F2F4F7': '#1F2A3F', '#F3F4F6': '#1F2A3F', '#EEF3F8': '#1F2A3F', '#EAF0F6': '#222D42', '#E5EDF5': '#26324A', '#E7EDF5': '#26324A', '#E8EEF6': '#26324A',
    '#FBFCFE': '#182234', '#FBFCFD': '#182234', '#F7F9FC': '#1A2436', '#FDF1F2': '#3A1820', '#FFF2F3': '#3A1820', '#FFF3F4': '#3A1820',
    '#EFFAF3': '#12301F', '#E9F8EF': '#12301F', '#FFFAEB': '#3A2C10', '#FFF7ED': '#3A2C10', '#FFF3DD': '#3A2C10', '#F0F9FF': '#10283D',
}
_FG_PAIRS = {
    '#0F172A': '#E8EDF6', '#111827': '#E8EDF6', '#1E293B': '#D5DDEA', '#334155': '#B7C3D6', '#475569': '#A9B7CC', '#64748B': '#93A3BC', '#94A3B8': '#7B8CA6',
    '#B91C1C': '#FCA5A5', '#DC2626': '#FCA5A5', '#7F1D1D': '#FCA5A5', '#B91C28': '#FCA5A5',
    '#16A34A': '#4ADE80', '#15803D': '#4ADE80',
    '#D97706': '#FBBF24', '#B45309': '#FBBF24', '#B96D00': '#FBBF24',
    '#2563EB': '#7DB1FF', '#0369A1': '#7DD3FC',
}
_BG_KEYS = {'bg', 'background', 'activebackground', 'highlightbackground', 'disabledbackground', 'readonlybackground', 'selectbackground', 'troughcolor', 'buttonbackground',
            'fieldbackground', 'lightcolor', 'darkcolor', 'bordercolor', 'highlightcolor', 'fill', 'outline', 'activefill', 'activeoutline', 'disabledfill', 'sliderbackground', 'focuscolor'}
_FG_KEYS = {'fg', 'foreground', 'activeforeground', 'insertbackground', 'insertcolor', 'disabledforeground', 'selectforeground', 'arrowcolor', 'selectcolor'}
_NAMED = {'white': '#FFFFFF', 'black': '#000000'}


def is_dark():
    return _MODE == 'escuro'


def set_mode(mode):
    global _MODE
    _MODE = 'escuro' if str(mode).lower().startswith('esc') or str(mode).lower() == 'dark' else 'claro'
    _PIL_CACHE.clear()


def mode():
    return _MODE


def tr(color, kind='bg'):
    """Traduz uma cor do tema claro para o escuro (quando ligado). kind: 'bg' (fundo/borda) ou 'fg' (texto)."""
    if _MODE != 'escuro' or not isinstance(color, str):
        return color
    c = _NAMED.get(color.lower(), color).upper()
    if not c.startswith('#'):
        return color
    table = _FG_PAIRS if kind == 'fg' else _BG_PAIRS
    return table.get(c, color)


def _tr_option(key, value):
    if key in _FG_KEYS: return tr(value, 'fg')
    if key in _BG_KEYS: return tr(value, 'bg')
    return value


def _tr_dict(d):
    if not d or _MODE != 'escuro': return d
    return {k: (_tr_option(k, v) if isinstance(v, str) else v) for k, v in d.items()}


_PATCHED = False


def install():
    """Liga a tradução de cores em todo o Tk/ttk (uma vez). Só tem efeito com o tema escuro."""
    global _PATCHED
    if _PATCHED: return
    _PATCHED = True
    orig_options = tk.Misc._options
    def _options(self, cnf, kw=None):
        if _MODE == 'escuro':
            if kw: kw = _tr_dict(kw)
            if cnf and isinstance(cnf, dict): cnf = _tr_dict(cnf)
        return orig_options(self, cnf, kw)
    tk.Misc._options = _options
    orig_cfg = ttk.Style.configure
    def configure(self, style, query_opt=None, **kw):
        return orig_cfg(self, style, query_opt, **_tr_dict(kw))
    ttk.Style.configure = configure
    orig_map = ttk.Style.map
    def map_(self, style, query_opt=None, **kw):
        if _MODE == 'escuro' and kw:
            kw = {k: [tuple(list(t[:-1]) + [_tr_option(k, t[-1])]) if isinstance(t, tuple) and t and isinstance(t[-1], str) else t for t in v] if isinstance(v, (list, tuple)) else v for k, v in kw.items()}
        return orig_map(self, style, query_opt, **kw)
    ttk.Style.map = map_
    orig_tag = ttk.Treeview.tag_configure
    def tag_configure(self, tagname, option=None, **kw):
        return orig_tag(self, tagname, option, **_tr_dict(kw))
    ttk.Treeview.tag_configure = tag_configure


# ---------- renderização com suavização (PIL) para cartões e etiquetas
_PIL_CACHE = {}


def _alive(photo):
    """A imagem em cache ainda existe? (ao reabrir a janela principal, por exemplo na troca de tema, o Tk antigo some e leva as imagens junto)"""
    try:
        photo.width(); return True
    except Exception:
        return False


def reset_caches():
    _PIL_CACHE.clear(); _ICON_CACHE.clear(); _KEEP_IMAGES.clear()


def palette():
    """Cores do tema atual para quem desenha com PIL (cartões, sombras, etiquetas)."""
    if _MODE == 'escuro':
        return {'bg': '#0D1320', 'surface': '#141C2B', 'surface_alt': '#1A2436', 'border': '#26324A', 'shadow': (0, 0, 0), 'text': '#E8EDF6', 'muted': '#93A3BC'}
    return {'bg': '#F4F6FA', 'surface': '#FFFFFF', 'surface_alt': '#F8FAFC', 'border': '#E6EAF1', 'shadow': (15, 23, 42), 'text': '#0F172A', 'muted': '#64748B'}


def _hex(c):
    """'#RRGGBB' -> (r, g, b). Nomes de cor ('white', 'SystemButtonFace' do Windows) nunca derrubam o desenho (V161)."""
    t = str(c).strip()
    if len(t) == 4 and t[0] == '#': t = '#' + ''.join(ch * 2 for ch in t[1:])
    try:
        h = t.lstrip('#')
        if len(h) == 6: return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        pass
    try:
        from PIL import ImageColor
        return tuple(ImageColor.getrgb(t)[:3])
    except Exception:
        return (240, 240, 240)


def to_hex(widget, color, default='#FFFFFF'):
    """Converte qualquer cor do Tk (inclusive nomes do sistema, como SystemButtonFace) em '#RRGGBB'."""
    t = str(color or '')
    if len(t) == 7 and t[0] == '#':
        try: int(t[1:], 16); return t
        except ValueError: pass
    try:
        r, g, b = widget.winfo_rgb(t)
        return '#%02x%02x%02x' % (r >> 8, g >> 8, b >> 8)
    except Exception:
        return default


def _render_card_pil(width, height, radius, fill, border, page_bg, shadow, shadow_rgb):
    from PIL import Image, ImageDraw, ImageFilter
    S = 3; pad = 6 if shadow else 0
    W, H = width * S, height * S
    base = Image.new('RGBA', (W, H), _hex(page_bg) + (255,))
    if shadow:
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
        d.rounded_rectangle((pad * S, (pad + 2) * S, W - pad * S, H - (pad - 1) * S), radius=radius * S, fill=shadow_rgb + (30 if shadow_rgb[0] > 40 else 110,))
        base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(radius=3.6 * S)))
    d = ImageDraw.Draw(base)
    box = (pad * S, pad * S, W - pad * S - 1, H - (pad + 1) * S)
    d.rounded_rectangle(box, radius=radius * S, fill=_hex(fill) + (255,), outline=_hex(border) + (255,), width=max(1, S))
    return base.resize((width, height), Image.Resampling.LANCZOS)


def card_image(width, height, radius=14, fill='#FFFFFF', border='#E6EAF1', page_bg='#F4F6FA', shadow=True, shadow_rgb=(15, 23, 42)):
    """Cartão de cantos arredondados com sombra suave, na cor da página (sem serrilhado).

    Rápido para qualquer tamanho: desenha uma vez um cartão pequeno e monta os demais esticando só as bordas (fatiamento 3x3).
    """
    from PIL import Image, ImageTk
    m = radius + (6 if shadow else 0) + 8
    width = max(int(width), 2 * m + 2); height = max(int(height), 2 * m + 2)
    key = ('card', width, height, radius, fill, border, page_bg, shadow, shadow_rgb)
    if key in _PIL_CACHE and _alive(_PIL_CACHE[key]): return _PIL_CACHE[key]
    skey = ('slice', radius, fill, border, page_bg, shadow, shadow_rgb)
    small = _PIL_CACHE.get(skey)
    if small is None:
        small = _render_card_pil(2 * m + 6, 2 * m + 6, radius, fill, border, page_bg, shadow, shadow_rgb); _PIL_CACHE[skey] = small
    sw, sh_ = small.size
    out = Image.new('RGBA', (width, height))
    out.paste(small.crop((0, 0, m, m)), (0, 0)); out.paste(small.crop((sw - m, 0, sw, m)), (width - m, 0))
    out.paste(small.crop((0, sh_ - m, m, sh_)), (0, height - m)); out.paste(small.crop((sw - m, sh_ - m, sw, sh_)), (width - m, height - m))
    cx, cy = sw // 2, sh_ // 2
    out.paste(small.crop((cx, 0, cx + 1, m)).resize((width - 2 * m, m)), (m, 0))
    out.paste(small.crop((cx, sh_ - m, cx + 1, sh_)).resize((width - 2 * m, m)), (m, height - m))
    out.paste(small.crop((0, cy, m, cy + 1)).resize((m, height - 2 * m)), (0, m))
    out.paste(small.crop((sw - m, cy, sw, cy + 1)).resize((m, height - 2 * m)), (width - m, m))
    out.paste(small.crop((cx, cy, cx + 1, cy + 1)).resize((width - 2 * m, height - 2 * m)), (m, m))
    photo = ImageTk.PhotoImage(out)
    if len(_PIL_CACHE) > 300: _PIL_CACHE.clear()
    _PIL_CACHE[key] = photo
    return photo


def pill_image(text, fg, bg, font_size=9, pad_x=10, pad_y=3, bold=True):
    """Etiqueta em pílula (situação, tipo...) com cantos totalmente arredondados."""
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    key = ('pill', text, fg, bg, font_size, pad_x, pad_y, bold, _MODE)
    if key in _PIL_CACHE and _alive(_PIL_CACHE[key]): return _PIL_CACHE[key]
    font = None
    for name in (('segoeuib.ttf' if bold else 'segoeui.ttf'), ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')):
        try:
            font = ImageFont.truetype(name, font_size * 3); break
        except Exception:
            continue
    font = font or ImageFont.load_default()
    probe = ImageDraw.Draw(Image.new('RGBA', (4, 4)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font)
    w = (r - l) + 2 * pad_x * 3; h = (b - t) + 2 * pad_y * 3 + 6
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=_hex(bg) + (255,))
    d.text((pad_x * 3 - l, (h - (b - t)) // 2 - t), text, font=font, fill=_hex(fg) + (255,))
    photo = ImageTk.PhotoImage(img.resize((max(1, w // 3), max(1, h // 3)), Image.Resampling.LANCZOS))
    _PIL_CACHE[key] = photo
    return photo


# ---------- componentes
class Card(tk.Canvas):
    """Cartão de cantos arredondados com sombra suave. Coloque o conteúdo em `card.body` (Frame)."""
    def __init__(self, parent, page_bg=None, fill='#FFFFFF', border='#E6EAF1', radius=14, pad=14, shadow=True, **kw):
        self._page_bg = page_bg or '#F4F6FA'; self._fill = fill; self._border = border; self._radius = radius; self._pad = pad; self._shadow = shadow
        super().__init__(parent, bg=self._page_bg, highlightthickness=0, bd=0, height=40, **kw)
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(0, 0, window=self.body, anchor='nw')
        self._img_id = None; self._size = (0, 0)
        self.bind('<Configure>', self._on_canvas, add='+'); self.body.bind('<Configure>', self._on_body, add='+')

    def _inset(self):
        return (6 if self._shadow else 0) + self._pad

    def _on_canvas(self, e=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 8: return
        ins = self._inset()
        self.itemconfigure(self._win, width=max(w - 2 * ins, 10))
        self.coords(self._win, ins, ins - (1 if self._shadow else 0))
        if (w, h) != self._size:
            self._size = (w, h)
            self._photo = card_image(w, h, self._radius, self._fill, self._border, self._page_bg, self._shadow, palette()['shadow'])
            if self._img_id is None:
                self._img_id = self.create_image(0, 0, image=self._photo, anchor='nw'); self.tag_lower(self._img_id)
            else:
                self.itemconfigure(self._img_id, image=self._photo)

    def _on_body(self, e=None):
        want = self.body.winfo_reqheight() + 2 * self._inset()
        if abs(int(self.cget('height')) - want) > 1:
            self.configure(height=want)


def icon_font_name(root):
    """Fonte de ícones do Windows (Segoe Fluent Icons ou Segoe MDL2 Assets), se existir."""
    import tkinter.font as tkfont
    try:
        fams = set(tkfont.families(root))
    except Exception:
        return None
    for name in ('Segoe Fluent Icons', 'Segoe MDL2 Assets'):
        if name in fams: return name
    return None


# glifos da fonte de ícones do Windows (nome -> código); no Linux/sem a fonte usa-se o símbolo de reserva
ICONS = {
    'inicio': ('', '⌂'), 'buscar_xml': ('', '↻'), 'nfse': ('', '▥'), 'documentos': ('', '▤'), 'empresas': ('', '▣'),
    'auditoria': ('', '⌕'), 'pendencias': ('', '!'), 'historico': ('', '◷'), 'relatorios': ('', '◫'), 'usuarios': ('', '♙'),
    'certificado': ('', '◉'), 'manutencao': ('', '⚙'), 'tema_escuro': ('', '☾'), 'tema_claro': ('', '☀'), 'ajuda': ('', '?'),
    'repositorio': ('\ue8f1', '▦'),
    'sair': ('', '⏻'), 'buscar': ('', '⌕'), 'sino': ('', '●'),
}


def icon_glyph(name, font_ok):
    g = ICONS.get(name, ('', '•'))
    return g[0] if font_ok else g[1]


class ModernCard(tk.Frame):
    """Cartão moderno: cantos arredondados, borda fina e sombra suave. Usa-se como um Frame comum (o conteúdo vai direto nele).

    O fundo é uma imagem suavizada colocada atrás do conteúdo; `bg`, `highlightbackground` e `highlightcolor` (usados antes para
    cor e borda) continuam funcionando e redesenham o cartão. Sombra só quando o cartão está sobre o fundo da página.
    """
    def __init__(self, parent, fill=None, border=None, radius=14, shadow=None, **kw):
        fill = to_hex(parent, kw.pop('bg', None) or kw.pop('background', None) or fill or '#FFFFFF')
        border = to_hex(parent, kw.pop('highlightbackground', None) or border or '#E6EAF1', '#E6EAF1')
        kw.pop('highlightcolor', None); kw.pop('highlightthickness', None)
        try:
            page_bg = to_hex(parent, parent.cget('bg'), '#F4F6FA')      # no Windows o fundo padrão vem como nome ('SystemButtonFace')
        except Exception:
            page_bg = '#F4F6FA'
        self._page_bg = page_bg
        if shadow is None:
            shadow = str(page_bg).lower() == palette()['bg'].lower()
        self._shadow = bool(shadow); self._radius = radius if self._shadow else min(radius, 10)
        self._ring = 7 if self._shadow else 2
        self._fill, self._border = fill, border
        super().__init__(parent, bg=fill, highlightthickness=self._ring, highlightbackground=page_bg, highlightcolor=page_bg, bd=0, **kw)
        self._bg = tk.Label(self, bd=0, highlightthickness=0, bg=fill)
        self._bg.place(x=0, y=0, relwidth=1, relheight=1, bordermode='outside')
        self._bg.lower()
        self._size = (0, 0); self._job = None
        self.bind('<Configure>', self._queue, add='+')

    def winfo_children(self):
        return [c for c in super().winfo_children() if c is not getattr(self, '_bg', None)]

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict): kw = {**cnf, **kw}; cnf = None
        changed = False
        for k in ('bg', 'background'):
            if k in kw:
                self._fill = kw[k] = to_hex(self, kw[k]); changed = True
        for k in ('highlightbackground', 'highlightcolor'):
            if k in kw:
                self._border = to_hex(self, kw.pop(k), '#E6EAF1'); changed = True
        kw.pop('highlightthickness', None)
        res = super().configure(**kw) if (kw or cnf) else None
        if changed:
            self._size = (0, 0); self._queue()
        return res
    config = configure

    def _queue(self, e=None):
        if self._job is None:
            self._job = self.after(30, self._render)

    def _render(self):
        self._job = None
        try:
            w, h = self.winfo_width(), self.winfo_height()
            if w < 16 or h < 16: return
            if (w, h) == self._size: return
            self._size = (w, h)
            try: self._bg.configure(bg=self._fill)
            except Exception: pass
            self._photo = card_image(w, h, self._radius, tr(self._fill, 'bg') if str(self._fill).startswith('#') else self._fill, tr(self._border, 'bg') if str(self._border).startswith('#') else self._border,
                                     self._page_bg, self._shadow, palette()['shadow'])
            self._bg.configure(image=self._photo)
        except Exception:      # nunca mostrar erro por causa do desenho do cartão: fica o fundo liso
            pass


# ---------- ícones de traço (desenhados com PIL: iguais no Windows e no Linux, nítidos e coloríveis)
def _draw_icon(name, px, color):
    from PIL import Image, ImageDraw
    S = 8; N = 24 * S
    img = Image.new('RGBA', (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    col = _hex(color) + (255,); w = int(2.0 * S)
    def P(*pts): return [(x * S, y * S) for x, y in pts]
    def line(*pts): d.line(P(*pts), fill=col, width=w, joint='curve'); [d.ellipse((x * S - w / 2, y * S - w / 2, x * S + w / 2, y * S + w / 2), fill=col) for x, y in pts]
    def rrect(x0, y0, x1, y1, r=2): d.rounded_rectangle((x0 * S, y0 * S, x1 * S, y1 * S), radius=r * S, outline=col, width=w)
    def circle(cx, cy, r, fill=False):
        if fill: d.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=col)
        else: d.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), outline=col, width=w)
    def arc(cx, cy, r, a0, a1): d.arc(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), a0, a1, fill=col, width=w)
    n = name
    if n == 'inicio':
        line((3, 11), (12, 3.5), (21, 11)); line((5.5, 9.5), (5.5, 20.5), (18.5, 20.5), (18.5, 9.5)); line((10, 20.5), (10, 14.5), (14, 14.5), (14, 20.5))
    elif n == 'buscar_xml':
        arc(12, 12, 8, 30, 300); line((17.5, 3.5), (18.5, 8.5), (13.5, 8.5))
    elif n == 'nfse':
        rrect(5, 3, 19, 21, 2.5); line((8.5, 8), (15.5, 8)); line((8.5, 12), (15.5, 12)); line((8.5, 16), (12.5, 16))
    elif n == 'documentos':
        rrect(8, 3, 20, 16, 2); line((16, 20), (6, 20), (4, 18), (4, 7))
    elif n == 'empresas':
        rrect(5, 3, 19, 21, 2); line((9, 8), (9, 8)); line((15, 8), (15, 8)); line((9, 12), (9, 12)); line((15, 12), (15, 12)); line((10, 21), (10, 17), (14, 17), (14, 21))
    elif n in ('auditoria', 'buscar'):
        circle(11, 11, 6.5); line((16, 16), (20.5, 20.5))
    elif n == 'pendencias':
        circle(12, 12, 9); line((12, 7), (12, 13)); circle(12, 16.6, 0.9, fill=True)
    elif n == 'historico':
        circle(12, 12, 9); line((12, 7), (12, 12.5), (15.5, 14.5))
    elif n == 'relatorios':
        line((6.5, 20), (6.5, 12)); line((12, 20), (12, 5)); line((17.5, 20), (17.5, 9)); line((3.5, 20.5), (20.5, 20.5))
    elif n == 'usuarios':
        circle(12, 8, 4); arc(12, 21, 8, 190, 350)
    elif n == 'certificado':
        line((12, 3), (19.5, 6), (19.5, 12), (12, 21), (4.5, 12), (4.5, 6), (12, 3)); line((8.5, 12), (11, 14.5), (15.5, 9.5))
    elif n == 'repositorio':
        rrect(3.5, 4, 20.5, 9, 1.5); line((5.5, 9), (5.5, 19.5), (18.5, 19.5), (18.5, 9)); line((10, 13), (14, 13))
    elif n == 'manutencao':
        line((4, 7), (20, 7)); line((4, 12), (20, 12)); line((4, 17), (20, 17)); circle(9, 7, 2.2, fill=True); circle(15, 12, 2.2, fill=True); circle(8, 17, 2.2, fill=True)
    elif n == 'tema_escuro':
        m = Image.new('L', (N, N), 0); md = ImageDraw.Draw(m); md.ellipse((4 * S, 4 * S, 20 * S, 20 * S), fill=255); md.ellipse((10 * S, 0.5 * S, 26 * S, 16.5 * S), fill=0)
        img.paste(Image.new('RGBA', (N, N), col), (0, 0), m)
    elif n == 'tema_claro':
        circle(12, 12, 4.2); [line((12 + 7.4 * __import__('math').cos(a), 12 + 7.4 * __import__('math').sin(a)), (12 + 9.6 * __import__('math').cos(a), 12 + 9.6 * __import__('math').sin(a))) for a in [i * 3.14159265 / 4 for i in range(8)]]
    elif n == 'ajuda':
        circle(12, 12, 9); arc(12, 10, 3, 200, 20); line((12, 13), (12, 14.2)); circle(12, 17, 0.9, fill=True)
    elif n == 'sair':
        line((10, 4), (5, 4), (5, 20), (10, 20)); line((10, 12), (20, 12)); line((16.5, 8.5), (20, 12), (16.5, 15.5))
    elif n == 'sino':
        arc(12, 11, 6, 180, 360); line((6, 11), (6, 16), (4.5, 17.5), (19.5, 17.5), (18, 16), (18, 11)); line((10, 20.5), (14, 20.5))
    elif n == 'check':
        line((5, 12.5), (10, 17.5), (19, 7))
    elif n == 'alerta':
        line((12, 3.5), (21, 19.5), (3, 19.5), (12, 3.5)); line((12, 9.5), (12, 14)); circle(12, 16.8, 0.8, fill=True)
    elif n == 'dinheiro':
        circle(12, 12, 9); line((14.5, 8.5), (10.5, 8.5), (9.5, 10), (9.5, 11), (10.5, 12), (13.5, 12), (14.5, 13), (14.5, 14), (13.5, 15.5), (9.5, 15.5)); line((12, 6.5), (12, 8.5)); line((12, 15.5), (12, 17.5))
    elif n == 'entrada':
        line((12, 4), (12, 16)); line((7, 11), (12, 16), (17, 11)); line((5, 20), (19, 20))
    elif n == 'saida':
        line((12, 20), (12, 8)); line((7, 13), (12, 8), (17, 13)); line((5, 4), (19, 4))
    elif n == 'cancelada':
        circle(12, 12, 9); line((8.5, 8.5), (15.5, 15.5)); line((15.5, 8.5), (8.5, 15.5))
    else:
        circle(12, 12, 3, fill=True)
    return img.resize((px, px), Image.Resampling.LANCZOS)


_ICON_CACHE = {}


def icon(name, size=18, color='#64748B'):
    """Ícone de traço como PhotoImage (guardado em cache; a cor passa pela tradução do tema escuro)."""
    from PIL import ImageTk
    c = tr(color, 'fg') if _MODE == 'escuro' else color
    key = (name, size, c)
    if key not in _ICON_CACHE or not _alive(_ICON_CACHE[key]):
        _ICON_CACHE[key] = ImageTk.PhotoImage(_draw_icon(name, size, c))
    return _ICON_CACHE[key]


def icon_chip(name, size=36, icon_color='#E11D2E', chip_bg='#FFF1F2', page_bg='#FFFFFF'):
    """Ícone dentro de um círculo colorido suave (cartões de indicadores)."""
    from PIL import Image, ImageDraw, ImageTk
    ic = tr(icon_color, 'fg') if _MODE == 'escuro' else icon_color
    cb = tr(chip_bg, 'bg') if _MODE == 'escuro' else chip_bg
    key = ('chip', name, size, ic, cb, page_bg)
    if key in _ICON_CACHE and _alive(_ICON_CACHE[key]): return _ICON_CACHE[key]
    S = 4; base = Image.new('RGBA', (size * S, size * S), (0, 0, 0, 0)); d = ImageDraw.Draw(base)
    d.rounded_rectangle((0, 0, size * S - 1, size * S - 1), radius=int(size * S * 0.32), fill=_hex(cb) + (255,))
    base = base.resize((size, size), Image.Resampling.LANCZOS)
    glyph = _draw_icon(name, int(size * 0.56), ic)
    off = (size - glyph.size[0]) // 2
    base.alpha_composite(glyph, (off, off))
    _ICON_CACHE[key] = ImageTk.PhotoImage(base)
    return _ICON_CACHE[key]


def avatar_image(initials, size=36, bg='#E11D2E', fg='#FFFFFF'):
    """Círculo com as iniciais do usuário."""
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    key = ('avatar', initials, size, bg, fg, _MODE)
    if key in _ICON_CACHE and _alive(_ICON_CACHE[key]): return _ICON_CACHE[key]
    S = 4; im = Image.new('RGBA', (size * S, size * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((0, 0, size * S - 1, size * S - 1), fill=_hex(bg) + (255,))
    font = None
    for name in ('segoeuib.ttf', 'DejaVuSans-Bold.ttf'):
        try: font = ImageFont.truetype(name, int(size * S * 0.4)); break
        except Exception: continue
    font = font or ImageFont.load_default()
    l, t, r, b = d.textbbox((0, 0), initials, font=font)
    d.text(((size * S - (r - l)) / 2 - l, (size * S - (b - t)) / 2 - t), initials, font=font, fill=_hex(fg) + (255,))
    _ICON_CACHE[key] = ImageTk.PhotoImage(im.resize((size, size), Image.Resampling.LANCZOS))
    return _ICON_CACHE[key]


def _round_photo(w, h, r, fill, outline=None, ow=1):
    """Retângulo de cantos arredondados com transparência fora dos cantos (para os elementos de botão e campo do ttk)."""
    from PIL import Image, ImageDraw, ImageTk
    S = 4; im = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=r * S, fill=_hex(outline or fill) + (255,))
    if outline:
        d.rounded_rectangle((ow * S, ow * S, w * S - 1 - ow * S, h * S - 1 - ow * S), radius=max(1, (r - ow)) * S, fill=_hex(fill) + (255,))
    return ImageTk.PhotoImage(im.resize((w, h), Image.Resampling.LANCZOS))


_KEEP_IMAGES = []


def skin_ttk(style):
    """Botões, campos e listas suspensas com cantos arredondados e estados (passar o mouse, foco, desativado)."""
    T = lambda c: tr(c, 'bg')
    keep = _KEEP_IMAGES      # as imagens precisam ficar vivas enquanto a janela existir
    def img(w, h, r, fill, outline=None):
        p = _round_photo(w, h, r, T(fill), T(outline) if outline else None); keep.append(p); return p
    R = 10; B = (R, R, R, R)
    prim = (img(32, 32, R, '#E11D2E'), ('pressed', img(32, 32, R, '#9F1621')), ('active', img(32, 32, R, '#C81A28')), ('disabled', img(32, 32, R, '#E2E8F0')))
    sec = (img(32, 32, R, '#FFFFFF', '#DDE3EC'), ('pressed', img(32, 32, R, '#E8EDF4', '#CBD5E1')), ('active', img(32, 32, R, '#F4F7FB', '#C5CEDB')), ('disabled', img(32, 32, R, '#F8FAFC', '#EDF0F5')))
    fld = (img(32, 32, 9, '#FFFFFF', '#DDE3EC'), ('focus', img(32, 32, 9, '#FFFFFF', '#E11D2E')), ('disabled', img(32, 32, 9, '#F1F5F9', '#E6EAF1')), ('readonly', img(32, 32, 9, '#FFFFFF', '#DDE3EC')))
    style.element_create('Exato.Primary', 'image', *prim, border=B, padding=(0, 0, 0, 0), sticky='nswe')
    style.element_create('Exato.Secondary', 'image', *sec, border=B, padding=(0, 0, 0, 0), sticky='nswe')
    style.element_create('Exato.Field', 'image', *fld, border=(9, 9, 9, 9), padding=(0, 0, 0, 0), sticky='nswe')
    btn_layout = lambda e: [(e, {'sticky': 'nswe', 'children': [('Button.padding', {'sticky': 'nswe', 'children': [('Button.label', {'sticky': 'nswe'})]})]})]
    for name in ('Primary.TButton', 'Blue.TButton', 'CompactPrimary.TButton', 'LoginPrimary.TButton'):
        style.layout(name, btn_layout('Exato.Primary'))
    for name in ('Secondary.TButton', 'CompactSecondary.TButton', 'LoginSecondary.TButton'):
        style.layout(name, btn_layout('Exato.Secondary'))
    style.layout('Secondary.TMenubutton', [('Exato.Secondary', {'sticky': 'nswe', 'children': [('Menubutton.padding', {'expand': '1', 'sticky': 'we', 'children': [('Menubutton.indicator', {'side': 'right', 'sticky': ''}), ('Menubutton.label', {'side': 'left', 'sticky': ''})]})]})])
    style.layout('TEntry', [('Exato.Field', {'sticky': 'nswe', 'children': [('Entry.padding', {'sticky': 'nswe', 'children': [('Entry.textarea', {'sticky': 'nswe'})]})]})])
    style.layout('TCombobox', [('Exato.Field', {'sticky': 'nswe', 'children': [('Combobox.downarrow', {'side': 'right', 'sticky': 'ns'}), ('Combobox.padding', {'expand': '1', 'sticky': 'nswe', 'children': [('Combobox.textarea', {'sticky': 'nswe'})]})]})])


def neutralize_widget_background(style):
    """O ttk pinta (inclui caixas de seleção e botões de opção) o fundo do botão/campo com a cor do estilo antes de desenhar a imagem arredondada: usa um tom quase igual
    ao da página e do cartão (cantos discretos) e tira as trocas de cor de fundo por estado (as imagens já cuidam disso)."""
    neutral = '#FAFBFD'
    for name in ('Primary.TButton', 'Blue.TButton', 'CompactPrimary.TButton', 'LoginPrimary.TButton', 'Secondary.TButton', 'CompactSecondary.TButton', 'LoginSecondary.TButton',
                 'Secondary.TMenubutton', 'TEntry', 'TCombobox', 'TCheckbutton', 'TRadiobutton'):
        try:
            style.configure(name, background=neutral)
            if name.endswith('Button') or name.endswith('Menubutton'):
                style.map(name, background=[])
        except Exception:
            pass


def _short_money(v):
    v = float(v)
    if v >= 1_000_000: return f'R$ {v / 1_000_000:.1f} mi'.replace('.', ',')
    if v >= 1_000: return f'R$ {v / 1_000:.0f} mil'
    return f'R$ {v:.0f}'


def draw_bar_chart(canvas, labels, series, colors, empty_text='Sem movimentação neste período'):
    """Gráfico de barras agrupadas desenhado no Canvas (ajusta à largura; cores passam pelo tema)."""
    canvas.delete('all')
    canvas.update_idletasks()
    W = max(canvas.winfo_width(), 360); H = int(canvas.cget('height'))
    muted = tr('#64748B', 'fg'); grid = '#E6EAF1'
    top, bottom, left, right = 14, 26, 74, 10
    peak = max([max(s) for s in series if s] + [0])          # V184: sem dados a lista vem vazia (erro 'max() iterable' no Início)
    if peak <= 0:
        canvas.create_text(W / 2, H / 2, text=empty_text, fill=muted, font=('Segoe UI', 9)); return
    step = 10 ** (len(str(int(peak))) - 1)
    for cand in (1, 2, 2.5, 5, 10):
        if peak <= cand * step: nice = cand * step; break
    ch = H - top - bottom
    for i in range(4):
        y = top + ch * i / 3
        canvas.create_line(left, y, W - right, y, fill=grid)
        canvas.create_text(left - 8, y, text=_short_money(nice * (3 - i) / 3), anchor='e', fill=muted, font=('Segoe UI', 8))
    n = len(labels); gw = (W - left - right) / n; bw = min(22, gw / (len(series) * 1.7))
    for i, lab in enumerate(labels):
        cx = left + gw * (i + 0.5)
        canvas.create_text(cx, H - 10, text=lab, fill=muted, font=('Segoe UI', 8))
        for j, serie in enumerate(series):
            val = serie[i]
            x0 = cx - bw * len(series) / 2 + j * bw + (1 if j else 0); x1 = x0 + bw - 2
            hgt = ch * (val / nice) if nice else 0
            if hgt > 0:
                canvas.create_rectangle(x0, top + ch - hgt, x1, top + ch, fill=colors[j], outline='')


# ---------- etiquetas de situação em pílula para as tabelas (imagem na primeira coluna do Treeview)
PILL_KINDS = {'ok': ('#15803D', '#DCFCE7'), 'danger': ('#B91C1C', '#FEE2E2'), 'warn': ('#B45309', '#FEF3C7'), 'info': ('#2563EB', '#DBEAFE'), 'muted': ('#475569', '#EEF2F7'), 'busy': ('#0369A1', '#E0F2FE')}


def _pill_pil(text, fg, bg, size=10):
    from PIL import Image, ImageDraw, ImageFont
    S = 3; px = 10 * S; py = 3 * S
    font = None
    for name in ('segoeuib.ttf', 'DejaVuSans-Bold.ttf'):
        try: font = ImageFont.truetype(name, size * S); break
        except Exception: continue
    font = font or ImageFont.load_default()
    probe = ImageDraw.Draw(Image.new('RGBA', (4, 4)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font)
    w = (r - l) + 2 * px; h = (b - t) + 2 * py + 5 * S
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=_hex(bg) + (255,))
    d.text((px - l, (h - (b - t)) // 2 - t), text, font=font, fill=_hex(fg) + (255,))
    return img.resize((max(1, w // S), max(1, h // S)), Image.Resampling.LANCZOS)


def pill_row(items, gap=6):
    """Imagem com uma ou mais etiquetas em pílula lado a lado. items: [(texto, tipo)] com tipo em PILL_KINDS."""
    from PIL import Image, ImageTk
    key = ('pillrow', tuple(items), gap, _MODE)
    cached = _PIL_CACHE.get(key)
    if cached is not None and _alive(cached): return cached
    pills = []
    for text, kind in items:
        fg, bg = PILL_KINDS.get(kind, PILL_KINDS['muted'])
        pills.append(_pill_pil(str(text), tr(fg, 'fg'), tr(bg, 'bg')))
    W = sum(p.size[0] for p in pills) + gap * (len(pills) - 1); H = max(p.size[1] for p in pills)
    out = Image.new('RGBA', (max(W, 1), max(H, 1)), (0, 0, 0, 0)); x = 0
    for p in pills:
        out.alpha_composite(p, (x, (H - p.size[1]) // 2)); x += p.size[0] + gap
    photo = ImageTk.PhotoImage(out)
    if len(_PIL_CACHE) > 400: _PIL_CACHE.clear()
    _PIL_CACHE[key] = photo
    return photo


def _box_photo(kind, checked, hover=False, disabled=False, size=18):
    """Caixa de seleção (quadrado arredondado com ✓) ou botão de opção (círculo) no estilo do Exato."""
    from PIL import Image, ImageDraw, ImageTk
    S = 6; N = size * S; im = Image.new('RGBA', (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    border = tr('#C5CEDB' if not hover else '#94A3B8', 'bg'); fill = tr('#FFFFFF', 'bg'); red = '#E11D2E'
    if disabled: border = tr('#E2E8F0', 'bg'); fill = tr('#F1F5F9', 'bg'); red = '#F4A3AA'
    rad = N // 5 if kind == 'check' else N // 2
    if checked and kind == 'check':
        d.rounded_rectangle((S, S, N - S, N - S), radius=rad, fill=_hex(red) + (255,))
        pts = [(N * 0.27, N * 0.52), (N * 0.44, N * 0.69), (N * 0.74, N * 0.33)]
        d.line(pts, fill=(255, 255, 255, 255), width=int(S * 2.1), joint='curve')
        for x, y in (pts[0], pts[-1]): d.ellipse((x - S, y - S, x + S, y + S), fill=(255, 255, 255, 255))
    elif checked:
        d.ellipse((S, S, N - S, N - S), fill=_hex(fill) + (255,), outline=_hex(red) + (255,), width=int(S * 1.6))
        c = N // 2; r = int(N * 0.2); d.ellipse((c - r, c - r, c + r, c + r), fill=_hex(red) + (255,))
    else:
        if kind == 'check': d.rounded_rectangle((S, S, N - S, N - S), radius=rad, fill=_hex(fill) + (255,), outline=_hex(border) + (255,), width=int(S * 1.4))
        else: d.ellipse((S, S, N - S, N - S), fill=_hex(fill) + (255,), outline=_hex(border) + (255,), width=int(S * 1.4))
    return ImageTk.PhotoImage(im.resize((size, size), Image.Resampling.LANCZOS))


def skin_toggles(style):
    """Caixas de seleção e botões de opção modernos."""
    keep = _KEEP_IMAGES
    for kind, name, element in (('check', 'TCheckbutton', 'Exato.Check'), ('radio', 'TRadiobutton', 'Exato.Radio')):
        off = _box_photo(kind, False); off_h = _box_photo(kind, False, hover=True); off_d = _box_photo(kind, False, disabled=True)
        on = _box_photo(kind, True); on_d = _box_photo(kind, True, disabled=True)
        keep.extend([off, off_h, off_d, on, on_d])
        try: style.element_create(element, 'image', off, ('disabled', 'selected', on_d), ('disabled', off_d), ('selected', on), ('active', off_h), sticky='')
        except tk.TclError: pass      # já criado neste estilo (a imagem nova fica guardada à toa, mas nada quebra)
        base = 'Checkbutton' if kind == 'check' else 'Radiobutton'
        style.layout(name, [(f'{base}.padding', {'sticky': 'nswe', 'children': [(element, {'side': 'left', 'sticky': ''}), (f'{base}.focus', {'side': 'left', 'sticky': 'w', 'children': [(f'{base}.label', {'sticky': 'nswe'})]})]})])


# ---------------------------------------------------------------- rolagem suave (V159)
class WheelRouter:
    """Roda do mouse / touchpad: sempre rola o que está sob o ponteiro.

    - tabelas, listas, textos e áreas rolantes internas rolam primeiro; só depois (e sem "pular") a página;
    - o touchpad do notebook manda passos pequenos: eles são somados em vez de ignorados;
    - a página rola com animação curta; janelas de diálogo nunca rolam a página de trás;
    - listas de seleção (combobox) não trocam o valor ao rolar a página por cima delas.
    """
    INNER = ('Treeview', 'Listbox', 'Text')
    CHAIN_PAUSE = 0.45          # depois de rolar uma tabela até o fim, a página só segue após essa pausa

    def __init__(self, root, page_canvas, after_inner=None):
        self.root, self.page, self.after_inner = root, page_canvas, after_inner
        self._acc = {}; self._target = None; self._job = None; self._inner_at = 0.0
        self._slow = False          # True quando redesenhar a página custa caro: sem animação, vai direto
        for cls in ('Treeview', 'Listbox', 'Text', 'Canvas', 'TCombobox', 'TSpinbox', 'TScale', 'Scale', 'Spinbox'):
            for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                root.bind_class(cls, seq, self.on_wheel)
        for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            root.bind_all(seq, self.on_wheel, add='+')

    @staticmethod
    def _delta(event):
        num = getattr(event, 'num', None)
        if num == 4: return 120
        if num == 5: return -120
        return float(getattr(event, 'delta', 0) or 0)

    def _can(self, w, up):
        """'scroll' se a peça rola nessa direção, 'edge' se rola mas já está no limite, None se não rola."""
        try:
            cls = w.winfo_class()
            if w is self.page: return None
            if cls not in self.INNER and cls != 'Canvas': return None
            first, last = w.yview()
            if first <= 0.0 and last >= 1.0: return None
            if up: return 'scroll' if first > 0.0 else 'edge'
            return 'scroll' if last < 1.0 else 'edge'
        except Exception:
            return None

    def on_wheel(self, event):
        delta = self._delta(event)
        if not delta: return 'break'
        try: w = self.root.winfo_containing(event.x_root, event.y_root)
        except Exception: w = None          # (ex.: lista aberta de um combobox)
        if w is None: w = event.widget
        up = delta > 0
        try: top = w.winfo_toplevel()
        except Exception: return 'break'
        edge_seen = False; cur = w
        while cur is not None:
            state = self._can(cur, up)
            if state == 'scroll':
                acc = self._acc.get(str(cur), 0.0) - delta / 120.0 * 3
                n = int(acc); self._acc[str(cur)] = acc - n
                if n:
                    try: cur.yview_scroll(n, 'units'); cur.update_idletasks()      # desenha já: o Windows deixa "rastro" se o redesenho atrasa
                    except Exception: pass
                    if self.after_inner: self.after_inner(cur)
                self._inner_at = time.monotonic(); return 'break'
            if state == 'edge': edge_seen = True
            if cur is top: break
            try: cur = cur.nametowidget(cur.winfo_parent()) if cur.winfo_parent() else None
            except Exception: cur = None
        if edge_seen and time.monotonic() - self._inner_at < self.CHAIN_PAUSE:
            return 'break'
        if top is not self.root: return 'break'      # diálogo: nunca mexe na página de trás
        self._scroll_page(delta)
        return 'break'

    # --- página (animada)
    def _extent(self):
        try:
            region = [float(v) for v in str(self.page.cget('scrollregion')).split()]
            return max(region[3] - region[1], 1.0), float(max(self.page.winfo_height(), 1))
        except Exception:
            return 1.0, 1.0

    def _scroll_page(self, delta):
        total, view = self._extent()
        if total <= view + 1: return
        top = self.page.yview()[0] * total
        base = self._target if self._target is not None else top
        self._target = min(max(base - delta / 120.0 * 96, 0.0), total - view)
        if self._slow:                # máquina/tela pesada: pula direto (sem animação) e desenha antes do próximo movimento
            self._jump()
        elif self._job is None: self._step()

    def _paint(self):
        """Move e DESENHA já. Sem isso, com a roda girando o Tk só desenha quando para de receber eventos e o Windows deixa
        pedaços antigos da tela (rastro) até o próximo desenho."""
        t0 = time.monotonic()
        self.page.update_idletasks()
        cost = time.monotonic() - t0
        self._slow = cost > 0.045 if not self._slow else cost > 0.02      # volta ao suave quando o desenho ficar leve de novo
        return cost

    def _jump(self):
        total, view = self._extent()
        if self._target is None: return
        self.page.yview_moveto(min(max(self._target, 0.0), max(total - view, 0.0)) / total)
        self._target = None
        self._paint()

    def _step(self):
        self._job = None
        if self._target is None: return
        total, view = self._extent()
        top = self.page.yview()[0] * total
        self._target = min(max(self._target, 0.0), max(total - view, 0.0))
        diff = self._target - top
        if abs(diff) < 1.5:          # o Tk arredonda para pixels inteiros: passos menores que 1 px nunca chegariam
            self.page.yview_moveto(self._target / total); self._target = None; self._paint(); return
        step = diff * 0.32
        if abs(step) < 1.0: step = 1.0 if diff > 0 else -1.0
        self.page.yview_moveto((top + step) / total)
        self._paint()
        if self._slow: self._jump(); return
        try: self._job = self.root.after(16, self._step)
        except Exception: self._job = None

    def stop(self):
        self._target = None
        if self._job is not None:
            try: self.root.after_cancel(self._job)
            except Exception: pass
            self._job = None
