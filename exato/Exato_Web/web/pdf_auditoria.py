"""PDF da Auditoria fiscal (SAT x XML) no visual novo. Todos os dados vêm do que o programa já calculou (`_audit_display_rows`, `analyze_audit_result`...);
aqui só a apresentação: capa, cartões, faixa de situação, análise do Exatinho e a tabela de documentos (uma seção por tipo quando é NF-e + NFC-e)."""
from datetime import datetime
from decimal import Decimal
from html import escape

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, PageBreak, Image, Table, TableStyle

from . import pdf_estilo as E

ST = E.ST
SITUACAO = {'conforme': ('CONFORME', E.VERDE, 'Todos os documentos do período foram conciliados com sucesso.'),
            'atencao': ('ATENÇÃO', E.AMBAR, 'Alguns documentos ainda precisam de conferência.'),
            'divergencia': ('DIVERGÊNCIA', E.ALERTA, 'Há diferenças nos dados conferidos.')}


def _estilo_status():
    from reportlab.lib.styles import ParagraphStyle
    return ParagraphStyle('aud_s', parent=ST['corpo'], fontName='Helvetica-Bold', fontSize=15, leading=19)


def _faixa_status(cor, rotulo, frase, w):
    t = Table([[[Paragraph(f'<font color="{cor}"><b>SITUAÇÃO DA AUDITORIA</b></font>', ST['peq']), Paragraph(f'<font size="15" color="{cor}"><b>{rotulo}</b></font>', _estilo_status())], Paragraph(escape(frase), ST['corpo'])]], colWidths=[70 * mm, (w - 70) * mm])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), E.hx(E.FUNDO)), ('LINEBEFORE', (0, 0), (0, -1), 3.4, E.hx(cor)), ('BOX', (0, 0), (-1, -1), 0.6, E.hx(E.LINHA)), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0, 0), (-1, -1), 10), ('ROUNDEDCORNERS', [5, 5, 5, 5])])); return t


def _analise(core, ai, w):
    """Quadro "Análise do Exatinho": título, mensagem e frase de destaque, com o mascote ao lado."""
    corpo = [Paragraph('<font color="#16A34A"><b>EXATO IA</b></font> <font color="#64748B"><b>• ANÁLISE</b></font>', ST['peq']),
             Paragraph(f"<b>{escape(str(ai.get('title') or 'Conferência concluída.'))}</b>", ParagraphStyle_titulo()), Paragraph(escape(str(ai.get('message') or '')), ST['corpo'])]
    if ai.get('callout'): corpo.append(Paragraph('“' + escape(str(ai['callout'])) + '”', ST['mudo']))
    mascote = None
    try:
        from pathlib import Path
        for cand in (Path(core.MASCOT_ASSET_DIR) / 'exato_ia_transparente.png', Path(core.MASCOT_EXATO_IA_PATH)):
            if cand.exists(): mascote = Image(str(cand), mask='auto'); mascote._restrictSize(30 * mm, 34 * mm); break
    except Exception: mascote = None
    t = Table([[mascote or '', corpo]], colWidths=[38 * mm, (w - 38) * mm])
    t.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, E.hx(E.LINHA)), ('BACKGROUND', (0, 0), (-1, -1), E.hx('#FFFFFF')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                           ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('ROUNDEDCORNERS', [5, 5, 5, 5])])); return t


def ParagraphStyle_titulo():
    from reportlab.lib.styles import ParagraphStyle
    return ParagraphStyle('aud_t', parent=ST['corpo'], fontName='Helvetica-Bold', fontSize=13, leading=17, spaceBefore=2, spaceAfter=3)


def _tabela(core, linhas, modelo, cor):
    larg = [30, 20, 24, 18, 26, 32, 32, 87]; tit = ['Situação', 'Nº nota', 'Data', 'Modelo', 'Documento', 'Valor SAT', 'Valor XML', 'Observação']
    t = [[Paragraph(x, ST['cabr'] if i in (5, 6) else ST['cab']) for i, x in enumerate(tit)]]; extra = []
    for i, r in enumerate(linhas, 1):
        st = core._audit_status_label_for_row(r); cor_st = {'Conforme': E.VERDE, 'Divergência': E.AMBAR, 'Cancelada': E.MUDO}.get(st, E.ALERTA)
        obs = 'Dados conferem.' if st == 'Conforme' else str(r.get('observacao') or '')
        v = [f'<font color="{cor_st}"><b>•</b> <b>{escape(st)}</b></font>', escape(str(r.get('numero') or '—')), E.data_br(r.get('data') or r.get('issued_at') or ''), escape(str(r.get('modelo') or modelo or '—')),
             escape(str(r.get('situacao_doc') or 'Autorizada')), '—' if r.get('valor_sat') is None else E.dinheiro(core._audit_clean_decimal(r.get('valor_sat'))), '—' if r.get('valor_xml') is None else E.dinheiro(core._audit_clean_decimal(r.get('valor_xml'))),
             escape(E.ajustar(obs, larg[7], 'Helvetica', 7.8))]
        t.append([Paragraph(x, ST['celr'] if k in (5, 6) else ST['cel']) for k, x in enumerate(v)])
        if st == 'Sem correspondência': extra.append(('BACKGROUND', (0, i), (-1, i), E.hx('#FFF1F2')))
        elif st == 'Divergência': extra.append(('BACKGROUND', (0, i), (-1, i), E.hx('#FFFBEB')))
    return E.tabela(t, larg, cor, direita=(5, 6), extra=extra, tam=7.8)


def gerar(core, resultado, caminho, empresa='', cnpj='', ini='', fim='', arquivos=None):
    """Gera o PDF da auditoria (um tipo, ou NF-e + NFC-e separados). `core` = o núcleo do programa. Devolve o caminho."""
    W = E.LARG; res = resultado or {}; fam = str(res.get('family') or '').casefold()
    multi = fam == 'multi'; tipos = [f for f in ('nfe', 'nfce') if f in set(res.get('selected_families') or [])] if multi else [fam]
    ini = ini or res.get('period_start', ''); fim = fim or res.get('period_end', ''); empresa = str(empresa or 'Empresa não identificada')
    ai = res.get('ai_analysis') or core.analyze_audit_result(res, empresa, ini, fim)
    rot, cor, frase = SITUACAO.get(str(ai.get('status') or 'atencao'), SITUACAO['atencao'])
    linhas = core._audit_display_rows(res)
    total = lambda s: sum(1 for r in linhas if core._audit_status_label_for_row(r) == s)
    rotulo_tipo = lambda f: core.AUDIT_FAMILY_LABELS.get(f) or core.SUPPORTED_FAMILIES.get(f, f)
    nome_tipo = ' + '.join(rotulo_tipo(f) for f in tipos) if multi else str(res.get('family_label') or core.SUPPORTED_FAMILIES.get(fam, 'Documentos fiscais'))
    periodo = f'{core._format_user_date(ini)} a {core._format_user_date(fim)}' if ini and fim else 'Período não informado'
    meta = {'titulo': 'Auditoria fiscal', 'logo': core.LOGO_PATH if getattr(core, 'LOGO_PATH', None) and core.LOGO_PATH.exists() else None, 'empresa_linha': empresa + f'   •   CNPJ {E.cnpj_fmt(cnpj)}',
            'sub': f'Conciliação {nome_tipo} × XML   •   Período auditado: {periodo}'}
    cw = (W - 18) / 4; story = []
    story += [E.lado_a_lado(E.Cartao('Documentos conciliados', str(total('Conforme')), 'SAT e XML conferem', E.VERDE, cw), E.lado_a_lado(E.Cartao('Sem correspondência', str(total('Sem correspondência')), 'só em um dos lados', E.VERDE if not total('Sem correspondência') else E.AMBAR, cw),
              E.lado_a_lado(E.Cartao('Divergências de dados', str(total('Divergência')), 'valor, data ou número', E.VERDE if not total('Divergência') else E.ALERTA, cw), E.Cartao('Valor conciliado', E.dinheiro(core._audit_clean_decimal(res.get('matched_sat_total') or 0)), 'soma dos conciliados', E.AZUL, cw), cw, cw, 6), cw, 2 * cw + 6, 6), cw, 3 * cw + 12, 6),
              Spacer(1, 4 * mm), _faixa_status(cor, rot, frase, W), Spacer(1, 4 * mm), _analise(core, ai, W)]
    if multi:
        subs = res.get('subaudits') or {}; story += [Spacer(1, 5 * mm), Paragraph('Conciliação por tipo documental', ST['h2'])]; cartas = []
        for f in tipos:
            s = subs.get(f, {}) or {}; r = s.get('result') or {}; falta = len(r.get('sat_only') or []) + len(r.get('xml_only') or [])
            dif = abs(core._audit_clean_decimal(r.get('sat_total')) - core._audit_clean_decimal(r.get('xml_total')))
            duros = len(r.get('number_differences') or []) + len(r.get('date_differences') or []) + len(r.get('value_differences') or [])
            c = E.ALERTA if duros else (E.AMBAR if falta else E.VERDE)
            cartas.append(E.Cartao(f"{rotulo_tipo(f)} • Modelo {core.AUDIT_FAMILY_MODELS.get(f, '')}", f"SAT {s.get('sat_count') or 0}  •  XML {s.get('xml_count') or 0}", f"{falta} sem correspondência • diferença {E.dinheiro(dif)}", c, (W - 6) / 2, 24))
        if len(cartas) == 2: story.append(E.lado_a_lado(cartas[0], cartas[1], (W - 6) / 2, (W - 6) / 2, 6))
        elif cartas: story.append(cartas[0])
        story.append(Spacer(1, 2 * mm)); story.append(Paragraph('NF-e e NFC-e são conciliadas separadamente; os detalhes de cada modelo estão nas páginas seguintes.', ST['peq']))
        for f in tipos:
            sub = (subs.get(f, {}) or {}).get('result')
            if not sub: continue
            lin = core._audit_display_rows(sub)
            story += [PageBreak(), E.Faixa(f"{rotulo_tipo(f)} • Modelo {core.AUDIT_FAMILY_MODELS.get(f, '')}", f'{len(lin)} documento(s) analisados', E.COR_TIPO.get(f, E.MARINHO)), Spacer(1, 4 * mm), _tabela(core, lin, core.AUDIT_FAMILY_MODELS.get(f, ''), E.COR_TIPO.get(f, E.MARINHO))]
    else:
        story += [PageBreak(), E.Faixa('Documentos analisados', f'{len(linhas)} documento(s)  •  ordem: emissão e número crescentes', E.COR_TIPO.get(fam, E.MARINHO)), Spacer(1, 4 * mm), _tabela(core, linhas, core.AUDIT_FAMILY_MODELS.get(fam, ''), E.COR_TIPO.get(fam, E.MARINHO))]
    if arquivos: story += [Spacer(1, 4 * mm), Paragraph('Arquivos do SAT usados: ' + escape(', '.join(str(a) for a in arquivos)), ST['peq'])]
    return E.montar(caminho, meta, story, 'Auditoria fiscal')
