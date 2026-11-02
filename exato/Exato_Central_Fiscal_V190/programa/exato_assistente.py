"""Exatinho conversando: entende perguntas e pedidos em português, consulta o Arquivo Fiscal Local e devolve respostas com as
evidências (as notas e a conta por trás), botões de ação e o resumo do dia.

Tudo roda no computador: nenhum dado fiscal sai daqui e não há IA externa. O módulo não conhece a tela: recebe `data`, um
dicionário de funções (empresas, resumo, notas, buscas, certificados...), e devolve dicionários simples que a tela mostra.

Resposta: {'text': str, 'lines': [str], 'actions': [{'label', 'kind', ...}], 'confirm': {...}|None, 'topic': str}
Ações: {'kind': 'goto', 'screen'} | {'kind': 'nfse_search_save'|'nfse_search', 'cnpj'} | {'kind': 'nfse_all_save'} |
       {'kind': 'nfse_report', 'cnpj', 'df', 'dt'} | {'kind': 'docs_cancelled_exported'} | {'kind': 'cert_list'}
"""
import difflib
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

MONTHS = ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
MONTH_NAMES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
STOP_COMPANY = {'ltda', 'epp', 'eireli', 'sa', 'me', 'comercio', 'servicos', 'servico', 'industria', 'empresa', 'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'para', 'com', 'cia', 'grupo',
                'nota', 'notas', 'nfse', 'nfe', 'xml', 'mes', 'ano', 'todas', 'todos', 'tudo', 'quanto', 'quantas', 'quais', 'qual', 'busque', 'buscar', 'salve', 'gere', 'relatorio', 'abra', 'mostre',
                'prestou', 'prestei', 'tomou', 'tomei', 'cancelada', 'canceladas', 'exportada', 'exportadas', 'passado', 'atual', 'este', 'esta', 'esse', 'essa', 'meu', 'minha', 'hoje', 'ontem'}
FAMILY_LABEL = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}
SCREENS = {'nfse': ('nfs-e', 'nfse', 'servicos eletronicos'), 'documents': ('documentos', 'documento fiscal', 'arquivo fiscal'), 'companies': ('empresas', 'empresa cadastro', 'cadastro'),
           'audit': ('auditoria',), 'history': ('historico',), 'pending': ('pendencias', 'pendencia'), 'certificate': ('certificado', 'certificados'), 'reports': ('relatorios',),
           'dashboard': ('inicio', 'painel', 'home'), 'sync': ('buscar xml', 'busca de xml', 'buscar nf-e')}
SCREEN_LABEL = {'nfse': 'NFS-e', 'documents': 'Documentos Fiscais', 'companies': 'Empresas', 'audit': 'Auditoria Fiscal', 'history': 'Histórico', 'pending': 'Pendências',
                'certificate': 'Certificado', 'reports': 'Relatórios', 'dashboard': 'Início', 'sync': 'Buscar XML'}


def norm(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'\s+', ' ', text).strip()


def brl(v):
    try:
        d = Decimal(str(v or 0))
    except Exception:
        d = Decimal('0')
    s = f'{d:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'R$ {s}'


def fmt_cnpj(d):
    d = re.sub(r'\D', '', str(d or ''))
    return f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}' if len(d) == 14 else d


def br_date(iso):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(iso or ''))
    return f'{m.group(3)}/{m.group(2)}/{m.group(1)}' if m else str(iso or '')


def _month_range(year, month):
    first = date(year, month, 1)
    nxt = date(year + (month == 12), (month % 12) + 1, 1)
    return first, nxt - timedelta(days=1)


def parse_period(text, today):
    """(inicio, fim, rótulo) em datas, ou None se a frase não fala de período."""
    t = norm(text)
    m = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s*(?:a|ate|ao|-)\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', t)
    if m:
        try:
            y1 = int(m.group(3) or today.year); y2 = int(m.group(6) or y1)
            y1 += 2000 if y1 < 100 else 0; y2 += 2000 if y2 < 100 else 0
            a = date(y1, int(m.group(2)), int(m.group(1))); b = date(y2, int(m.group(5)), int(m.group(4)))
            if a <= b: return a, b, f'{a:%d/%m/%Y} a {b:%d/%m/%Y}'
        except ValueError:
            pass
    if re.search(r'\bhoje\b', t): return today, today, 'hoje'
    if re.search(r'\bontem\b', t):
        y = today - timedelta(days=1); return y, y, 'ontem'
    if re.search(r'mes passado|mes anterior|ultimo mes', t):
        last = today.replace(day=1) - timedelta(days=1); a, b = _month_range(last.year, last.month); return a, b, f'{MONTH_NAMES[a.month - 1]}/{a.year}'
    if re.search(r'este mes|esse mes|mes atual|no mes\b|do mes\b|neste mes', t) and not any(mo in t for mo in MONTHS):
        a, b = _month_range(today.year, today.month); return a, b, f'{MONTH_NAMES[a.month - 1]}/{a.year}'
    mm = re.search(r'ultimos?\s+(\d{1,2})\s+(mes(?:es)?|dias?|semanas?)', t)
    if mm:
        n = int(mm.group(1)); unit = mm.group(2)
        if unit.startswith('mes'):
            a = today.replace(day=1)
            for _ in range(n - 1): a = (a - timedelta(days=1)).replace(day=1)
            return a, today, f'últimos {n} meses'
        days = n * (7 if unit.startswith('semana') else 1)
        return today - timedelta(days=days - 1), today, f'últimos {days} dias'
    if re.search(r'semana passada', t):
        mon = today - timedelta(days=today.weekday() + 7); return mon, mon + timedelta(days=6), 'semana passada'
    if re.search(r'esta semana|essa semana|nesta semana', t):
        mon = today - timedelta(days=today.weekday()); return mon, today, 'esta semana'
    mm = re.search(r'(primeiro|segundo|terceiro|quarto|1o|2o|3o|4o|1|2|3|4)\s*(?:o\s*)?trimestre(?:\s*de\s*(\d{4}))?', t)
    if mm:
        q = {'primeiro': 1, '1o': 1, '1': 1, 'segundo': 2, '2o': 2, '2': 2, 'terceiro': 3, '3o': 3, '3': 3, 'quarto': 4, '4o': 4, '4': 4}[mm.group(1)]
        y = int(mm.group(2)) if mm.group(2) else today.year
        return date(y, 3 * q - 2, 1), _month_range(y, 3 * q)[1], f'{q}º trimestre/{y}'
    if re.search(r'este trimestre|esse trimestre|neste trimestre', t):
        q = (today.month - 1) // 3 + 1; return date(today.year, 3 * q - 2, 1), today, f'{q}º trimestre/{today.year}'
    if re.search(r'ano passado|ano anterior', t):
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), f'{today.year - 1}'
    if re.search(r'este ano|esse ano|neste ano|no ano\b', t):
        return date(today.year, 1, 1), today, f'{today.year}'
    for idx, name in enumerate(MONTHS, 1):
        mm = re.search(rf'\b{name}\b(?:\s*(?:de|/)?\s*(\d{{4}}))?', t)
        if mm:
            year = int(mm.group(1)) if mm.group(1) else (today.year if idx <= today.month else today.year - 1)
            a, b = _month_range(year, idx); return a, b, f'{MONTH_NAMES[idx - 1]}/{year}'
    mm = re.search(r'\b(0?[1-9]|1[0-2])/(\d{4})\b', t)
    if mm:
        a, b = _month_range(int(mm.group(2)), int(mm.group(1))); return a, b, f'{MONTH_NAMES[a.month - 1]}/{a.year}'
    return None


def _tokens(name):
    return [w for w in re.findall(r'[a-z0-9]+', norm(name)) if len(w) >= 3 and w not in STOP_COMPANY and w not in MONTHS]


def match_companies(text, companies):
    """Empresas citadas na frase: CNPJ digitado ou nome (pelo menos uma palavra própria do nome). Devolve as de maior pontuação."""
    t = norm(text); digits = re.sub(r'\D', '', text or '')
    for c in companies:
        cn = re.sub(r'\D', '', str(c.get('cnpj') or ''))
        if cn and len(digits) >= 14 and cn in digits:
            return [c]
    words = set(re.findall(r'[a-z0-9]+', t)); scored = []
    for c in companies:
        toks = _tokens(c.get('name'))
        hit = [w for w in toks if w in words]
        if hit:
            scored.append((len(hit) / max(1, len(toks)) + len(hit), c))
    if not scored: return []
    best = max(s for s, _ in scored)
    return [c for s, c in scored if s == best]


def _has(t, *words):
    return any(w in t for w in words)


VOCAB = sorted({w for w in re.findall(r'[a-z]{5,}', ' '.join([
    'prestou prestei prestado prestadas tomou tomei tomado tomadas canceladas cancelada exportada exportadas exportei certificado certificados vencendo vencido empresas empresa notas quantas quantos quanto',
    'faturei faturou faturamento relatorio relatorios buscar busque salve salvar abrir mostre resumo pendencias historico auditoria documentos clientes fornecedores maiores principais ranking comparar compare variacao',
    'setembro outubro novembro dezembro janeiro fevereiro marco abril maio junho julho agosto passado atual semana trimestre ultimos anterior todas todos tudo piloto automatico ligue desligue ajuda'])) if w not in ('', None)})


def fix_typos(question, protect=()):
    """Corrige erros de digitação comuns trocando palavras quase iguais às que o assistente conhece (nomes de empresas ficam como estão)."""
    protect = set(protect); out = []
    for w in re.findall(r'\S+|\s+', str(question or '')):
        core = norm(re.sub(r'[^\w]', '', w))
        if len(core) >= 5 and core.isalpha() and core not in VOCAB and core not in protect and core not in STOP_COMPANY:
            near = difflib.get_close_matches(core, VOCAB, n=1, cutoff=0.8)
            if near:
                out.append(near[0] + re.sub(r'^[\w]+', '', w, flags=re.U) if w[0].isalnum() else w); continue
        out.append(w)
    return ''.join(out)


def detect_intent(question):
    t = norm(question)
    if not t: return 'vazio'
    if _has(t, 'piloto'):
        if _has(t, 'desligue', 'desligar', 'desative', 'desativar', 'pare', 'pausar'): return 'piloto_off'
        if _has(t, 'ligue', 'ligar', 'ative', 'ativar', 'comece', 'inicie'): return 'piloto_on'
        if _has(t, 'agora', 'execute', 'rode', 'rodar', 'executar'): return 'piloto_agora'
        return 'piloto_status'
    if _has(t, 'maiores clientes', 'principais clientes', 'maior cliente', 'top clientes', 'quem mais comprou', 'melhores clientes', 'meus clientes'): return 'top_clientes'
    if _has(t, 'maiores fornecedores', 'principais fornecedores', 'maior fornecedor', 'top fornecedores', 'quem mais me vendeu', 'fornecedores'): return 'top_fornecedores'
    if _has(t, 'maior nota', 'maiores notas', 'nota mais cara', 'nota de maior valor', 'nota mais alta'): return 'maiores_notas'
    if _has(t, 'compar', 'em relacao ao', 'versus', 'variacao', 'cresceu', 'caiu', 'aumentou', 'diminuiu', 'evolucao'): return 'comparar'
    if _has(t, 'ranking', 'qual empresa', 'que empresa mais', 'empresa que mais', 'cada empresa', 'por empresa') and not _has(t, 'sem busca', 'certificado'): return 'ranking_empresas'
    if _has(t, 'ajuda', 'o que voce faz', 'o que voce sabe', 'o que voce pode', 'comandos', 'como funciona voce') and not _has(t, 'relatorio'): return 'ajuda'
    if _has(t, 'resumo do dia', 'resumo de hoje', 'o que tenho', 'o que preciso', 'pendencias de hoje', 'o que falta fazer', 'bom dia', 'tem algo', 'alguma pendencia', 'o que fazer hoje'): return 'resumo'
    if _has(t, 'relatorio'): return 'acao_relatorio'
    if _has(t, 'busque', 'buscar', 'busca', 'puxe', 'puxar', 'baixe', 'baixar', 'atualize', 'atualizar') and not _has(t, 'sem busca', 'nao buscou', 'nao buscaram', 'ultima busca', 'quando buscou'):
        if re.search(r'\b(todas|todos)\b', t) and _has(t, 'empresa'): return 'acao_todas'
        return 'acao_buscar_salvar' if _has(t, 'salv', 'tudo', 'exporte', 'exportar') else 'acao_buscar'
    if _has(t, 'abra', 'abrir', 'va para', 'ir para', 'leve-me', 'me leve', 'mostre a tela', 'abre') : return 'ir'
    if _has(t, 'sem busca', 'nao buscou', 'nao buscaram', 'sem buscar', 'desatualizad', 'atrasad', 'ultima busca', 'quando buscou', 'nao busquei', 'faz tempo'): return 'sem_busca'
    if _has(t, 'certificado') and _has(t, 'venc', 'validade', 'expira'): return 'certificados'
    if _has(t, 'cancelad'): return 'canceladas'
    if _has(t, 'nao exportad', 'falta exportar', 'ainda nao exportei', 'para exportar', 'nao salv', 'falta salvar'): return 'nao_exportadas'
    if _has(t, 'quanto', 'total', 'valor', 'soma', 'faturamento', 'faturei', 'faturou', 'gastei', 'paguei', 'recebi') and _has(t, 'prest', 'emit', 'fatur', 'tom', 'receb', 'pagu', 'gast', 'nfs'): return 'total_nfse'
    if _has(t, 'quantas', 'quantidade', 'quantos', 'numero de notas', 'contagem'): return 'contagem'
    if _has(t, 'nfs', 'servico') and _has(t, 'total', 'quanto'): return 'total_nfse'
    return 'desconhecido'


def _kind_from_text(t):
    if _has(t, 'prest', 'emit', 'fatur', 'recebi de', 'saida'): return 'Saída'
    if _has(t, 'tomad', 'tomei', 'tomou', 'gastei', 'paguei', 'contrat', 'entrada'): return 'Entrada'
    return ''


def _resolve_company(question, data, ctx=None):
    """(empresa|None, mensagem de dúvida|None). Ordem: a que a frase cita > a da conversa > a ativa na tela."""
    companies = data['companies']() or []
    found = match_companies(question, companies)
    if len(found) > 1:
        names = ', '.join(c['name'] for c in found[:5])
        return None, {'text': f'Encontrei mais de uma empresa parecida: {names}. Diga o nome completo ou o CNPJ.', 'lines': [], 'actions': [], 'confirm': None, 'topic': 'duvida'}
    if found: return found[0], None
    for cand in ((ctx or {}).get('company'), data['active_cnpj']()):
        cn = re.sub(r'\D', '', str(cand or ''))
        for c in companies:
            if cn and re.sub(r'\D', '', str(c.get('cnpj'))) == cn: return c, None
    return (companies[0], None) if len(companies) == 1 else (None, None)


def _reply(text, lines=None, actions=None, confirm=None, topic='resposta', how='', suggest=None, ctx=None):
    return {'text': text, 'lines': (lines or []) + ([f'ℹ Como calculei: {how}'] if how else []), 'actions': (actions or []) + [{'label': q, 'kind': 'ask', 'text': q} for q in (suggest or [])],
            'confirm': confirm, 'topic': topic, 'ctx': ctx or {}}


def _period_or_default(question, data, ctx=None, default='mes'):
    today = data['today']()
    p = parse_period(question, today)
    if p: return p
    cp = (ctx or {}).get('period')
    if cp:
        return date.fromisoformat(cp[0]), date.fromisoformat(cp[1]), cp[2]
    if default == 'mes':
        a, b = _month_range(today.year, today.month); return a, b, f'{MONTH_NAMES[a.month - 1]}/{a.year} (mês atual)'
    return None


def _goto(screen, label=None):
    return {'label': label or f'Abrir {SCREEN_LABEL.get(screen, screen)}', 'kind': 'goto', 'screen': screen}


# ---------- resumo do dia
def daily_briefing(data):
    """Pontos que pedem a atenção do usuário hoje: [{'severity': 'alta'|'media'|'info', 'text', 'action'}]."""
    today = data['today'](); items = []; names = {re.sub(r'\D', '', str(c['cnpj'])): c['name'] for c in (data['companies']() or [])}
    nm = lambda cnpj: names.get(re.sub(r'\D', '', str(cnpj)), fmt_cnpj(cnpj))
    canc = data['cancelled_exported']() or []
    n = sum(int(x['count']) for x in canc)
    if n:
        who = ', '.join(sorted({nm(x['cnpj']) for x in canc})[:3])
        items.append({'severity': 'alta', 'text': f'{n} nota(s) já exportada(s) foram canceladas ({who}). Confira antes de lançar.', 'action': {'label': 'Ver canceladas exportadas', 'kind': 'docs_cancelled_exported'}})
    certs = data['certs']() or []
    for c in certs:
        try:
            left = (date.fromisoformat(str(c['not_after'])[:10]) - today).days
        except Exception:
            continue
        if left < 0:
            items.append({'severity': 'alta', 'text': f'O certificado de {c.get("name") or "uma empresa"} venceu há {-left} dia(s).', 'action': {'label': 'Abrir Certificado', 'kind': 'cert_list'}})
        elif left <= 30:
            items.append({'severity': 'media', 'text': f'O certificado de {c.get("name") or "uma empresa"} vence em {left} dia(s).', 'action': {'label': 'Abrir Certificado', 'kind': 'cert_list'}})
    runs = data['last_runs']() or {}
    stale = []
    for cnpj, name in names.items():
        ok = (runs.get(cnpj) or {}).get('ok_at')
        try:
            days = (today - date.fromisoformat(str(ok)[:10])).days if ok else None
        except Exception:
            days = None
        if days is None or days >= 7:
            stale.append((name, days))
    if stale:
        sample = ', '.join(f'{n} ({"nunca buscou" if d is None else f"há {d} dias"})' for n, d in stale[:3])
        items.append({'severity': 'media', 'text': f'{len(stale)} empresa(s) sem busca há 7 dias ou mais: {sample}{"..." if len(stale) > 3 else ""}.', 'action': {'label': 'Buscar NFS-e de todas e salvar', 'kind': 'nfse_all_save'}})
    failed = [(cnpj, r) for cnpj, r in runs.items() if r.get('last_error') and 'XML' in str(r.get('last_error'))]
    if failed:
        items.append({'severity': 'media', 'text': f'A última busca de {nm(failed[0][0])} deixou XMLs sem baixar. Tente de novo.', 'action': {'label': 'Buscar de novo', 'kind': 'nfse_search', 'cnpj': failed[0][0]}})
    unexp = data['unexported']() or []
    k = sum(int(x['count']) for x in unexp)
    if k:
        items.append({'severity': 'info', 'text': f'{k} nota(s) ainda não foram salvas na pasta dos clientes.', 'action': {'label': 'Abrir Documentos Fiscais', 'kind': 'goto', 'screen': 'documents'}})
    return items


def render_briefing(items, name=''):
    if not items:
        return _reply(f'{"Bom ver você, " + name + "! " if name else ""}Hoje está tudo em dia: nada pendente que eu tenha encontrado.', topic='resumo')
    head = f'{"Oi, " + name + "! " if name else ""}Tenho {len(items)} ponto(s) para você hoje:'
    lines = [('⚠ ' if i['severity'] == 'alta' else '• ') + i['text'] for i in items]
    return _reply(head, lines, [i['action'] for i in items if i.get('action')], topic='resumo')


# ---------- respostas
_FOLLOW_START = re.compile(r'^(e|mas|agora|entao|tambem|so|apenas|e se|e quanto|e quantas|e em|e no|e na|e as|e os|e da|e do)\b')


def _split_requests(question):
    parts = [x.strip() for x in re.split(r';|\bdepois\b|\be tambem\b|\balem disso\b|\?\s+(?=\S)', str(question or '')) if x and x.strip(' ?.!')]
    return parts if len(parts) > 1 and all(len(norm(x).split()) >= 2 for x in parts) else [str(question or '')]


def answer(question, data, name='', ctx=None):
    """Responde a uma frase (ou a várias, separadas por ';' ou 'depois'). `ctx`: memória da conversa (empresa, período, tipo, assunto);
    é atualizada a cada resposta, para o usuário poder perguntar "e em outubro?" ou "e as tomadas?"."""
    ctx = ctx if ctx is not None else {}
    parts = _split_requests(question)
    first = _answer_one(parts[0], data, name, ctx)
    if len(parts) > 1:
        more = []
        for extra in parts[1:]:
            r = _answer_one(extra, data, name, ctx)
            if r.get('confirm') or r.get('run'):
                r = dict(r, confirm=None, run=None, text=r['text'] + ' (Peça isso separado, depois de resolver o pedido acima.)')
            more.append(r)
        first = dict(first, more=more)
    return first


def _answer_one(question, data, name, ctx):
    companies = data['companies']() or []
    protect = {w for c in companies for w in re.findall(r'[a-z0-9]+', norm(c.get('name')))}
    q = fix_typos(question, protect)
    t = norm(q)
    if re.match(r'^(de novo|repita|repete|mais uma vez|outra vez)\b', t) and ctx.get('last_question'):
        q = ctx['last_question']; t = norm(q)
    intent = detect_intent(q)
    per_in_q = parse_period(q, data['today']()); comp_in_q = match_companies(q, companies); kind_in_q = _kind_from_text(t)
    follow = bool(_FOLLOW_START.match(t)) or (len(t.split()) <= 5 and bool(per_in_q or comp_in_q or kind_in_q))
    if intent in ('desconhecido', 'vazio') and ctx.get('topic') and (follow or per_in_q or comp_in_q or kind_in_q) and t:
        intent = ctx['topic']                                     # "e em outubro?" / "e as tomadas?" / "e da outra empresa?": mesmo assunto, novo detalhe
    if intent in ('total_nfse', 'contagem', 'canceladas', 'top_clientes', 'top_fornecedores', 'maiores_notas', 'comparar') and follow and not kind_in_q and ctx.get('kind') and intent == ctx.get('topic'):
        q = q + ' ' + {'Saída': 'prestadas', 'Entrada': 'tomadas'}.get(ctx['kind'], '')
    if t and not t.startswith('de novo'): ctx['last_question'] = question
    reply = _dispatch(intent, q, t, data, name, ctx)
    for k, v in (reply.get('ctx') or {}).items():
        ctx[k] = v
    if reply.get('topic') in ('total', 'contagem', 'canceladas', 'top', 'maiores', 'comparar'):
        ctx['topic'] = {'total': 'total_nfse', 'contagem': 'contagem', 'canceladas': 'canceladas', 'top': ctx.get('topic_top') or ctx.get('topic'), 'maiores': 'maiores_notas', 'comparar': 'comparar'}[reply['topic']]
    return reply


def _dispatch(intent, question, t, data, name, ctx):
    if intent == 'vazio':
        return _reply('Pode perguntar: por exemplo "quanto a CREATIVE HUB prestou em setembro?" ou "quais notas canceladas eu já exportei?".', topic='ajuda')
    if intent == 'ajuda': return _help()
    if intent == 'resumo': return render_briefing(daily_briefing(data), name)
    if intent.startswith('piloto'): return _a_piloto(intent)
    if intent == 'ir':
        for screen, words in SCREENS.items():
            if any(w in t for w in words):
                return _reply(f'Abrindo {SCREEN_LABEL[screen]}.', topic='ir') | {'run': _goto(screen)}
        return _reply('Para qual tela? Posso abrir NFS-e, Documentos Fiscais, Empresas, Auditoria, Histórico, Pendências, Certificado, Relatórios, Início ou Buscar XML.', topic='duvida')
    if intent == 'sem_busca': return _a_sem_busca(data)
    if intent == 'certificados': return _a_certificados(data)
    if intent == 'nao_exportadas': return _a_nao_exportadas(data)
    if intent in ('acao_buscar', 'acao_buscar_salvar', 'acao_todas'): return _a_buscar(question, data, intent, ctx)
    if intent == 'ranking_empresas': return _a_ranking_empresas(question, data, ctx)
    comp, doubt = _resolve_company(question, data, ctx)
    if doubt: return doubt
    if intent == 'acao_relatorio': return _a_relatorio(question, data, comp, ctx)
    if intent == 'canceladas': return _a_canceladas(question, data, comp, ctx)
    if intent == 'total_nfse': return _a_total_nfse(question, data, comp, ctx)
    if intent == 'contagem': return _a_contagem(question, data, comp, ctx)
    if intent in ('top_clientes', 'top_fornecedores'): return _a_top_partes(question, data, comp, ctx, 'Saída' if intent == 'top_clientes' else 'Entrada')
    if intent == 'maiores_notas': return _a_maiores_notas(question, data, comp, ctx)
    if intent == 'comparar': return _a_comparar(question, data, comp, ctx)
    return _reply('Ainda não sei responder isso. Eu consigo falar de valores e quantidades de notas, maiores clientes e fornecedores, comparações entre meses, canceladas, empresas sem busca e certificados, e também fazer buscas, relatórios e ligar o piloto automático.',
                  actions=[{'label': 'Ver o resumo do dia', 'kind': 'briefing'}, {'label': 'O que você sabe fazer?', 'kind': 'help'}], topic='desconhecido')


def _help():
    lines = ['"Quanto a CREATIVE HUB prestou em setembro?" — valores de NFS-e prestadas ou tomadas',
             '"Quantas notas tem a CREATIVE HUB este mês?" — quantidades por tipo de nota',
             '"Quais notas canceladas eu já exportei?" — canceladas, com as notas por trás',
             '"Que empresas estão sem busca?" — quem não busca há dias',
             '"Algum certificado vencendo?" — validade dos certificados',
             '"Busque e salve tudo da CREATIVE HUB" — eu faço a busca e salvo os XMLs (peço confirmação)',
             '"Gere o relatório de setembro" — relatório mensal em PDF',
             '"Abra Documentos" — vou para a tela; "Resumo do dia" — o que precisa de você']
    return _reply('Eu consulto os seus dados aqui no computador e posso fazer algumas tarefas por você. Exemplos do que dá para pedir:', lines, topic='ajuda')


def _sum_rows(rows):
    ok = [r for r in rows if r.get('status') != 'Cancelado']
    bad = [r for r in rows if r.get('status') == 'Cancelado']
    tot = lambda xs: sum((Decimal(str(r.get('value') or 0)) for r in xs), Decimal('0.00'))
    return ok, bad, tot(ok), tot(bad)


def _note_line(r):
    kind = 'Prestada' if r.get('direction') == 'Saída' else 'Tomada'
    flag = ' — cancelada' if r.get('status') == 'Cancelado' else ''
    exp = ' (já exportada)' if r.get('exported') else ''
    return f'NFS-e {r.get("number") or "s/n"} • {br_date(r.get("issued_at"))} • {kind} • {brl(r.get("value"))}{flag}{exp}'


def _a_total_nfse(question, data, comp, ctx=None):
    if comp is None:
        return _reply('De qual empresa? Diga o nome ou o CNPJ.', topic='duvida')
    t = norm(question); per = _period_or_default(question, data, ctx)
    df, dt, label = per
    rows = data['nfse_rows'](comp['cnpj'], df.isoformat(), dt.isoformat(), 5000)
    want = _kind_from_text(t)
    shown = [r for r in rows if not want or r.get('direction') == want]
    ok, bad, total, canc_total = _sum_rows(shown)
    kind_label = {'Saída': 'prestou', 'Entrada': 'tomou', '': 'movimentou'}[want]
    name = comp['name']
    if not shown:
        return _reply(f'Não encontrei NFS-e {"prestadas" if want == "Saída" else "tomadas" if want == "Entrada" else ""} de {name} em {label}. Se você ainda não buscou, posso fazer isso.'.replace('  ', ' '),
                      actions=[{'label': 'Buscar e salvar tudo', 'kind': 'nfse_search_save', 'cnpj': comp['cnpj']}], topic='total', ctx={'company': comp['cnpj'], 'period': [df.isoformat(), dt.isoformat(), label], 'kind': want})
    text = f'{name} {kind_label} {brl(total)} em {label}: {len(ok)} nota(s) autorizada(s).'
    if want == '':
        p = [r for r in ok if r.get('direction') == 'Saída']; tm = [r for r in ok if r.get('direction') == 'Entrada']
        text = f'{name} em {label}: prestou {brl(sum((Decimal(str(r["value"] or 0)) for r in p), Decimal("0")))} ({len(p)} nota(s)) e tomou {brl(sum((Decimal(str(r["value"] or 0)) for r in tm), Decimal("0")))} ({len(tm)} nota(s)).'
    if bad:
        text += f' Há {len(bad)} cancelada(s) ({brl(canc_total)}), que não entram na soma.'
    lines = [_note_line(r) for r in sorted(shown, key=lambda r: str(r.get('issued_at')))[:8]]
    if len(shown) > 8: lines.append(f'… e mais {len(shown) - 8} nota(s).')
    actions = [{'label': 'Gerar relatório mensal', 'kind': 'nfse_report', 'cnpj': comp['cnpj'], 'df': df.isoformat(), 'dt': dt.isoformat()},
               {'label': 'Abrir NFS-e', 'kind': 'goto', 'screen': 'nfse', 'cnpj': comp['cnpj'], 'df': df.isoformat(), 'dt': dt.isoformat()}]
    how = f'somei o valor das NFS-e {"prestadas" if want == "Saída" else "tomadas" if want == "Entrada" else "prestadas e tomadas"} emitidas de {br_date(df.isoformat())} a {br_date(dt.isoformat())}; as canceladas ficam fora da soma.'
    return _reply(text, lines, actions, topic='total', how=how, suggest=['Comparar com o período anterior', 'Quem são os maiores clientes?'],
                  ctx={'company': comp['cnpj'], 'period': [df.isoformat(), dt.isoformat(), label], 'kind': want})


def _a_contagem(question, data, comp, ctx=None):
    if comp is None:
        return _reply('De qual empresa? Diga o nome ou o CNPJ.', topic='duvida')
    df, dt, label = _period_or_default(question, data, ctx)
    summ = data['summary'](comp['cnpj'], df.isoformat(), dt.isoformat())
    by = {}
    for r in summ:
        if r.get('status') == 'Evento': continue
        k = (r['family'], r.get('direction') or '')
        b = by.setdefault(k, {'n': 0, 'canc': 0, 'total': Decimal('0')})
        b['n'] += int(r['count'])
        if r.get('status') == 'Cancelado': b['canc'] += int(r['count'])
        else: b['total'] += Decimal(str(r.get('total') or 0))
    if not by:
        return _reply(f'{comp["name"]} não tem notas guardadas em {label}.', topic='contagem', ctx={'company': comp['cnpj'], 'period': [df.isoformat(), dt.isoformat(), label]})
    lines = []
    for (fam, dire), b in sorted(by.items()):
        d = ('prestadas' if dire == 'Saída' else 'tomadas') if fam == 'nfse' else ('saídas' if dire == 'Saída' else 'entradas' if dire == 'Entrada' else '')
        lines.append(f'{FAMILY_LABEL.get(fam, fam)} {d}: {b["n"]} nota(s) • {brl(b["total"])}' + (f' • {b["canc"]} cancelada(s)' if b['canc'] else ''))
    n = sum(b['n'] for b in by.values())
    return _reply(f'{comp["name"]} tem {n} nota(s) em {label}:', lines, [{'label': 'Abrir Documentos Fiscais', 'kind': 'goto', 'screen': 'documents'}], topic='contagem',
                  how=f'contei as notas guardadas no Arquivo Fiscal Local de {br_date(df.isoformat())} a {br_date(dt.isoformat())}, por tipo e movimentação (eventos não contam).',
                  suggest=['Quanto prestou nesse período?'], ctx={'company': comp['cnpj'], 'period': [df.isoformat(), dt.isoformat(), label]})


def _a_canceladas(question, data, comp, ctx=None):
    only_exp = _has(norm(question), 'exportad')
    rows_all = []
    if comp is not None:
        per = parse_period(question, data['today']()) or ((date.fromisoformat(ctx['period'][0]), date.fromisoformat(ctx['period'][1]), ctx['period'][2]) if (ctx or {}).get('period') and _has(norm(question), 'mesmo', 'esse periodo', 'nesse periodo') else None)
        df, dt = (per[0].isoformat(), per[1].isoformat()) if per else ('', '')
        rows_all = data['nfse_rows'](comp['cnpj'], df, dt, 5000)
    canc = [r for r in rows_all if r.get('status') == 'Cancelado' and (r.get('exported') or not only_exp)]
    if comp is None or not canc:
        gl = data['cancelled_exported']() or []
        n = sum(int(x['count']) for x in gl)
        if n:
            return _reply(f'No total, {n} nota(s) já exportada(s) foram canceladas depois. Confira antes de lançar.' if comp is None else f'{comp["name"]} não tem NFS-e canceladas {"já exportadas " if only_exp else ""}nesse período. No total do Exato há {n} nota(s) exportada(s) que foram canceladas.',
                          actions=[{'label': 'Ver canceladas exportadas', 'kind': 'docs_cancelled_exported'}], topic='canceladas')
        return _reply('Nenhuma nota exportada foi cancelada depois. Está tudo certo.' if only_exp else 'Não encontrei notas canceladas.', topic='canceladas')
    ok, bad, total, canc_total = _sum_rows(canc)
    lines = [_note_line(r) for r in canc[:8]] + ([f'… e mais {len(canc) - 8}.'] if len(canc) > 8 else [])
    return _reply(f'{comp["name"]} tem {len(canc)} NFS-e cancelada(s){" já exportada(s)" if only_exp else ""}, somando {brl(canc_total + total)}:', lines,
                  [{'label': 'Ver canceladas exportadas', 'kind': 'docs_cancelled_exported'}], topic='canceladas', ctx={'company': comp['cnpj']})


def _a_sem_busca(data):
    today = data['today'](); runs = data['last_runs']() or {}; rows = []
    for c in data['companies']() or []:
        cnpj = re.sub(r'\D', '', str(c['cnpj'])); ok = (runs.get(cnpj) or {}).get('ok_at')
        try: days = (today - date.fromisoformat(str(ok)[:10])).days if ok else None
        except Exception: days = None
        rows.append((9999 if days is None else days, c['name'], days))
    late = [r for r in sorted(rows, reverse=True) if r[0] >= 7]
    if not late:
        return _reply('Todas as empresas buscaram nos últimos 7 dias.', topic='sem_busca')
    lines = [f'{n} — {"nunca buscou" if d is None else f"última busca há {d} dia(s)"}' for _, n, d in late[:12]]
    return _reply(f'{len(late)} empresa(s) estão sem busca há 7 dias ou mais:', lines, [{'label': 'Buscar NFS-e de todas e salvar', 'kind': 'nfse_all_save'}], topic='sem_busca')


def _a_certificados(data):
    today = data['today'](); certs = data['certs']() or []
    if not certs:
        return _reply('Não encontrei certificados instalados neste computador.', actions=[{'label': 'Abrir Certificado', 'kind': 'cert_list'}], topic='certificados')
    rows = []
    for c in certs:
        try: rows.append(((date.fromisoformat(str(c['not_after'])[:10]) - today).days, c.get('name') or 'Certificado'))
        except Exception: pass
    rows.sort()
    near = [r for r in rows if r[0] <= 60]
    lines = [f'{n} — {"vencido há " + str(-d) + " dia(s)" if d < 0 else "vence em " + str(d) + " dia(s)"}' for d, n in (near or rows)[:10]]
    head = f'{len([r for r in rows if r[0] < 0])} vencido(s) e {len([r for r in rows if 0 <= r[0] <= 30])} vencendo em 30 dias:' if near else 'Nenhum certificado vence nos próximos 60 dias. Os mais próximos:'
    return _reply(head, lines, [{'label': 'Abrir Certificado', 'kind': 'cert_list'}], topic='certificados')


def _a_nao_exportadas(data):
    names = {re.sub(r'\D', '', str(c['cnpj'])): c['name'] for c in data['companies']() or []}
    items = data['unexported']() or []
    n = sum(int(x['count']) for x in items)
    if not n:
        return _reply('Tudo o que está no Arquivo Fiscal Local já foi salvo na pasta dos clientes.', topic='nao_exportadas')
    agg = {}
    for x in items:
        agg[x['cnpj']] = agg.get(x['cnpj'], 0) + int(x['count'])
    lines = [f'{names.get(re.sub(r"\D", "", str(c)), fmt_cnpj(c))}: {k} nota(s)' for c, k in sorted(agg.items(), key=lambda kv: -kv[1])[:10]]
    return _reply(f'{n} nota(s) ainda não foram salvas na pasta dos clientes:', lines, [{'label': 'Abrir Documentos Fiscais', 'kind': 'goto', 'screen': 'documents'}], topic='nao_exportadas')


def _a_buscar(question, data, intent, ctx=None):
    if intent == 'acao_todas':
        return _reply('Vou buscar as NFS-e de todas as empresas que têm certificado neste computador e salvar os XMLs novos na pasta dos clientes. Posso começar?',
                      confirm={'kind': 'nfse_all_save', 'label': 'Buscar de todas e salvar'}, topic='acao')
    comp, doubt = _resolve_company(question, data, ctx)
    if doubt: return doubt
    if comp is None:
        return _reply('De qual empresa? Diga o nome ou o CNPJ.', topic='duvida')
    t2 = ' ' + norm(question) + ' '
    for w in re.findall(r'[a-z0-9]+', norm(comp['name'])):      # "tudo" no nome da empresa (AGRO TUDO) não é o pedido de salvar tudo
        t2 = t2.replace(f' {w} ', ' ')
    save = _has(t2, 'salv', 'tudo', 'exporte', 'exportar')
    kind = 'nfse_search_save' if save else 'nfse_search'
    verb = 'buscar as NFS-e' + (' e salvar os XMLs novos na pasta dos clientes' if kind == 'nfse_search_save' else '')
    return _reply(f'Vou {verb} de {comp["name"]} ({fmt_cnpj(comp["cnpj"])}). Posso começar?', confirm={'kind': kind, 'cnpj': comp['cnpj'], 'label': 'Sim, pode começar'}, topic='acao')


def _a_relatorio(question, data, comp, ctx=None):
    if comp is None:
        return _reply('De qual empresa é o relatório? Diga o nome ou o CNPJ.', topic='duvida')
    p = parse_period(question, data['today']()) or (((date.fromisoformat(ctx['period'][0]), date.fromisoformat(ctx['period'][1]), ctx['period'][2])) if (ctx or {}).get('period') else None)
    if p is None:
        today = data['today'](); last = today.replace(day=1) - timedelta(days=1); a, b = _month_range(last.year, last.month); p = (a, b, f'{MONTH_NAMES[a.month - 1]}/{a.year} (mês anterior)')
    df, dt, label = p
    return _reply(f'Vou gerar o relatório mensal de NFS-e de {comp["name"]} para {label}.', confirm={'kind': 'nfse_report', 'cnpj': comp['cnpj'], 'df': df.isoformat(), 'dt': dt.isoformat(), 'label': 'Gerar o relatório'}, topic='acao')


# ---------- V156: perguntas novas, explicações e piloto automático
def _party_rows(data, comp, df, dt, direction):
    rows = data['nfse_parties'](comp['cnpj'], df.isoformat(), dt.isoformat(), 4000) if 'nfse_parties' in data else []
    return [r for r in rows if r.get('direction') == direction and r.get('status') != 'Cancelado']


def _a_top_partes(question, data, comp, ctx, direction):
    if comp is None:
        return _reply('De qual empresa? Diga o nome ou o CNPJ.', topic='duvida')
    df, dt, label = _period_or_default(question, data, ctx, default='mes')
    if parse_period(question, data['today']()) is None and not (ctx or {}).get('period'):
        today = data['today'](); df, dt = date(today.year, 1, 1), today; label = f'{today.year} até hoje'
    rows = _party_rows(data, comp, df, dt, direction)
    quem = 'clientes' if direction == 'Saída' else 'fornecedores'
    base_ctx = {'company': comp['cnpj'], 'period': [df.isoformat(), dt.isoformat(), label], 'kind': direction, 'topic_top': 'top_clientes' if direction == 'Saída' else 'top_fornecedores'}
    if not rows:
        return _reply(f'Não encontrei NFS-e {"prestadas" if direction == "Saída" else "tomadas"} de {comp["name"]} em {label} para montar o ranking de {quem}.', topic='top', ctx=base_ctx)
    agg = {}
    for r in rows:
        key = r.get('party_doc') or r.get('party_name') or '—'
        b = agg.setdefault(key, {'name': r.get('party_name') or fmt_cnpj(key), 'n': 0, 'total': Decimal('0')}); b['n'] += 1; b['total'] += Decimal(str(r.get('value') or 0))
    grand = sum((b['total'] for b in agg.values()), Decimal('0')) or Decimal('1')
    top = sorted(agg.values(), key=lambda b: -b['total'])[:5]
    lines = [f'{i}. {b["name"]} — {brl(b["total"])} ({b["n"]} nota(s), {b["total"] * 100 / grand:.0f}% do total)' for i, b in enumerate(top, 1)]
    return _reply(f'Maiores {quem} de {comp["name"]} em {label} (total {brl(grand)} em {len(agg)} {quem[:-1] if len(agg) == 1 else quem}):', lines,
                  [{'label': 'Abrir NFS-e', 'kind': 'goto', 'screen': 'nfse', 'cnpj': comp['cnpj'], 'df': df.isoformat(), 'dt': dt.isoformat()}],
                  topic='top', how=f'agrupei as NFS-e {"prestadas" if direction == "Saída" else "tomadas"} autorizadas por {"tomador" if direction == "Saída" else "prestador"} e somei os valores; canceladas ficam fora.',
                  suggest=['Comparar com o período anterior'], ctx=base_ctx)


def _a_maiores_notas(question, data, comp, ctx):
    if comp is None:
        return _reply('De qual empresa? Diga o nome ou o CNPJ.', topic='duvida')
    t = norm(question); df, dt, label = _period_or_default(question, data, ctx)
    want = _kind_from_text(t)
    rows = [r for r in data['nfse_rows'](comp['cnpj'], df.isoformat(), dt.isoformat(), 5000) if r.get('status') != 'Cancelado' and (not want or r.get('direction') == want)]
    ctxu = {'company': comp['cnpj'], 'period': [df.isoformat(), dt.isoformat(), label], 'kind': want}
    if not rows:
        return _reply(f'Não encontrei NFS-e de {comp["name"]} em {label}.', topic='maiores', ctx=ctxu)
    top = sorted(rows, key=lambda r: -Decimal(str(r.get('value') or 0)))[:5]
    return _reply(f'As {len(top)} maiores NFS-e de {comp["name"]} em {label}:', [_note_line(r) for r in top], topic='maiores',
                  how='ordenei as notas autorizadas do período pelo valor, da maior para a menor.', ctx=ctxu)


def _previous_period(df, dt):
    if df.day == 1 and dt == _month_range(df.year, df.month)[1] and df.month == dt.month:
        last = df - timedelta(days=1); a, b = _month_range(last.year, last.month); return a, b, f'{MONTH_NAMES[a.month - 1]}/{a.year}'
    span = (dt - df).days + 1; b = df - timedelta(days=1); a = b - timedelta(days=span - 1)
    return a, b, f'{br_date(a.isoformat())} a {br_date(b.isoformat())}'


def _a_comparar(question, data, comp, ctx):
    if comp is None:
        return _reply('De qual empresa? Diga o nome ou o CNPJ.', topic='duvida')
    df, dt, label = _period_or_default(question, data, ctx)
    pa, pb, plabel = _previous_period(df, dt)
    def tot(a, b):
        ok = [r for r in data['nfse_rows'](comp['cnpj'], a.isoformat(), b.isoformat(), 5000) if r.get('status') != 'Cancelado']
        s_ = lambda xs: sum((Decimal(str(r.get('value') or 0)) for r in xs), Decimal('0'))
        return s_([r for r in ok if r.get('direction') == 'Saída']), s_([r for r in ok if r.get('direction') == 'Entrada']), len(ok)
    cp, ct, cn = tot(df, dt); pp, pt, pn = tot(pa, pb)
    def var(new, old):
        if old == 0: return 'sem base para comparar' if new == 0 else 'novo (antes era zero)'
        d = (new - old) * 100 / old; return f'{"+" if d >= 0 else ""}{d:.1f}%'.replace('.', ',')
    lines = [f'Prestadas: {brl(cp)} em {label} × {brl(pp)} em {plabel} → {var(cp, pp)}', f'Tomadas: {brl(ct)} em {label} × {brl(pt)} em {plabel} → {var(ct, pt)}', f'Quantidade de notas: {cn} × {pn}']
    head = f'{comp["name"]}: {label} comparado a {plabel}.'
    return _reply(head, lines, topic='comparar', how='somei as NFS-e autorizadas de cada período (canceladas fora) e calculei a variação percentual do primeiro em relação ao segundo.',
                  ctx={'company': comp['cnpj'], 'period': [df.isoformat(), dt.isoformat(), label]})


def _a_ranking_empresas(question, data, ctx):
    t = norm(question); per = _period_or_default(question, data, ctx); df, dt, label = per
    want = _kind_from_text(t) or 'Saída'; rows = []
    for c in data['companies']() or []:
        ok = [r for r in data['nfse_rows'](c['cnpj'], df.isoformat(), dt.isoformat(), 5000) if r.get('status') != 'Cancelado' and r.get('direction') == want]
        if ok: rows.append((sum((Decimal(str(r.get('value') or 0)) for r in ok), Decimal('0')), len(ok), c['name']))
    if not rows:
        return _reply(f'Nenhuma empresa tem NFS-e {"prestadas" if want == "Saída" else "tomadas"} em {label}.', topic='ranking', ctx={'period': [df.isoformat(), dt.isoformat(), label]})
    rows.sort(reverse=True)
    lines = [f'{i}. {n} — {brl(v)} ({q} nota(s))' for i, (v, q, n) in enumerate(rows[:10], 1)]
    return _reply(f'Empresas por NFS-e {"prestadas" if want == "Saída" else "tomadas"} em {label} (maior primeiro):', lines, topic='ranking',
                  how='somei as NFS-e autorizadas de cada empresa no período; as canceladas ficam fora.', ctx={'period': [df.isoformat(), dt.isoformat(), label], 'kind': want})


def _a_piloto(intent):
    if intent == 'piloto_on':
        return _reply('O piloto automático faz a rotina do dia sozinho: busca as NFS-e das empresas com certificado, salva os XMLs novos e gera o relatório do mês anterior. Ele só roda com o Exato aberto. Quer ligar?',
                      confirm={'kind': 'pilot_on', 'label': 'Ligar o piloto automático'}, actions=[{'label': 'Configurar o piloto', 'kind': 'pilot_dialog'}], topic='piloto')
    if intent == 'piloto_off':
        return _reply('Vou desligar o piloto automático. Você pode ligar de novo quando quiser.', confirm={'kind': 'pilot_off', 'label': 'Desligar o piloto'}, topic='piloto')
    if intent == 'piloto_agora':
        return _reply('Vou rodar a rotina do piloto agora (buscar, salvar e gerar relatório do mês anterior). Posso começar?', confirm={'kind': 'pilot_run', 'label': 'Rodar agora'}, topic='piloto')
    return _reply('Abrindo o piloto automático: lá você liga, escolhe o horário e vê o que ele já fez.', actions=[{'label': 'Abrir o piloto automático', 'kind': 'pilot_dialog'}], topic='piloto') | {'run': {'kind': 'pilot_dialog'}}


def _extend_vocab():
    """O vocabulário de correção inclui todas as palavras que o próprio detector de intenção usa (assim "exportar" não vira "exportada")."""
    import inspect
    global VOCAB
    words = set(VOCAB)
    for fn in (detect_intent, _kind_from_text):
        for lit in re.findall(r"'([^']+)'", inspect.getsource(fn)):
            words.update(w for w in re.findall(r'[a-z]{5,}', norm(lit)))
    VOCAB = sorted(words)


_extend_vocab()
