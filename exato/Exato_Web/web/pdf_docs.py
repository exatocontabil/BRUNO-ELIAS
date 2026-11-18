"""Relatório de documentos fiscais no visual novo. Os NÚMEROS vêm das mesmas funções do programa (`exato_relatorio_docs_pdf`: seções, análise, lacunas de numeração);
aqui só muda a apresentação (capa, cartões, rosca, barras, tabelas). Mesma assinatura de `gerar` do módulo antigo."""
from decimal import Decimal
from html import escape

from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, CondPageBreak, KeepTogether

from . import nucleo, pdf_estilo as E

ZERO = Decimal('0.00')
ST = E.ST


def gerar(linhas, caminho, empresa='', cnpj='', periodo='Todo o período', filtros=None, logo=None, progresso=None):
    rp = nucleo.modulo('exato_relatorio_docs_pdf'); numeracao = nucleo.modulo('exato_numeracao')
    W = E.LARG; story = []; por = rp.secoes(linhas); ordem = rp.ordem_secoes(por); ana = rp.analise(linhas)
    varias = len({r.get('cnpj') for r in linhas if r.get('cnpj')}) > 1
    meta = {'titulo': 'Relatório de documentos fiscais', 'logo': logo,
            'empresa_linha': (empresa or 'Várias empresas') + (f'   •   CNPJ {E.cnpj_fmt(cnpj)}' if cnpj else ''),
            'sub': f'Período: {periodo}   •   {len(linhas):,} documento(s)'.replace(',', '.') + (('   •   ' + '  /  '.join(filtros)) if filtros else '')}

    # ---------------------------------------------------------------- resumo
    res = ana['resultado']
    cw = (W - 12) / 3
    story += [E.lado_a_lado(E.Cartao('Faturamento', E.dinheiro(ana['faturamento']), 'NF-e e NFC-e saída • NFS-e e CT-e prestados', E.VERDE, cw), E.lado_a_lado(
        E.Cartao('Despesa', E.dinheiro(ana['despesa']), 'NF-e e NFC-e entrada • NFS-e e CT-e tomados', E.VERMELHO, cw), E.Cartao('Faturamento – despesa', E.dinheiro(res), 'análise do período (não é total de documentos)', E.AZUL if res >= 0 else E.ALERTA, cw), cw, cw, 6), cw, 2 * cw + 6, 6), Spacer(1, 6 * mm)]

    def quadro(titulo, cor, saida):
        t = [[Paragraph(titulo, ST['cab']), Paragraph('Notas', ST['cabr']), Paragraph('Valor (autorizadas)', ST['cabr']), Paragraph('Canceladas', ST['cabr'])]]; tn = 0; tv = ZERO
        for fam, s in ordem:
            if s != saida: continue
            g = por[(fam, s)]
            t.append([Paragraph(f'<font color="{E.COR_TIPO[fam]}"><b>•</b></font> {escape(rp.rotulo_secao(fam, s))}', ST['cel']), Paragraph(str(g['an']), ST['celr']), Paragraph(E.dinheiro(g['av']), ST['celr']),
                      Paragraph(f'<font color="{E.ALERTA}">{g["cn"]} • {E.dinheiro(g["cv"])}</font>' if g['cn'] else '—', ST['celr'])])
            tn += g['an']; tv += g['av']
        if len(t) == 1: t.append([Paragraph('Nenhum documento.', ST['cel']), '', '', ''])
        t.append([Paragraph('Total do lado', ST['neg']), Paragraph(str(tn), ST['negr']), Paragraph(E.dinheiro(tv), ST['negr']), ''])
        return E.tabela(t, [52, 16, 34, 29.5], cor, direita=(1, 2, 3), extra=[('BACKGROUND', (0, -1), (-1, -1), E.hx(E.SUAVE))])
    story += [E.lado_a_lado(quadro('FATURAMENTO  (saídas / prestados)', E.VERDE, True), quadro('DESPESA  (entradas / tomados)', E.VERMELHO, False), W / 2 - 3, W / 2 - 3), Spacer(1, 3 * mm),
              Paragraph('Os valores são das notas AUTORIZADAS; as canceladas aparecem à parte e nunca entram nos valores. Faturamento e despesa nunca são somados entre si. Cada tipo de documento tem uma seção para cada lado, a partir da próxima página.', ST['peq'])]
    exp_total = sum(g['exp_canc'] for g in por.values())
    if exp_total: story += [Spacer(1, 2 * mm), Paragraph(f'<font color="{E.ALERTA}"><b>Atenção:</b> {exp_total} nota(s) cancelada(s) já foram exportadas. Confira na Domínio.</font>', ST['corpo'])]

    # ---------------------------------------------------------------- análise
    meses = ana['meses']; chaves = sorted(meses)[-12:]
    if chaves and (ana['faturamento'] > 0 or ana['despesa'] > 0):
        story += [PageBreak(), Paragraph('Faturamento x despesa', ST['h2']), Spacer(1, 2 * mm)]
        cats = [E.mes_curto(m) for m in chaves]; fat_m = [float(meses[m]['fat']) for m in chaves]; des_m = [float(meses[m]['desp']) for m in chaves]
        story += [E.lado_a_lado(E.barras('Faturamento e despesa por mês', cats, [fat_m, des_m], [E.VERDE, E.VERMELHO], ['Faturamento', 'Despesa'], W / 2 - 3, 52),
                                E.barras('Resultado do mês (faturamento – despesa)', cats, [[a - b for a, b in zip(fat_m, des_m)]], [E.AZUL], ['Resultado'], W / 2 - 3, 52), W / 2 - 3, W / 2 - 3), Spacer(1, 2 * mm)]
        def partes(d): return [(rp.TIPOS[f], d[f], E.COR_TIPO[f]) for f in rp.ORDEM if f in d and d[f] > 0]
        story += [E.lado_a_lado(E.rosca('De onde vem o FATURAMENTO', partes(ana['tipo_fat']), 'faturamento', W / 2 - 3, 44), E.rosca('Para onde vai a DESPESA', partes(ana['tipo_desp']), 'despesa', W / 2 - 3, 44), W / 2 - 3, W / 2 - 3), Spacer(1, 4 * mm)]
        md = [[Paragraph(x, ST['cabr'] if i else ST['cab']) for i, x in enumerate(('Mês', 'Faturamento', 'Despesa', 'Faturamento – despesa', 'Despesa / faturamento'))]]
        for m in sorted(meses):
            f_, d_ = meses[m]['fat'], meses[m]['desp']
            md.append([Paragraph(E.mes_curto(m), ST['cel']), Paragraph(E.dinheiro(f_), ST['celr']), Paragraph(E.dinheiro(d_), ST['celr']), Paragraph(f'<font color="{E.ALERTA if f_ - d_ < 0 else E.TINTA}">{E.dinheiro(f_ - d_)}</font>', ST['celr']),
                       Paragraph((f'{d_ / f_ * 100:.0f}%' if f_ else '—'), ST['celr'])])
        story.append(KeepTogether([E.tabela(md, [40, 55, 55, 60, 59], E.MARINHO, direita=(1, 2, 3, 4))]))
        def top(titulo, lista, cor):
            t = [[Paragraph(titulo, ST['cab']), Paragraph('Valor', ST['cabr'])]]
            for n, v in lista: t.append([Paragraph(escape(E.ajustar(n, 92, 'Helvetica', 8.2)), ST['cel']), Paragraph(E.dinheiro(v), ST['celr'])])
            if len(t) == 1: t.append([Paragraph('—', ST['cel']), ''])
            return E.tabela(t, [92, 39.5], cor, direita=(1,))
        if ana['clientes'] or ana['fornecedores']:
            story += [CondPageBreak(36 * mm), Spacer(1, 5 * mm), E.lado_a_lado(top('Maiores CLIENTES (faturamento)', ana['clientes'], E.VERDE), top('Maiores FORNECEDORES (despesa)', ana['fornecedores'], E.VERMELHO), W / 2 - 3, W / 2 - 3)]

    # ---------------------------------------------------------------- uma seção por tipo e lado
    feitos = 0
    for fam, saida in ordem:
        g = por[(fam, saida)]; itens = g['itens']; fat = rp.lado_da(fam, saida) == 'faturamento'; cor = E.COR_TIPO[fam]; rotulo = rp.rotulo_secao(fam, saida)
        story += [PageBreak() if itens else CondPageBreak(45 * mm), Spacer(1, 0 if itens else 4 * mm), E.Faixa(rotulo, f"{'FATURAMENTO' if fat else 'DESPESA'}  •  {len(itens)} documento(s)", cor), Spacer(1, 3 * mm)]
        if not itens: story.append(Paragraph('Nenhum documento deste tipo e movimentação neste filtro.', ST['corpo'])); continue
        itens = sorted(itens, key=lambda r: (str(r.get('data') or ''), str(r.get('numero') or '').zfill(12)))
        aut = [r for r in itens if rp._autorizada(r)]; can = [r for r in itens if rp._cancelada(r)]; va = g['av']; vc = g['cv']; cw4 = (W - 18) / 4
        story += [E.lado_a_lado(E.Cartao('Autorizadas (notas)', str(len(aut)), 'entram nos valores', E.VERDE, cw4, 24), E.lado_a_lado(E.Cartao('Autorizadas (valor)', E.dinheiro(va), 'soma das autorizadas', E.VERDE, cw4, 24),
                  E.lado_a_lado(E.Cartao('Canceladas (notas)', str(len(can)), 'ficam fora dos valores', E.ALERTA if can else E.MUDO, cw4, 24), E.Cartao('Canceladas (valor)', E.dinheiro(vc), 'só para conferência', E.ALERTA if can else E.MUDO, cw4, 24), cw4, cw4, 6), cw4, 2 * cw4 + 6, 6), cw4, 3 * cw4 + 12, 6)]
        exp_c = [r for r in can if r.get('exportada')]
        if exp_c: story += [Spacer(1, 2 * mm), Paragraph(f'<font color="{E.ALERTA}"><b>{len(exp_c)} nota(s) cancelada(s) já exportada(s):</b> confira na Domínio.</font>', ST['corpo'])]
        if fam == 'nfse':
            fora = [r for r in aut if r.get('iss_fora') == 'SIM']; iss_a = sum((rp._dec(r.get('iss')) for r in aut), ZERO); iss_f = sum((rp._dec(r.get('iss')) for r in fora), ZERO); iss_r = sum((rp._dec(r.get('iss')) for r in aut if r.get('iss_retido') == 'Sim'), ZERO)
            story += [Spacer(1, 2 * mm), Paragraph(f'ISS das autorizadas: <b>{E.dinheiro(iss_a)}</b>  •  ISS retido: <b>{E.dinheiro(iss_r)}</b>  •  ISS pago fora do município do prestador: <b>{E.dinheiro(iss_f)}</b> ({len(fora)} nota(s))', ST['corpo'])]
        if fam in ('nfe', 'nfce') and saida:
            for serie, faixas in numeracao.lacunas(itens).items():
                story += [Spacer(1, 2 * mm), Paragraph(f'<font color="{E.ALERTA}"><b>Numeração faltando</b></font> (série {escape(serie)}, {numeracao.total_faltando(faixas)} número(s)): {escape(numeracao.texto_faixas(faixas, 30))}. Se o número foi inutilizado na SEFAZ, é normal faltar.', ST['corpo'])]
        story.append(Spacer(1, 4 * mm))
        if fam == 'nfse':
            tit = ['Nº', 'Emissão', 'Outra parte', 'CNPJ / CPF', 'Valor', 'Alíq.', 'ISS', 'Retido', 'ISS fora?', 'Município', 'Situação', 'Exp.']; larg = [15, 18, 60, 31, 22, 12, 19, 15, 14, 31, 20, 12]; direita = (4, 5, 6); vi = 4; i_parte = 2; i_mun = 9
        elif fam == 'nfe' and not saida:
            tit = ['Nº', 'Série', 'Emissão', 'Outra parte', 'Chave de acesso', 'Valor', 'Optante pelo Simples Nacional?', 'Permite aproveitamento?', 'Situação', 'Exp.']; larg = [14, 12, 18, 46, 66, 24, 22, 38, 18, 11]; direita = (5,); vi = 5; i_parte = 3; i_mun = None
            cred_ok = [r for r in aut if r.get('credito') == 'Sim']; cred_total = sum((rp._dec(r.get('cred_valor')) for r in cred_ok), ZERO)
            story += [Paragraph(f'Fornecedores do Simples Nacional que permitem o aproveitamento do crédito de ICMS: <b>{len(cred_ok)}</b> nota(s) autorizada(s)' + (f', crédito informado de <b>{E.dinheiro(cred_total)}</b>' if cred_total > 0 else '')
                                + '. Quem não é optante do Simples só pode aproveitar esse crédito quando o fornecedor o informa na nota (CSOSN 101 ou 201 e a frase nas informações complementares). "—" = a nota não traz a informação.', ST['corpo']), Spacer(1, 2 * mm)]
        else:
            tit = ['Nº', 'Série', 'Emissão', 'Outra parte', 'Chave de acesso', 'Valor', 'Situação', 'Exp.']; larg = [16, 12, 19, 80, 83, 27, 20, 12]; direita = (5,); vi = 5; i_parte = 3; i_mun = None
        if varias: tit[i_parte] = 'Empresa / outra parte'
        corpo_t = [[Paragraph(x, ST['cabr'] if i in direita else ST['cab']) for i, x in enumerate(tit)]]; extra = []; i_sit = tit.index('Situação')
        for i, r in enumerate(itens, 1):
            parte = E.ajustar(((r['empresa'] + ' / ') if varias else '') + (r.get('parte') or '—'), larg[i_parte]); exp = 'Sim' if r.get('exportada') else '—'
            if fam == 'nfse':
                lin = [E.ajustar(r['numero'], larg[0]), E.data_br(r['data']), parte, E.cnpj_fmt(r.get('doc')), E.dinheiro(r['valor']), (f"{rp._dec(r['aliquota']):.2f}".replace('.', ',') + '%') if r.get('aliquota') not in (None, '') else '—',
                       E.dinheiro(r['iss']) if r.get('iss') not in (None, '') else '—', r.get('iss_retido') or '—', r.get('iss_fora') or '—', E.ajustar(r.get('municipio') or '—', larg[i_mun]), r['situacao'], exp]
            elif fam == 'nfe' and not saida:
                cred = r.get('credito') or '—'
                if cred == 'Sim': cred = 'Sim' + (f" • {E.dinheiro(r['cred_valor'])}" if r.get('cred_valor') else '') + ((f" • {rp._dec(r['cred_aliq']):.2f}".replace('.', ',') + '%') if r.get('cred_aliq') else '')
                lin = [E.ajustar(r['numero'], larg[0]), r['serie'] or '—', E.data_br(r['data']), parte, r['chave'] or '—', E.dinheiro(r['valor']), r.get('optante') or '—', E.ajustar(cred, larg[7]), r['situacao'], exp]
            else:
                lin = [E.ajustar(r['numero'], larg[0]), r['serie'] or '—', E.data_br(r['data']), parte, r['chave'] or '—', E.dinheiro(r['valor']), r['situacao'], exp]
            lin = [Paragraph(E.selo(x) if k == i_sit else escape(str(x)), ST['celr'] if k in direita else ST['cel']) for k, x in enumerate(lin)]
            corpo_t.append(lin)
            if rp._cancelada(r) and r.get('exportada'): extra.append(('BACKGROUND', (0, i), (-1, i), E.hx(E.ROSA)))
            feitos += 1
            if progresso and feitos % 500 == 0:
                try: progresso(feitos, len(linhas))
                except Exception: pass
        n = len(itens) + 1
        for rot, val, cor_t in (('Total das autorizadas', va, E.TINTA), ('Total das canceladas', vc, E.ALERTA)):
            l = [''] * len(tit); l[0] = Paragraph(f'<font color="{cor_t}"><b>{rot}</b></font>', ST['neg']); l[vi] = Paragraph(f'<font color="{cor_t}"><b>{E.dinheiro(val)}</b></font>', ST['negr']); corpo_t.append(l)
        extra += [('BACKGROUND', (0, n), (-1, n + 1), E.hx(E.SUAVE)), ('SPAN', (0, n), (vi - 1, n)), ('SPAN', (0, n + 1), (vi - 1, n + 1)), ('LINEABOVE', (0, n), (-1, n), 0.8, E.hx(cor))]
        story.append(E.tabela(corpo_t, larg, cor, direita=direita, extra=extra, tam=7.8))
    if not linhas: story += [PageBreak(), Paragraph('Nenhum documento neste filtro.', ST['h2'])]
    return E.montar(caminho, meta, story, 'Relatório de documentos fiscais')
