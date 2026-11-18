"""Relatório mensal de NFS-e e Fechamento do mês (NF-e/NFC-e/CT-e) no visual novo. Números: mesmas funções do programa (`exato_nfse_pdf`, `exato_fechamento_pdf`);
aqui só a apresentação. `instalar()` troca as funções antigas pelas novas SÓ dentro do site (o programa instalado continua como está)."""
from decimal import Decimal
from html import escape

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, PageBreak, CondPageBreak, KeepTogether

from . import nucleo, pdf_estilo as E

ZERO = Decimal('0.00')
ST = E.ST


def _p(txt, direita=False, neg=False, cor=None):
    est = ST[('neg' if neg else 'cel') + ('r' if direita else '')]
    return Paragraph(f'<font color="{cor}">{txt}</font>' if cor else txt, est)


def gerar_relatorio_mensal(rows, output_path, company_name='', cnpj='', period_label='Todo o período', logo_path=None, title='Relatório mensal de NFS-e'):
    nf = nucleo.modulo('exato_nfse_pdf'); W = E.LARG; story = []
    secoes = nf.monthly_report_sections(rows); resumo = nf.monthly_summary(rows)
    meta = {'titulo': title, 'logo': logo_path, 'empresa_linha': (company_name or 'Empresa') + f'   •   CNPJ {E.cnpj_fmt(cnpj)}', 'sub': f'Período: {period_label}   •   {len(rows)} nota(s)'}
    tot = {k: ZERO for k in ('pv', 'pi', 'tv', 'ti', 'ri', 'rp', 'rt', 'cv', 'pcv', 'tcv', 'fi')}; tot.update(pq=0, tq=0, cq=0, pcq=0, tcq=0, fq=0)
    for m in resumo:
        for k, k2 in (('pq', 'prest_qtd'), ('pv', 'prest_valor'), ('pi', 'prest_iss'), ('tq', 'tom_qtd'), ('tv', 'tom_valor'), ('ti', 'tom_iss'), ('ri', 'iss_retido'), ('rp', 'prest_iss_retido'), ('rt', 'tom_iss_retido'),
                      ('cq', 'canc_qtd'), ('cv', 'canc_valor'), ('pcq', 'prest_canc_qtd'), ('pcv', 'prest_canc_valor'), ('tcq', 'tom_canc_qtd'), ('tcv', 'tom_canc_valor'), ('fi', 'iss_fora'), ('fq', 'fora_qtd')): tot[k] += m[k2]
    cw = (W - 18) / 4
    story += [E.lado_a_lado(E.Cartao('Serviços prestados', E.dinheiro(tot['pv']), f"{tot['pq']} nota(s) • ISS {E.dinheiro(tot['pi'])}", E.VERDE, cw), E.lado_a_lado(
        E.Cartao('Serviços tomados', E.dinheiro(tot['tv']), f"{tot['tq']} nota(s) • ISS {E.dinheiro(tot['ti'])}", E.VERMELHO, cw), E.lado_a_lado(
        E.Cartao('ISS retido', E.dinheiro(tot['ri']), 'dentro do ISS das autorizadas', E.AZUL, cw), E.Cartao('Canceladas (à parte)', E.dinheiro(tot['cv']), f"{tot['cq']} nota(s) • fora dos valores", E.ALERTA if tot['cq'] else E.MUDO, cw), cw, cw, 6), cw, 2 * cw + 6, 6), cw, 3 * cw + 12, 6), Spacer(1, 5 * mm)]

    cab = ['Mês', 'Prestados (notas)', 'Prestados (valor)', 'ISS prestados', 'ISS retido (prest.)', 'Tomados (notas)', 'Tomados (valor)', 'ISS tomados', 'ISS retido (tom.)', 'ISS pago fora', 'Canceladas (à parte)']
    larg = [28, 21, 28, 22, 22, 21, 28, 22, 22, 24, 31]; linhas = [[Paragraph(x, ST['cab'] if i == 0 else ST['cabr']) for i, x in enumerate(cab)]]
    cz = lambda q, v: Paragraph(f'{q} nota(s)<br/>{E.dinheiro(v)}', ST['celr'])
    for m in resumo:
        linhas.append([_p(escape(nf.month_label(m['mes']).capitalize())), _p(str(m['prest_qtd']), 1), _p(E.dinheiro(m['prest_valor']), 1), _p(E.dinheiro(m['prest_iss']), 1), _p(E.dinheiro(m['prest_iss_retido']), 1), _p(str(m['tom_qtd']), 1), _p(E.dinheiro(m['tom_valor']), 1),
                       _p(E.dinheiro(m['tom_iss']), 1), _p(E.dinheiro(m['tom_iss_retido']), 1), _p(E.dinheiro(m['iss_fora']) if m['fora_qtd'] else '—', 1), cz(m['canc_qtd'], m['canc_valor'])])
    if len(linhas) == 1: linhas.append([_p('Nenhuma NFS-e neste período.')] + [''] * 10)
    linhas.append([_p('Total', neg=True), _p(str(tot['pq']), 1, True), _p(E.dinheiro(tot['pv']), 1, True), _p(E.dinheiro(tot['pi']), 1, True), _p(E.dinheiro(tot['rp']), 1, True), _p(str(tot['tq']), 1, True), _p(E.dinheiro(tot['tv']), 1, True),
                   _p(E.dinheiro(tot['ti']), 1, True), _p(E.dinheiro(tot['rt']), 1, True), _p(E.dinheiro(tot['fi']) if tot['fq'] else '—', 1, True), _p(f"{tot['cq']} nota(s)<br/>{E.dinheiro(tot['cv'])}", 1, True)])
    story += [E.tabela(linhas, larg, E.MARINHO, direita=tuple(range(1, 11)), extra=[('BACKGROUND', (0, -1), (-1, -1), E.hx(E.SUAVE)), ('LINEABOVE', (0, -1), (-1, -1), 0.8, E.hx(E.MARINHO))]), Spacer(1, 2 * mm),
              Paragraph('Notas CANCELADAS ficam à parte: não entram nos valores nem no ISS de prestados e tomados; aparecem nas listas em vermelho. "ISS retido" soma o ISS das notas em que o ISS é retido. "ISS pago fora" soma o ISS das notas autorizadas cujo município de incidência não é o do prestador.', ST['peq'])]

    meses = [m for m in resumo if m['mes'] != 'Sem data'][-12:]
    if len(meses) >= 2:
        cats = [nf.month_label(m['mes'])[:3] + '/' + m['mes'][2:4] for m in meses]
        story += [CondPageBreak(60 * mm), Spacer(1, 4 * mm), E.lado_a_lado(E.barras('Valor por mês: prestados e tomados', cats, [[float(m['prest_valor']) for m in meses], [float(m['tom_valor']) for m in meses]], [E.VERDE, E.VERMELHO], ['Prestados', 'Tomados'], W / 2 - 3, 52),
                                                                          E.barras('ISS por mês: prestados e tomados', cats, [[float(m['prest_iss']) for m in meses], [float(m['tom_iss']) for m in meses]], [E.VERDE, E.VERMELHO], ['Prestados', 'Tomados'], W / 2 - 3, 52), W / 2 - 3, W / 2 - 3)]

    ult = None
    for mes, tipo, itens, t in secoes:
        story.append(PageBreak() if ult is not None and mes != ult else CondPageBreak(60 * mm)); ult = mes
        prest = tipo == 'Prestado'; cor = E.VERDE if prest else E.VERMELHO
        story += [Spacer(1, 3 * mm), E.Faixa(f"{nf.month_label(mes).capitalize()} — serviços {'prestados' if prest else 'tomados'}", f"{'FATURAMENTO' if prest else 'DESPESA'}  •  {len(itens)} nota(s)", cor), Spacer(1, 3 * mm)]
        cw4 = (W - 18) / 4
        story += [E.lado_a_lado(E.Cartao('Autorizadas', E.dinheiro(t['valor']), f"{t['qtd']} nota(s)", cor, cw4, 22), E.lado_a_lado(E.Cartao('ISS', E.dinheiro(t['iss']), ('retido: ' + E.dinheiro(t['iss_retido'])) if t['iss_retido'] else 'sem ISS retido', E.AZUL, cw4, 22), E.lado_a_lado(
            E.Cartao('ISS pago fora', E.dinheiro(t['iss_fora']) if t['fora_qtd'] else '—', f"{t['fora_qtd']} nota(s)" if t['fora_qtd'] else 'nenhuma nota', E.AMBAR if t['fora_qtd'] else E.MUDO, cw4, 22),
            E.Cartao('Canceladas', E.dinheiro(t['canc_valor']), f"{t['canc_qtd']} nota(s) • fora dos valores", E.ALERTA if t['canc_qtd'] else E.MUDO, cw4, 22), cw4, cw4, 6), cw4, 2 * cw4 + 6, 6), cw4, 3 * cw4 + 12, 6), Spacer(1, 4 * mm)]
        tit = ['Nº', 'Emissão', 'Prestador' if not prest else 'Tomador', 'CNPJ / CPF', 'Valor', 'Alíq.', 'ISS', 'ISS retido', 'ISS fora?', 'Município de incidência', 'Situação']
        lw = [12, 22, 52, 36, 24, 14, 22, 14, 14, 32, 27]; direita = (4, 5, 6); linhas = [[Paragraph(x, ST['cabr'] if i in direita else ST['cab']) for i, x in enumerate(tit)]]; extra = []
        for i, r in enumerate(itens, 1):
            ruim = r.get('situacao') == 'Cancelada'
            v = [escape(E.ajustar(r.get('numero') or '', lw[0])), E.data_br(r.get('data')), escape(E.ajustar(r.get('nome') or '—', lw[2])), E.cnpj_fmt(r.get('doc')), E.dinheiro(r.get('valor') or 0), nf._aliq(r.get('aliquota')), E.dinheiro(r.get('iss')),
                 escape(str(r.get('iss_retido') or '—')), escape(str(r.get('iss_fora') or '—')), escape(E.ajustar(r.get('municipio') or '—', lw[9])), E.selo(r.get('situacao') or '')]
            linhas.append([Paragraph(x, ST['celr'] if k in direita else ST['cel']) for k, x in enumerate(v)])
            if ruim: extra.append(('BACKGROUND', (0, i), (-1, i), E.hx(E.ROSA)))
        n = len(itens) + 1
        l = [''] * 11; l[0] = _p('Total do mês (autorizadas)', neg=True); l[4] = _p(E.dinheiro(t['valor']), 1, True); l[6] = _p(E.dinheiro(t['iss']), 1, True); l[10] = _p(f"{t['qtd']} nota(s)", neg=True); linhas.append(l)
        extra += [('BACKGROUND', (0, n), (-1, n), E.hx(E.SUAVE)), ('SPAN', (0, n), (3, n)), ('LINEABOVE', (0, n), (-1, n), 0.8, E.hx(cor))]
        story.append(E.tabela(linhas, lw, cor, direita=direita, extra=extra, tam=8))

    aq = tot['pq'] + tot['tq']; av = tot['pv'] + tot['tv']
    fin = [[Paragraph('Totais do período', ST['cab']), Paragraph('Notas', ST['cabr']), Paragraph('Valor', ST['cabr']), Paragraph('ISS', ST['cabr'])],
           [_p('Serviços prestados — autorizadas'), _p(str(tot['pq']), 1), _p(E.dinheiro(tot['pv']), 1), _p(E.dinheiro(tot['pi']), 1)],
           [_p('Serviços tomados — autorizadas'), _p(str(tot['tq']), 1), _p(E.dinheiro(tot['tv']), 1), _p(E.dinheiro(tot['ti']), 1)],
           [_p('TOTAL AUTORIZADAS', neg=True), _p(str(aq), 1, True), _p(E.dinheiro(av), 1, True), _p(E.dinheiro(tot['pi'] + tot['ti']), 1, True)],
           [_p('Serviços prestados — canceladas'), _p(str(tot['pcq']), 1), _p(E.dinheiro(tot['pcv']), 1), _p('—', 1)],
           [_p('Serviços tomados — canceladas'), _p(str(tot['tcq']), 1), _p(E.dinheiro(tot['tcv']), 1), _p('—', 1)],
           [_p('TOTAL CANCELADAS (não somadas acima)', neg=True), _p(str(tot['cq']), 1, True), _p(E.dinheiro(tot['cv']), 1, True), _p('—', 1, True)],
           [_p('ISS retido (dentro do ISS acima)'), '', '', _p(E.dinheiro(tot['ri']), 1)],
           [_p('ISS pago fora do município do prestador (dentro do ISS acima)'), _p(str(tot['fq']), 1), '', _p(E.dinheiro(tot['fi']), 1)]]
    story += [Spacer(1, 6 * mm), KeepTogether([E.tabela(fin, [110, 25, 50, 45], E.MARINHO, direita=(1, 2, 3), extra=[('BACKGROUND', (0, 3), (-1, 3), E.hx(E.SUAVE)), ('BACKGROUND', (0, 6), (-1, 6), E.hx(E.SUAVE))])])]
    return E.montar(output_path, meta, story, title)


def gerar_fechamento(rows, caminho, empresa='', cnpj='', mes='', logo=None, revisao=0, motivo=''):
    fp = nucleo.modulo('exato_fechamento_pdf'); W = E.LARG; story = []
    titulo = f'Fechamento de {fp._mes_texto(mes)}' + (f' — revisão {revisao}' if revisao else '')
    meta = {'titulo': titulo, 'logo': logo, 'empresa_linha': (empresa or 'Empresa') + f'   •   CNPJ {E.cnpj_fmt(cnpj)}', 'sub': 'Mês encerrado pelo Exato: não chegaram mais notas deste mês nos últimos dias de conferência.' + (f' {motivo}' if motivo else '')}
    res = fp.resumo_separado(rows); tn = sum(x[2] for x in res); tv = sum((x[3] for x in res), ZERO); tc = sum(x[4] for x in res); tcv = sum((x[5] for x in res), ZERO); cw = (W - 12) / 3
    story += [E.lado_a_lado(E.Cartao('Autorizadas', E.dinheiro(tv), f'{tn} nota(s)', E.VERDE, cw), E.lado_a_lado(E.Cartao('Canceladas (à parte)', E.dinheiro(tcv), f'{tc} nota(s) • fora dos valores', E.ALERTA if tc else E.MUDO, cw),
                                                                                                                         E.Cartao('Documentos no mês', str(tn + tc), 'NF-e, NFC-e e CT-e', E.AZUL, cw), cw, cw, 6), cw, 2 * cw + 6, 6), Spacer(1, 5 * mm)]
    cab = ['Tipo', 'Movimentação', 'Autorizadas (notas)', 'Autorizadas (valor)', 'Canceladas (notas)', 'Canceladas (valor)']; linhas = [[Paragraph(x, ST['cab'] if i < 2 else ST['cabr']) for i, x in enumerate(cab)]]
    for fam, d, n, v, c, cv in res: linhas.append([_p(fp.TIPOS.get(fam, str(fam))), _p(escape(str(d))), _p(str(n), 1), _p(E.dinheiro(v), 1), _p(str(c), 1, cor=E.ALERTA if c else None), _p(E.dinheiro(cv), 1, cor=E.ALERTA if c else None)])
    if len(linhas) == 1: linhas.append([_p('Nenhum documento neste mês.')] + [''] * 5)
    linhas.append([_p('Total', neg=True), '', _p(str(tn), 1, True), _p(E.dinheiro(tv), 1, True), _p(str(tc), 1, True), _p(E.dinheiro(tcv), 1, True)])
    story += [E.tabela(linhas, [35, 50, 40, 50, 40, 54], E.MARINHO, direita=(2, 3, 4, 5), extra=[('BACKGROUND', (0, -1), (-1, -1), E.hx(E.SUAVE))]), Spacer(1, 2 * mm),
              Paragraph('Autorizadas e canceladas são somadas separadamente: as canceladas aparecem nas listas (em vermelho), mas não entram no valor das autorizadas. As NFS-e têm o relatório mensal próprio (com alíquota, ISS e ISS fora do município), na mesma pasta.', ST['peq'])]
    listas = {}
    for r in rows:
        if r.get('family') in ('nfe', 'nfce', 'cte'): listas.setdefault((r['family'], r.get('direcao') or '—'), []).append(r)
    for (fam, direc) in sorted(listas, key=lambda k: (fp.ORDEM.index(k[0]), k[1])):
        itens = sorted(listas[(fam, direc)], key=lambda r: (str(r.get('data') or ''), str(r.get('numero') or '').zfill(12)))
        ok = [r for r in itens if r.get('situacao') != 'Cancelada']; ruins = [r for r in itens if r.get('situacao') == 'Cancelada']
        soma = sum((Decimal(str(r.get('valor') or 0)) for r in ok), ZERO); soma_c = sum((Decimal(str(r.get('valor') or 0)) for r in ruins), ZERO)
        cor = E.COR_TIPO[fam]; saida = str(direc).lower().startswith(('sa', 'pre'))
        story += [PageBreak(), Spacer(1, 0), E.Faixa(f'{fp.TIPOS[fam]} — {direc}', f'{len(itens)} documento(s)', cor), Spacer(1, 3 * mm)]
        cw4 = (W - 12) / 2
        story += [E.lado_a_lado(E.Cartao('Autorizadas', E.dinheiro(soma), f'{len(ok)} nota(s)', E.VERDE, cw4, 22), E.Cartao('Canceladas', E.dinheiro(soma_c), f'{len(ruins)} nota(s) • não somadas nas autorizadas', E.ALERTA if ruins else E.MUDO, cw4, 22), cw4, cw4, 6), Spacer(1, 4 * mm)]
        lw = [22, 14, 24, 112, 40, 57]; tit = ['Nº', 'Série', 'Emissão', 'Chave de acesso', 'Valor', 'Situação']; linhas = [[Paragraph(x, ST['cabr'] if i == 4 else ST['cab']) for i, x in enumerate(tit)]]; extra = []
        for i, r in enumerate(itens, 1):
            v = [escape(str(r.get('numero') or '')), escape(str(r.get('serie') or '')), E.data_br(r.get('data')), escape(str(r.get('chave') or '')), E.dinheiro(r.get('valor') or 0), E.selo(r.get('situacao') or '')]
            linhas.append([Paragraph(x, ST['celr'] if k == 4 else ST['cel']) for k, x in enumerate(v)])
            if r.get('situacao') == 'Cancelada': extra.append(('BACKGROUND', (0, i), (-1, i), E.hx(E.ROSA)))
        n = len(itens) + 1
        for rot, val, qt, cc in (('Total autorizadas', soma, len(ok), E.TINTA), ('Total canceladas', soma_c, len(ruins), E.ALERTA)):
            if rot == 'Total canceladas' and not ruins: continue
            l = [''] * 6; l[0] = _p(rot, neg=True, cor=cc); l[4] = _p(E.dinheiro(val), 1, True, cc); l[5] = _p(f'{qt} nota(s)', neg=True, cor=cc); linhas.append(l)
        extra += [('BACKGROUND', (0, n), (-1, -1), E.hx(E.SUAVE)), ('LINEABOVE', (0, n), (-1, n), 0.8, E.hx(cor))] + [('SPAN', (0, k), (3, k)) for k in range(n, len(linhas))]
        story.append(E.tabela(linhas, lw, cor, direita=(4,), extra=extra, tam=7.8))
    return E.montar(caminho, meta, story, titulo)


def instalar():
    """Troca, só no site, o PDF do relatório mensal de NFS-e e o do Fechamento pelos novos. Se algo falhar, ficam os antigos."""
    try:
        nf = nucleo.modulo('exato_nfse_pdf'); fp = nucleo.modulo('exato_fechamento_pdf')
        if not getattr(nf, '_exato_web_novo', False): nf._original_monthly = nf.generate_monthly_report_pdf; nf.generate_monthly_report_pdf = gerar_relatorio_mensal; nf._exato_web_novo = True
        if not getattr(fp, '_exato_web_novo', False): fp._original_fechamento = fp.gerar_fechamento_pdf; fp.gerar_fechamento_pdf = gerar_fechamento; fp._exato_web_novo = True
    except Exception: pass
