"""Exatinho do Exato Web: assistente local em português. Sem Tkinter, sem tela, sem inteligência artificial externa.

Responde perguntas sobre a situação da busca (quais empresas ainda não buscaram notas, por quê e de quais tipos), certificados, contagens, pendências do dia e
tira dúvidas de uso do sistema (base de conhecimento em `exatinho_base`). Nunca inventa: pergunta sem resposta vira "ainda não sei" e fica anotada para ser
ensinada. Ações (buscar) só são devolvidas como pedido de CONFIRMAÇÃO; quem executa é a tela, depois do "sim" da pessoa.

O módulo recebe `dados`, um dicionário de funções (empresas, linhas da situação da busca, certificados, contagens...), e devolve dicionários simples:
  {'text', 'passos': [...], 'lines': [...], 'cards': [...], 'actions': [...], 'confirm': {...}|None, 'mood', 'topic', 'ctx', 'sugestoes': [...]}"""
import difflib
import re
import unicodedata
from datetime import date, timedelta

from . import nucleo
from .exatinho_base import EXEMPLOS, TOPICOS

ROTULO = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}
TELAS = {'situacao': ('/situacao', 'Situação da busca', ('situacao da busca', 'situacao', 'inicio', 'painel')), 'buscar': ('/buscar', 'Buscar notas', ('buscar notas', 'tela de busca', 'busca manual')),
         'empresas': ('/empresas', 'Empresas', ('empresas', 'carteira', 'clientes')), 'certificados': ('/certificados', 'Certificados A1', ('certificados', 'certificado')),
         'documentos': ('/documentos', 'Documentos', ('documentos', 'notas fiscais')), 'nfse': ('/nfse', 'NFS-e', ('nfse', 'conferencia')), 'auditoria': ('/auditoria', 'Auditoria', ('auditoria',)),
         'manifestacao': ('/manifestacao', 'Manifestação', ('manifestacao', 'ciencia')), 'fechamento': ('/fechamento', 'Fechamento', ('fechamento',)),
         'repositorio': ('/repositorio', 'Repositório', ('repositorio',)), 'boxe': ('/boxe', 'Box-e e resumo', ('boxe', 'resumo por e mail')),
         'relatorios': ('/relatorios', 'Relatórios', ('relatorios', 'relatorio')), 'exportar': ('/exportar', 'Baixar XMLs (ZIP)', ('baixar xmls', 'baixar xml', 'exportar', 'zip'))}
STOP = {'de', 'da', 'do', 'das', 'dos', 'em', 'um', 'uma', 'o', 'a', 'os', 'as', 'e', 'que', 'para', 'pra', 'por', 'com', 'se', 'eu', 'me', 'meu', 'minha', 'voce', 'vc', 'no', 'na', 'nos', 'nas', 'ao', 'pelo', 'pela',
        'ja', 'so', 'muito', 'mais', 'ou', 'tem', 'ter', 'foi', 'ser', 'sao', 'esta', 'estao', 'isso', 'esse', 'essa', 'este', 'qual', 'quais', 'como', 'onde', 'quando', 'preciso', 'quero', 'posso', 'pode', 'favor', 'exatinho'}
_PREF = {'nfs': 'nfse', 'nfc': 'nfce', 'nf': 'nfe', 'ct': 'cte', 'box': 'boxe'}


def norm(texto):
    t = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode('ascii').lower()
    t = re.sub(r'\b(nfs|nfc|nf|ct|box)\s*-\s*e\b', lambda m: m.group(1) + 'e', t)
    t = re.sub(r'\be\s*-\s*mail\b', 'email', t)
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def _stem(w):
    if len(w) > 3 and w.endswith('s'): w = w[:-1]
    return w[:4] if len(w) >= 5 else w


def _tokens(t):
    return [w for w in norm(t).split() if w not in STOP]


def _stems(t):
    return {_stem(w) for w in _tokens(t)}


def _has(t, *frases):
    return any(f in t for f in frases)


# ------------------------------------------------------------------ vocabulário e correção de digitação
_VOCAB = sorted({w for top in TOPICOS for ch in top['chaves'] for w in norm(ch).split() if len(w) >= 5} | {'certificado', 'empresas', 'atrasadas', 'buscaram', 'pendencias', 'notas', 'quantas', 'cancelada', 'cancelamento', 'situacao', 'resumo'})


def corrigir(pergunta, protegidas=()):
    protegidas = set(protegidas); out = []
    for w in re.findall(r'\S+|\s+', str(pergunta or '')):
        n = norm(w)
        if len(n) >= 5 and n.isalpha() and n not in _VOCAB and n not in protegidas and n not in STOP:
            perto = difflib.get_close_matches(n, _VOCAB, n=1, cutoff=0.84)
            if perto: out.append(perto[0]); continue
        out.append(w)
    return ''.join(out)


# ------------------------------------------------------------------ base de conhecimento
_INDICE = []
for _t in TOPICOS:
    _frases = []
    for ch in _t['chaves']:
        st = [_stem(w) for w in norm(ch).split() if w not in STOP]
        if st: _frases.append((norm(ch), st))
    _INDICE.append((_t, _frases))


def procurar_topicos(pergunta, limite=3):
    """[(pontos, tópico)] dos tópicos que mais combinam com a pergunta."""
    q = norm(pergunta); S = _stems(pergunta); res = []
    for top, frases in _INDICE:
        melhor = 0; soma = 0
        for texto, st in frases:
            pts = 0
            if all(s in S for s in st): pts = len(st) * 2 + 1 + (3 if texto in q else 0)
            elif len(st) >= 3 and sum(1 for s in st if s in S) >= len(st) - 1: pts = len(st)
            if pts: soma += pts; melhor = max(melhor, pts)
        if melhor: res.append((melhor + 0.2 * (soma - melhor), top))
    res.sort(key=lambda x: -x[0])
    return res[:limite]


def _resposta_topico(top, mais=None):
    acoes = [{'label': top['botao'], 'kind': 'goto', 'url': top['tela']}] if top.get('tela') and top.get('botao') else []
    sug = []
    for _p, o in (mais or []):
        if o['id'] != top['id']: sug.append(o['titulo'])
    return {'text': top['titulo'], 'passos': list(top['resposta']), 'lines': [], 'cards': [], 'actions': acoes, 'confirm': None, 'mood': 'dica', 'topic': top['id'], 'sugestoes': sug[:2], 'ajudou': True, 'ctx': {}}


# ------------------------------------------------------------------ respostas em geral
def _r(text, lines=None, cards=None, actions=None, confirm=None, mood='feliz', topic='resposta', sug=None, ctx=None, passos=None):
    return {'text': text, 'passos': passos or [], 'lines': lines or [], 'cards': cards or [], 'actions': actions or [], 'confirm': confirm, 'mood': mood, 'topic': topic, 'sugestoes': sug or [], 'ctx': ctx or {}}


def _plural(n, um, varios): return um if n == 1 else varios


def _cnpj_fmt(c):
    d = re.sub(r'\D', '', str(c or ''))
    return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}' if len(d) == 14 else d


def _dias(texto):
    m = re.search(r'(\d+)\s*dia', str(texto or '')); return int(m.group(1)) if m else None


def _empresa_card(l, dados, tipos=None):
    itens = []
    cels = l.get('celulas') or {}
    sem_cert = not l.get('certificado') and not l.get('cert_escritorio')
    for fam in (tipos or list(ROTULO)):
        c = cels.get(fam) or {}
        est = str(c.get('estado') or '')
        if fam not in (l.get('pendentes') or []) and est in ('em_dia', 'sem_notas'): continue
        causa = c.get('causa') or {}
        titulo = causa.get('titulo') or ''; acao = causa.get('acao') or ''; grav = causa.get('gravidade') or ''
        if not titulo:
            if sem_cert: titulo, acao, grav = 'Falta o certificado digital (A1)', 'Envie o certificado da empresa (ou o do escritório) em Certificados A1.', 'erro'
            elif est == 'nunca': titulo, acao, grav = 'Ainda não foi buscado', 'É só buscar: clique em Buscar agora.', 'aviso'
            elif est == 'atrasado': titulo, acao, grav = 'A última busca foi há mais de 3 dias', 'Busque de novo. Se a busca automática estiver desligada, ligue em Situação da busca.', 'aviso'
        if causa.get('codigo') == 'janela': grav = 'espera'
        itens.append({'tipo': ROTULO.get(fam, fam), 'estado': est, 'texto': c.get('texto') or est, 'causa': titulo, 'acao': acao, 'gravidade': grav})
    botoes = [{'label': 'Buscar agora', 'kind': 'buscar', 'cnpj': l['cnpj'], 'nome': l.get('nome') or ''}, {'label': 'Abrir', 'kind': 'goto', 'url': '/buscar?empresa=' + l['cnpj']}]
    if sem_cert: botoes.insert(0, {'label': 'Enviar certificado', 'kind': 'goto', 'url': '/certificados'})
    return {'tipo': 'empresa', 'nome': l.get('nome') or l['cnpj'], 'cnpj': l['cnpj'], 'cnpj_fmt': _cnpj_fmt(l['cnpj']), 'itens': itens, 'botoes': botoes}


def _tipos_na_frase(t):
    out = [f for f, p in (('nfe', r'\bnfe\b|nota fiscal eletronica|\bnf\b'), ('nfce', r'\bnfce\b'), ('cte', r'\bcte\b|conhecimento de transporte'), ('nfse', r'\bnfse\b|servico')) if re.search(p, t)]
    if 'nfce' in out and 'nfe' in out and not re.search(r'\bnfe\b', t): out.remove('nfe')
    return out


# ------------------------------------------------------------------ resumo do dia
def resumo(dados, nome=''):
    hoje = dados['hoje'](); itens = []
    linhas = dados['linhas']() or []
    certs = dados['certs']() or []
    venc = [c for c in certs if c.get('vencido')]
    if venc: itens.append({'gravidade': 'alta', 'texto': f"{len(venc)} certificado(s) vencido(s): {', '.join(c['nome'] for c in venc[:3])}{'...' if len(venc) > 3 else ''}.", 'acao': {'label': 'Abrir Certificados A1', 'kind': 'goto', 'url': '/certificados'}})
    por_vencer = []
    for c in certs:
        try:
            falta = (date.fromisoformat(str(c.get('validade'))[:10]) - hoje).days
        except Exception: continue
        if not c.get('vencido') and falta <= 30: por_vencer.append((c['nome'], falta))
    if por_vencer: itens.append({'gravidade': 'media', 'texto': f"{len(por_vencer)} certificado(s) vencem em até 30 dias: {', '.join(f'{n} ({d} d)' for n, d in por_vencer[:3])}.", 'acao': {'label': 'Abrir Certificados A1', 'kind': 'goto', 'url': '/certificados'}})
    sem_evento = dados['canceladas_sem_evento']() or []
    n_se = sum(int(x['qtd']) for x in sem_evento)
    if n_se: itens.append({'gravidade': 'alta', 'texto': f'{n_se} nota(s) cancelada(s) sem o XML do cancelamento ({len(sem_evento)} empresa(s)). Elas ficam de fora dos ZIPs até o evento chegar.', 'acao': {'label': 'Quais notas?', 'kind': 'ask', 'text': 'quais notas canceladas estão sem o evento?'}})
    atras = [l for l in linhas if any((l.get('celulas') or {}).get(f, {}).get('estado') == 'atrasado' for f in ROTULO)]
    nunca = [l for l in linhas if any((l.get('celulas') or {}).get(f, {}).get('estado') == 'nunca' for f in ROTULO)]
    sem_a1 = [l for l in linhas if not l.get('certificado') and not l.get('cert_escritorio')]
    if atras: itens.append({'gravidade': 'media', 'texto': f'{len(atras)} empresa(s) com busca atrasada (mais de 3 dias).', 'acao': {'label': 'Ver quais e por quê', 'kind': 'ask', 'text': 'quais empresas não buscaram notas e por quê?'}})
    if sem_a1: itens.append({'gravidade': 'media', 'texto': f'{len(sem_a1)} empresa(s) sem certificado A1 guardado: não conseguem buscar.', 'acao': {'label': 'Abrir Certificados A1', 'kind': 'goto', 'url': '/certificados'}})
    elif nunca: itens.append({'gravidade': 'info', 'texto': f'{len(nunca)} empresa(s) ainda não foram buscadas neste site.', 'acao': {'label': 'Buscar o que falta', 'kind': 'buscar_pendentes'}})
    novas = int(dados['novas_hoje']() or 0)
    if novas: itens.append({'gravidade': 'info', 'texto': f'{novas} nota(s) nova(s) chegaram hoje.', 'acao': {'label': 'Ver as notas', 'kind': 'goto', 'url': '/documentos'}})
    if not dados['auto_ligado'](): itens.append({'gravidade': 'info', 'texto': 'A busca automática está desligada.', 'acao': {'label': 'Abrir Situação da busca', 'kind': 'goto', 'url': '/situacao'}})
    return itens


def resposta_resumo(dados, nome=''):
    itens = resumo(dados, nome); primeiro = (nome or '').split()[0] if nome else ''
    if not itens:
        return _r(f"{'Oi, ' + primeiro + '! ' if primeiro else ''}Hoje está tudo em dia: não encontrei nada pendente.", mood='comemorando', topic='resumo', sug=['quais certificados vencem?', 'quantas notas temos este mês?'], ctx={'topic': 'resumo'})
    alta = any(i['gravidade'] == 'alta' for i in itens)
    return _r(f"{'Oi, ' + primeiro + '! ' if primeiro else ''}Tenho {len(itens)} {_plural(len(itens), 'ponto', 'pontos')} para você hoje:", lines=[('⚠ ' if i['gravidade'] == 'alta' else '• ') + i['texto'] for i in itens],
              actions=[i['acao'] for i in itens if i.get('acao')], mood='alerta' if alta else 'dica', topic='resumo', ctx={'topic': 'resumo'})


# ------------------------------------------------------------------ quem não buscou, por quê, quais tipos
def resposta_sem_busca(dados, tipos=None, so_sem_cert=False):
    linhas = dados['linhas']() or []; tipos = tipos or list(ROTULO)
    def pend(l): return [f for f in (l.get('pendentes') or []) if f in tipos]
    lista = [l for l in linhas if pend(l)]
    if so_sem_cert:
        sem = [l for l in linhas if not l.get('certificado') and not l.get('cert_escritorio')]
        if not sem: return _r('Todas as empresas têm certificado guardado (ou o do escritório cobre). 👍', mood='feliz', topic='sem_certificado', ctx={'topic': 'sem_certificado'})
        cards = []
        for l in sem[:8]:
            cards.append({'tipo': 'empresa', 'nome': l.get('nome') or l['cnpj'], 'cnpj': l['cnpj'], 'cnpj_fmt': _cnpj_fmt(l['cnpj']), 'itens': [{'tipo': 'Todos os tipos', 'estado': 'nunca', 'texto': 'Sem certificado', 'causa': 'Falta o certificado digital (A1)', 'acao': 'Envie o certificado da empresa (ou o do escritório, para usar a procuração) em Certificados A1.', 'gravidade': 'erro'}],
                          'botoes': [{'label': 'Enviar certificado', 'kind': 'goto', 'url': '/certificados'}]})
        return _r(f"{len(sem)} {_plural(len(sem), 'empresa está', 'empresas estão')} sem certificado A1 guardado, por isso não conseguem buscar notas.", cards=cards, actions=([{'label': f'Ver as {len(sem)} em Certificados A1', 'kind': 'goto', 'url': '/certificados'}] if len(sem) > 8 else []), mood='alerta', topic='sem_certificado', ctx={'topic': 'sem_certificado'})
    nome_tipos = ', '.join(ROTULO[t] for t in tipos) if len(tipos) < 4 else ''
    if not lista:
        return _r(f"Todas as empresas estão em dia{(' em ' + nome_tipos) if nome_tipos else ''}. 🎉" if not so_sem_cert else 'Todas as empresas têm certificado guardado.', mood='comemorando', topic='sem_busca', ctx={'topic': 'sem_busca'}, sug=['como está a busca automática?', 'quais certificados vencem?'])
    lista.sort(key=lambda l: (0 if (not l.get('certificado') and not l.get('cert_escritorio')) else 1, -(max([_dias((l['celulas'].get(f) or {}).get('texto')) or 0 for f in pend(l)] or [0])), str(l.get('nome'))))
    n_nunca = sum(1 for l in lista if any((l['celulas'].get(f) or {}).get('estado') == 'nunca' for f in pend(l)))
    n_atras = sum(1 for l in lista if any((l['celulas'].get(f) or {}).get('estado') == 'atrasado' for f in pend(l)))
    n_a1 = sum(1 for l in lista if not l.get('certificado') and not l.get('cert_escritorio'))
    causas = {}
    for l in lista:
        for f in pend(l):
            c = (l['celulas'].get(f) or {}).get('causa') or {}
            t = c.get('titulo') or ('Falta o certificado digital (A1)' if (not l.get('certificado') and not l.get('cert_escritorio')) else ('Ainda não foi buscado' if (l['celulas'].get(f) or {}).get('estado') == 'nunca' else 'Busca atrasada'))
            causas[t] = causas.get(t, 0) + 1
    topo = sorted(causas.items(), key=lambda x: -x[1])[:4]
    partes = []
    if n_atras: partes.append(f'{n_atras} atrasada(s)')
    if n_nunca: partes.append(f'{n_nunca} nunca buscada(s)')
    if n_a1: partes.append(f'{n_a1} sem certificado')
    texto = f"{len(lista)} {_plural(len(lista), 'empresa precisa', 'empresas precisam')} de busca{(' de ' + nome_tipos) if nome_tipos else ''}: {', '.join(partes)}."
    lines = ['Motivos mais comuns: ' + '; '.join(f'{t} ({n})' for t, n in topo)] if topo else []
    cards = [_empresa_card(l, dados, [f for f in pend(l)]) for l in lista[:6]]
    acoes = []
    if len(lista) > 6: acoes.append({'label': f'Ver as {len(lista)} na Situação da busca', 'kind': 'goto', 'url': '/situacao'})
    acoes.append({'label': 'Buscar o que falta (todas)', 'kind': 'buscar_pendentes'})
    return _r(texto, lines=lines, cards=cards, actions=acoes, mood='alerta' if n_a1 or n_atras > 3 else 'dica', topic='sem_busca', ctx={'topic': 'sem_busca'}, sug=['por que a primeira não buscou?'] if cards else None)


def resposta_empresa(dados, emp, mostrar_tudo=True):
    linhas = {l['cnpj']: l for l in (dados['linhas']() or [])}; l = linhas.get(re.sub(r'\D', '', str(emp['cnpj'])))
    if not l: return _r(f"Não encontrei {emp.get('name')} na Situação da busca.", topic='situacao_empresa', mood='dica')
    card = _empresa_card(l, dados, list(ROTULO) if mostrar_tudo else None)
    pend = l.get('pendentes') or []
    if not card['itens']:
        return _r(f"{l.get('nome')}: tudo em dia, nos quatro tipos de nota. 👍", cards=[], actions=[{'label': 'Abrir a busca desta empresa', 'kind': 'goto', 'url': '/buscar?empresa=' + l['cnpj']}], mood='feliz', topic='situacao_empresa', ctx={'company': l['cnpj'], 'topic': 'situacao_empresa'})
    # mostra todos os tipos (inclusive os em dia), para a pessoa ver a empresa inteira
    itens = []
    for fam in ROTULO:
        c = (l.get('celulas') or {}).get(fam) or {}; est = str(c.get('estado') or '')
        ja = next((i for i in card['itens'] if i['tipo'] == ROTULO[fam]), None)
        itens.append(ja or {'tipo': ROTULO[fam], 'estado': est, 'texto': c.get('texto') or est, 'causa': '', 'acao': '', 'gravidade': ''})
    card['itens'] = itens
    return _r(f"{l.get('nome')}: {len(pend)} {_plural(len(pend), 'tipo precisa', 'tipos precisam')} de busca.", cards=[card], mood='alerta' if any(i['gravidade'] == 'erro' for i in itens) else 'dica', topic='situacao_empresa', ctx={'company': l['cnpj'], 'topic': 'situacao_empresa'})


def resposta_certificados(dados, so_vencendo=True):
    certs = dados['certs']() or []; hoje = dados['hoje'](); venc = []; logo = []; sem = [l for l in (dados['linhas']() or []) if not l.get('certificado') and not l.get('cert_escritorio')]
    for c in certs:
        try: falta = (date.fromisoformat(str(c.get('validade'))[:10]) - hoje).days
        except Exception: continue
        if c.get('vencido') or falta < 0: venc.append((c['nome'], -falta if falta < 0 else 0))
        elif falta <= 60: logo.append((c['nome'], falta))
    lines = []
    if venc: lines += [f'VENCIDO: {n} (há {d} dia(s))' for n, d in venc[:8]]
    if logo: lines += [f'Vence em {d} dia(s): {n}' for n, d in sorted(logo, key=lambda x: x[1])[:8]]
    if sem: lines.append(f'{len(sem)} empresa(s) sem certificado guardado' + (': ' + ', '.join(l['nome'] for l in sem[:4]) + ('...' if len(sem) > 4 else '')))
    if not lines: return _r(f'Os {len(certs)} certificado(s) guardados estão válidos por mais de 60 dias. 👍', mood='feliz', topic='certificados', actions=[{'label': 'Abrir Certificados A1', 'kind': 'goto', 'url': '/certificados'}])
    return _r('Veja a situação dos certificados:', lines=lines, mood='alerta' if venc or sem else 'dica', topic='certificados', actions=[{'label': 'Abrir Certificados A1', 'kind': 'goto', 'url': '/certificados'}])


def resposta_contagem(dados, emp, periodo, tipos=None):
    de, ate, rotulo = periodo
    cont = dados['contagem'](emp['cnpj'] if emp else None, de.isoformat(), ate.isoformat())
    total = 0; canc = 0; lines = []
    for fam in (tipos or list(ROTULO)):
        c = cont.get(fam) or {}; a, k = int(c.get('aut') or 0), int(c.get('canc') or 0); total += a; canc += k
        if a or k: lines.append(f"{ROTULO[fam]}: {a} autorizada(s)" + (f' e {k} cancelada(s)' if k else ''))
    quem = emp['name'] if emp else 'todas as empresas'
    if not lines: return _r(f'Não encontrei notas de {quem} em {rotulo}.', mood='dica', topic='contagem', ctx={'topic': 'contagem', 'period': [de.isoformat(), ate.isoformat(), rotulo], **({'company': emp['cnpj']} if emp else {})})
    return _r(f'{quem} em {rotulo}: {total} nota(s) autorizada(s)' + (f' e {canc} cancelada(s).' if canc else '.'), lines=lines, mood='feliz', topic='contagem', actions=[{'label': 'Baixar os XMLs em ZIP', 'kind': 'goto', 'url': '/exportar?' + (f"empresa={emp['cnpj']}&" if emp else '') + f'de={de.isoformat()}&ate={ate.isoformat()}'}],
              ctx={'topic': 'contagem', 'period': [de.isoformat(), ate.isoformat(), rotulo], **({'company': emp['cnpj']} if emp else {})})


def resposta_canceladas(dados):
    lista = dados['canceladas_sem_evento']() or []
    if not lista: return _r('Nenhuma nota cancelada está sem o XML do cancelamento. 👍', mood='comemorando', topic='canceladas')
    lines = [f"{x['nome']}: {x['qtd']} nota(s)" for x in lista[:10]]
    return _r(f"{sum(int(x['qtd']) for x in lista)} nota(s) cancelada(s) estão sem o XML do cancelamento (o Exato nunca inventa esse arquivo):", lines=lines,
              passos=['Busque de novo a empresa: o evento completo costuma chegar depois.', 'Se não chegar, peça o XML do cancelamento ao cliente.'], mood='alerta', topic='canceladas',
              actions=[{'label': 'Abrir Buscar notas', 'kind': 'goto', 'url': '/buscar'}])


def _empresa_da_frase(texto, dados, ctx):
    empresas = dados['empresas']() or []; ass = nucleo.modulo('exato_assistente')
    achadas = ass.match_companies(texto, empresas)
    if len(achadas) > 1: return None, _r('Encontrei mais de uma empresa parecida: ' + ', '.join(c['name'] for c in achadas[:5]) + '. Diga o nome completo ou o CNPJ.', mood='dica', topic='duvida')
    if achadas: return achadas[0], None
    cn = re.sub(r'\D', '', str((ctx or {}).get('company') or ''))
    for c in empresas:
        if cn and re.sub(r'\D', '', str(c['cnpj'])) == cn: return c, None
    return None, None


# ------------------------------------------------------------------ pergunta -> resposta
def responder(pergunta, dados, nome='', ctx=None):
    ctx = dict(ctx or {}); q0 = str(pergunta or '').strip()
    if not q0: return _r('Pode perguntar. Por exemplo: "quais empresas não buscaram notas?" ou "como envio o certificado?".', mood='dica', topic='vazio', sug=['resumo do dia', 'quais empresas não buscaram notas e por quê?', 'como envio o certificado?'])
    empresas = dados['empresas']() or []
    protegidas = {w for c in empresas for w in norm(c.get('name')).split()}
    q = corrigir(q0, protegidas); t = norm(q)
    ass = nucleo.modulo('exato_assistente'); hoje = dados['hoje'](); achadas = ass.match_companies(q, empresas)
    per = None
    try: per = ass.parse_period(q, hoje)
    except Exception: per = None
    tipos = _tipos_na_frase(t)
    pergunta_de_uso = (bool(re.match(r'^(como|onde|qual o caminho|o que (e|significa|quer dizer|faz)|para que serve|de que forma|ensina|me ensina|passo a passo)\b', t)) or t.startswith('como ')) and not re.match(r'^como (esta|estao|vai|andam?|foi)\b', t)

    # conversa
    if re.fullmatch(r'(oi+|ola|opa|e ai|hey|bom dia|boa tarde|boa noite|oie|ola exatinho|oi exatinho)', t):
        r = resposta_resumo(dados, nome); r['text'] = ('Olá! ' if not t.startswith('bom') and not t.startswith('boa') else t.capitalize() + '! ') + r['text']; return r
    if re.search(r'\b(obrigad|brigad|valeu|muito bom|show|perfeito|otimo|ajudou)\b', t) and len(t.split()) <= 6:
        return _r('Por nada! Estou aqui quando precisar. 😊', mood='comemorando', topic='agradecimento')
    if _has(t, 'resumo do dia', 'resumo de hoje', 'o que tenho', 'o que preciso fazer', 'o que falta fazer', 'pendencia', 'o que precisa de atencao', 'como estamos', 'como esta tudo', 'alguma novidade', 'tem algo para eu') or t in ('resumo', 'pendencias'):
        return resposta_resumo(dados, nome)

    # ir para uma tela
    if re.search(r'\b(abra|abrir|abre|va para|vai para|ir para|me leve|leve me|mostre a tela|mostra a tela|quero ver a tela)\b', t):
        for _k, (url, rot, palavras) in TELAS.items():
            if any(p in t for p in palavras):
                return _r(f'Abrindo {rot}.', actions=[{'label': f'Abrir {rot}', 'kind': 'goto', 'url': url}], mood='feliz', topic='ir', ctx={'topic': 'ir'}) | {'abrir': url}
        return _r('Para qual tela? Posso abrir ' + ', '.join(v[1] for v in TELAS.values()) + '.', mood='dica', topic='duvida', actions=[{'label': v[1], 'kind': 'goto', 'url': v[0]} for v in list(TELAS.values())[:6]])

    # buscar (sempre com confirmação)
    if re.search(r'\b(busque|busca|buscar|atualize|atualizar|puxe|puxar)\b', t) and not pergunta_de_uso and not _has(t, 'nao busc', 'sem busc', 'ja busc', 'ultima busca', 'quando busc', 'por que', 'porque', 'automatic', 'data', 'periodo') and (achadas or _has(t, 'todas', 'o que falta', 'pendente', 'atrasad')):
        if achadas and len(achadas) == 1:
            e = achadas[0]; tp = tipos or list(ROTULO)
            return _r(f"Posso buscar agora as notas de {e['name']} ({', '.join(ROTULO[x] for x in tp)})?", confirm={'texto': f"Buscar {e['name']} agora?", 'acao': {'kind': 'buscar', 'cnpj': re.sub(r'\D', '', str(e['cnpj'])), 'tipos': tp, 'nome': e['name']}}, mood='analisando', topic='acao_buscar', ctx={'company': e['cnpj'], 'topic': 'acao_buscar'})
        if len(achadas) > 1: return _r('Encontrei mais de uma empresa parecida: ' + ', '.join(c['name'] for c in achadas[:5]) + '. Diga o nome completo ou o CNPJ.', mood='dica', topic='duvida')
        todas = _has(t, 'todas') and not _has(t, 'o que falta', 'pendente', 'atrasad')
        return _r('Posso buscar ' + ('as notas de todas as empresas' if todas else 'só o que falta (empresas atrasadas ou nunca buscadas)') + ' agora?', confirm={'texto': 'Buscar agora?', 'acao': {'kind': 'buscar_todas' if todas else 'buscar_pendentes'}}, mood='analisando', topic='acao_buscar')

    # baixar zip de uma empresa
    if _has(t, 'zip', 'baixar xml', 'baixe os xml', 'exportar xml') and achadas and len(achadas) == 1 and not pergunta_de_uso:
        e = achadas[0]; de, ate, rot = per if per else (None, None, '')
        url = '/exportar?empresa=' + re.sub(r'\D', '', str(e['cnpj'])) + (f'&de={de.isoformat()}&ate={ate.isoformat()}' if de else '')
        return _r(f"Abri o formulário de ZIP de {e['name']}{(' em ' + rot) if rot else ''}. Confira o formato e clique em Gerar ZIP: ele já leva os eventos das notas.", actions=[{'label': 'Abrir Baixar XMLs (ZIP)', 'kind': 'goto', 'url': url}], mood='dica', topic='acao_zip', ctx={'company': e['cnpj'], 'topic': 'acao_zip'}) | {'abrir_ao_clicar': url}

    # quem não buscou / por quê / situação de uma empresa
    quer_sem_busca = _has(t, 'nao buscou', 'nao buscaram', 'nao buscadas', 'nao buscado', 'sem busca', 'sem buscar', 'nunca buscou', 'nunca buscad', 'ainda nao busc', 'atrasad', 'desatualizad', 'nao puxou', 'nao baixou', 'nao veio nota', 'sem notas novas', 'nao trouxe', 'quem nao busc', 'nao buscou notas', 'nao buscaram notas', 'falta buscar', 'precisam de busca', 'precisa de busca', 'pendentes de busca', 'busca pendente', 'buscas pendentes')
    quer_porque = bool(re.search(r'\b(por que|porque|pq|motivo|razao|causa)\b', t)) and _has(t, 'busc', 'atras', 'nao veio', 'erro', 'falh', 'recus', 'nao baix', 'nao puxou', 'nao trouxe', 'nao funcion', 'nao aparec')
    if (quer_sem_busca or quer_porque) and not pergunta_de_uso:
        emp, duvida = _empresa_da_frase(q, dados, ctx if (quer_porque and not achadas) else {})
        if duvida: return duvida
        if emp: return resposta_empresa(dados, emp)
        return resposta_sem_busca(dados, tipos or None)
    if achadas and len(achadas) == 1 and _has(t, 'situacao', 'status', 'como esta', 'em dia', 'esta atrasad', 'ultima busca', 'quando buscou', 'tipos de nota', 'quais tipos', 'foi buscad', 'buscou') and not pergunta_de_uso:
        return resposta_empresa(dados, achadas[0])

    # certificados e notas
    if _has(t, 'sem certificado', 'falta certificado', 'sem o certificado') and re.search(r'\b(quais|quantas|quem|algum|alguma|tem)\b', t) and not pergunta_de_uso:
        return resposta_sem_busca(dados, None, so_sem_cert=True)
    if 'certificad' in t and _has(t, 'venc', 'validade', 'expira', 'sem certificado', 'falta certificado', 'quais', 'quantos', 'algum') and not pergunta_de_uso and not _has(t, 'venceu o que', 'renovar', 'enviar', 'cadastrar'):
        return resposta_certificados(dados)
    if 'cancelad' in t and _has(t, 'sem evento', 'sem xml', 'falta o evento', 'sem o xml') and re.search(r'\b(quais|quantas|tem|algum|existe|mostre|liste)\b', t):
        return resposta_canceladas(dados)
    if re.search(r'\b(quantas|quantidade|quantos|numero de) (notas?|xmls?|documentos?)\b', t) or (_has(t, 'quantas notas', 'quantos xml') ):
        emp, duvida = _empresa_da_frase(q, dados, ctx)
        if duvida: return duvida
        if not per:
            a = date(hoje.year, hoje.month, 1); b = (date(hoje.year + (hoje.month == 12), (hoje.month % 12) + 1, 1) - timedelta(days=1)); per = (a, b, f'{hoje.month:02d}/{hoje.year} (mês atual)')
        return resposta_contagem(dados, emp, per, tipos or None)

    # dúvidas de uso (base de conhecimento)
    ach = procurar_topicos(q)
    if ach and ach[0][0] >= 3:
        top = ach[0][1]; mais = [x for x in ach[1:] if x[0] >= max(3, ach[0][0] * 0.6)]
        r = _resposta_topico(top, mais); r['ctx'] = {'topic': 'kb:' + top['id']}; return r
    # continuação ("e a outra empresa?", "e em outubro?")
    if ctx.get('topic') in ('situacao_empresa', 'contagem') and (achadas or per) and len(t.split()) <= 6:
        if ctx['topic'] == 'situacao_empresa' and achadas and len(achadas) == 1: return resposta_empresa(dados, achadas[0])
        if ctx['topic'] == 'contagem':
            emp, _d = _empresa_da_frase(q, dados, ctx); p2 = per
            if not p2 and ctx.get('period'):
                pp = ctx['period']; p2 = (date.fromisoformat(pp[0]), date.fromisoformat(pp[1]), pp[2])
            if p2: return resposta_contagem(dados, emp, p2, tipos or None)
    return desconhecida(dados, q0)


def desconhecida(dados, pergunta):
    ex = [EXEMPLOS[k][0] for k in ('enviar_certificado', 'baixar_zip', 'buscar_data', 'janela_sefaz') if k in EXEMPLOS]
    r = _r('Ainda não sei responder isso. 🤔 Não quero inventar: já anotei a sua pergunta para me ensinarem.', lines=['Eu sei dizer quais empresas ainda não buscaram notas e por quê, o que está pendente hoje, quantas notas uma empresa tem, certificados que vencem, e tirar dúvidas de uso do sistema.'],
           mood='dica', topic='desconhecido', sug=['resumo do dia', 'quais empresas não buscaram notas e por quê?'] + ex[:2])
    r['desconhecida'] = True; return r


def sugestoes_iniciais():
    return ['resumo do dia', 'quais empresas não buscaram notas e por quê?', 'quais certificados vencem?', 'como envio o certificado?', 'como baixo o ZIP com os eventos?']
