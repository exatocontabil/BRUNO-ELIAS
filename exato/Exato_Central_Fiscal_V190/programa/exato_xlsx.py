"""Gravação simples de planilhas .xlsx (sem componentes externos): títulos em destaque, colunas largas, valores em moeda.

Uso: write_xlsx(caminho, [{'name': 'Notas', 'columns': [{'title': 'Nº', 'width': 10, 'type': 'text'}, ...], 'rows': [[...], ...]}])
Tipos de coluna: text, int, money, date (texto dd/mm/aaaa).
"""
import re
import zipfile
from decimal import Decimal
from xml.sax.saxutils import escape


def _col(n):
    s = ''
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _clean(text):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(text))


def write_xlsx(path, sheets):
    names = []
    for sh in sheets:
        base = re.sub(r'[\\/*?:\[\]]', ' ', sh['name'])[:31] or 'Planilha'
        name, k = base, 2
        while name in names:
            name = f'{base[:28]} {k}'; k += 1
        names.append(name)
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00"/></numFmts>
<fonts count="2"><font><sz val="10"/><name val="Calibri"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0F172A"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                    + ''.join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(len(sheets))) + '</Types>')
        zf.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        zf.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                    + ''.join(f'<sheet name="{escape(n)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, n in enumerate(names)) + '</sheets></workbook>')
        zf.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + ''.join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(sheets)))
                    + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        zf.writestr('xl/styles.xml', styles)
        for i, sh in enumerate(sheets):
            cols = sh['columns']
            xml = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                   '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>']
            xml += [f'<col min="{j + 1}" max="{j + 1}" width="{c.get("width", 14)}" customWidth="1"/>' for j, c in enumerate(cols)]
            xml.append('</cols><sheetData>')
            xml.append('<row r="1">' + ''.join(f'<c r="{_col(j)}1" s="1" t="inlineStr"><is><t>{escape(_clean(c["title"]))}</t></is></c>' for j, c in enumerate(cols)) + '</row>')
            for r, row in enumerate(sh['rows'], 2):
                cells = []
                for j, (c, v) in enumerate(zip(cols, row)):
                    ref = f'{_col(j)}{r}'
                    kind = c.get('type', 'text')
                    if v is None or v == '':
                        continue
                    if kind in ('money', 'int'):
                        try:
                            num = Decimal(str(v)); cells.append(f'<c r="{ref}" s="{2 if kind == "money" else 3}"><v>{num}</v></c>'); continue
                        except Exception:
                            pass
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(_clean(v))}</t></is></c>')
                xml.append(f'<row r="{r}">' + ''.join(cells) + '</row>')
            xml.append(f'</sheetData><autoFilter ref="A1:{_col(len(cols) - 1)}{max(len(sh["rows"]) + 1, 1)}"/></worksheet>')
            zf.writestr(f'xl/worksheets/sheet{i + 1}.xml', ''.join(xml))
    return str(path)
