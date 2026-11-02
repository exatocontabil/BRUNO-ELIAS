"""Fechamento do mês no Repositório (V174). Sem Tkinter.

Quando um mês de uma empresa para de receber notas, o Exato "fecha" o mês sozinho: grava no Repositório, na pasta
`<CNPJ> - <Empresa>\\<Ano>\\<Mês>\\Fechamento\\`, o relatório do mês em PDF (NF-e/NFC-e/CT-e e, à parte, o das NFS-e com alíquota e ISS)
e os ZIPs de importação (um por tipo e movimentação, mais o de eventos). O arquivo `.fechamento.json` marca o mês como fechado.

Regras: o mês já acabou; a busca já passou do fim dele (quando o programa sabe); nenhuma nota nova chegou há `dias` dias; tudo do mês
já está copiado no servidor. Nunca sobrescreve: se depois chegar uma nota atrasada, o mês é "revisado" (novos arquivos com a data da revisão,
os antigos ficam). Só um computador fecha cada mês de cada vez (arquivo `.fechando`, que expira em 30 minutos).
"""
from __future__ import annotations
import json, os, re, shutil, socket, tempfile, time, zipfile, sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import exato_repositorio as repo
import exato_zip_importacao as zipimp
import exato_fechamento_pdf as fpdf

PASTA = 'Fechamento'
MARCA = '.fechamento.json'
RESERVA = '.fechando'
RESERVA_VALIDADE = 30 * 60
DIAS_PADRAO = 5
LIMITE_RODADA = 40


# ------------------------------------------------------------------ o que pode ser fechado
def _mes_atual(hoje=None):
    return (hoje or datetime.now()).strftime('%Y-%m')


def meses(db_path, hoje=None):
    """Situação de cada empresa/mês conhecido por este computador (só os meses já encerrados):
    [{'cnpj','nome','mes','notas','ultima','faltam','assinatura'}]. `faltam` = documentos do mês ainda não copiados para o servidor."""
    hoje = hoje or datetime.now()
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        repo.preparar_banco(conn)
        linhas = conn.execute(
            f"""SELECT d.cnpj, COALESCE(c.name,''), {repo._SQL_MES} AS mes,
                       SUM(CASE WHEN COALESCE(d.status,'')<>'Evento' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN COALESCE(d.status,'')<>'Evento' THEN length(d.xml) ELSE 0 END),
                       SUM(CASE WHEN d.status='Cancelado' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN COALESCE(d.status,'')='Evento' THEN 1 ELSE 0 END),
                       MAX(d.first_seen_at),
                       SUM(CASE WHEN r.copiado_em IS NULL THEN 1 ELSE 0 END)
                FROM documents d LEFT JOIN companies c ON c.cnpj=d.cnpj LEFT JOIN repositorio_copias r ON r.doc_id=d.doc_id
                WHERE COALESCE(r.removido,0)=0 GROUP BY d.cnpj, mes""").fetchall()
    finally:
        conn.close()
    saida = []
    for cnpj, nome, mes, notas, tam, canc, ev, ultima, faltam in linhas:
        if not re.fullmatch(r'\d{4}-\d{2}', str(mes)) or str(mes) >= _mes_atual(hoje): continue
        saida.append({'cnpj': re.sub(r'\D', '', str(cnpj or '')), 'nome': nome, 'mes': mes, 'notas': int(notas or 0), 'ultima': ultima or '', 'faltam': int(faltam or 0),
                      'assinatura': f'{int(notas or 0)}|{int(tam or 0)}|{int(canc or 0)}|{int(ev or 0)}'})
    return saida


def motivo(m, dias=DIAS_PADRAO, hoje=None, coberto=None):
    """'' se o mês pode ser fechado agora; senão, por que ainda não (em português claro). `coberto(cnpj, mes) -> bool | None`."""
    hoje = hoje or datetime.now()
    if not m['notas']: return 'Sem notas neste computador'
    if m['faltam']: return f"Faltam {m['faltam']} documento(s) no servidor"
    try:
        quieto_ate = datetime.fromisoformat(str(m['ultima'])[:19]) + timedelta(days=dias)
        if quieto_ate > hoje: return f"Chegou nota nova em {str(m['ultima'])[8:10]}/{str(m['ultima'])[5:7]}: fecha em {quieto_ate.strftime('%d/%m')} se não vier mais nenhuma"
    except ValueError:
        pass
    if coberto is not None:
        try:
            if coberto(m['cnpj'], m['mes']) is False: return 'A busca ainda não passou do fim do mês'
        except Exception:
            pass
    return ''


def candidatos(db_path, dias=DIAS_PADRAO, hoje=None, forcar=False, coberto=None):
    """Meses prontos para fechar: encerrados, sem nota nova há `dias` dias, totalmente copiados para o servidor e (se `coberto`) já cobertos pela busca.
    `forcar` ignora a espera e a cobertura (botão "Fechar agora"), mas nunca fecha mês com documento ainda sem copiar."""
    hoje = hoje or datetime.now(); saida = []
    for m in meses(db_path, hoje):
        if not m['notas'] or m['faltam']: continue
        if not forcar and motivo(m, dias, hoje, coberto): continue
        saida.append(m)
    return sorted(saida, key=lambda c: (c['mes'], c['cnpj']))


def motivos(db_path, dias=DIAS_PADRAO, hoje=None, coberto=None):
    """{(cnpj, mês): texto} de todos os meses conhecidos: '' = pronto para fechar."""
    return {(m['cnpj'], m['mes']): motivo(m, dias, hoje, coberto) for m in meses(db_path, hoje)}


# ------------------------------------------------------------------ pasta do fechamento, marcador e reserva
def _pasta_fechamento(pasta_repo, pasta_empresa, mes):
    ano, mm = mes.split('-')
    return Path(pasta_repo) / pasta_empresa / ano / mm / PASTA


def ler_marca(pasta_fech):
    try:
        with open(repo._longo(Path(pasta_fech) / MARCA), 'r', encoding='utf-8') as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else None
    except Exception:
        return None


def _reservar(pasta_fech):
    """True se ESTE computador pode fechar agora; False se outro está fechando (reserva recente)."""
    os.makedirs(repo._longo(pasta_fech), exist_ok=True)
    alvo = repo._longo(Path(pasta_fech) / RESERVA)
    for _ in range(2):
        try:
            fd = os.open(alvo, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w') as f: f.write(f'{socket.gethostname()} {datetime.now().isoformat(timespec="seconds")}')
            return True
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(alvo) < RESERVA_VALIDADE: return False
                os.remove(alvo)            # reserva esquecida (computador desligou no meio): assume
            except OSError:
                return False
        except OSError:
            return False
    return False


def _liberar(pasta_fech):
    try: os.remove(repo._longo(Path(pasta_fech) / RESERVA))
    except OSError: pass


def _nome_livre(pasta, nome):
    """Nunca sobrescreve: se o nome já existe, acrescenta (2), (3)..."""
    base, ext = os.path.splitext(nome); n = 1; atual = nome
    while os.path.exists(repo._longo(Path(pasta) / atual)):
        n += 1; atual = f'{base} ({n}){ext}'
    return atual


def _guardar(origem, pasta_fech, nome):
    """Copia um arquivo local para o servidor por arquivo temporário + troca (nunca fica pela metade). Devolve o nome final."""
    final = _nome_livre(pasta_fech, nome); destino = Path(pasta_fech) / final; tmp = Path(pasta_fech) / ('.' + final + '.tmp')
    with open(origem, 'rb') as a, open(repo._longo(tmp), 'wb') as b:
        shutil.copyfileobj(a, b, 1024 * 256); b.flush()
        try: os.fsync(b.fileno())
        except Exception: pass
    if os.path.getsize(repo._longo(tmp)) != os.path.getsize(origem): raise OSError('arquivo gravado incompleto')
    os.replace(repo._longo(tmp), repo._longo(destino))
    return final


# ------------------------------------------------------------------ documentos do mês
def _documentos(db_path, cnpj, mes):
    conn = sqlite3.connect(db_path, timeout=30); conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            f"""SELECT d.doc_id,d.cnpj,d.family,d.doc_type,d.direction,d.number,d.series,d.issued_at,d.value,d.status,d.access_key,d.first_seen_at,d.xml
                FROM documents d LEFT JOIN repositorio_copias r ON r.doc_id=d.doc_id
                WHERE d.cnpj=? AND {repo._SQL_MES}=? AND COALESCE(r.removido,0)=0 ORDER BY d.issued_at, d.number""", (cnpj, mes)).fetchall()]
    finally:
        conn.close()


def _direcao_visivel(familia, direcao):
    if familia == 'nfse': return {'Saída': 'Prestados', 'Entrada': 'Tomados'}.get(direcao, direcao or '—')
    return direcao or '—'


def _linhas_relatorio(docs):
    """(linhas NF-e/NFC-e/CT-e do PDF do mês, linhas das NFS-e)."""
    gerais, servicos = [], []
    import exato_nfse_pdf as nfse_pdf
    for d in docs:
        if d['status'] == 'Evento': continue
        situacao = 'Cancelada' if d['status'] == 'Cancelado' else 'Autorizada'
        if d['family'] == 'nfse':
            try: servicos.append(nfse_pdf.report_row_from_xml(bytes(d['xml'] or b''), d['cnpj'], situacao))
            except Exception: pass
            continue
        gerais.append({'family': d['family'], 'direcao': _direcao_visivel(d['family'], d['direction']), 'numero': d['number'], 'serie': d['series'],
                       'data': str(d['issued_at'] or '')[:10], 'chave': re.sub(r'\D', '', str(d['access_key'] or '')), 'valor': d['value'], 'situacao': situacao})
    resumo_nfse = [{'family': 'nfse', 'direcao': r['tipo'] + 's', 'valor': r['valor'], 'situacao': r['situacao']} for r in servicos]
    return gerais + resumo_nfse, servicos


def _montar_zips(docs, cnpj, mes, pasta_tmp, sufixo=''):
    """{nome do ZIP: caminho local}: um ZIP por tipo e movimentação (XMLs soltos) e um de eventos por tipo, com os XMLs vindos do banco."""
    ano, mm = mes.split('-'); grupos = {}
    for d in docs:
        if not bytes(d['xml'] or b''): continue
        tipo = repo.TIPOS.get(str(d['family'] or 'nfe').lower(), str(d['family']).upper())
        if d['status'] == 'Evento':
            chave = f'{cnpj}_{mes}_Eventos-{zipimp._nome(tipo)}'
        else:
            chave = zipimp.nome_do_zip(cnpj, ano, mm, tipo, _direcao_visivel(str(d['family']).lower(), d['direction']))[:-4]
        grupos.setdefault(chave, []).append(d)
    saida = {}
    for chave, itens in sorted(grupos.items()):
        nome = f'{chave}{sufixo}.zip'; caminho = os.path.join(pasta_tmp, nome); usados = set()
        with zipfile.ZipFile(caminho, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for d in itens:
                partes = repo._partes({**d, 'status': d['status'], 'family': d['family'], 'doc_type': d['doc_type']}, 'x')
                n = partes[-1]
                if n in usados: n = f'{Path(n).stem}_{len(usados)}.xml'
                usados.add(n); z.writestr(n, bytes(d['xml']))
        saida[nome] = caminho
    return saida


# ------------------------------------------------------------------ fechar um mês
def fechar_mes(db_path, base, cand, computador=None, nome_empresa=None, logo=None, nome_pasta_empresa=None):
    """Gera os arquivos do fechamento no servidor. `cand` vem de `candidatos`. Devolve
    {'situacao': 'fechado' | 'revisado' | 'igual' | 'ocupado' | 'erro', 'arquivos': [...], 'revisao': n, 'erro': ''}."""
    cnpj, mes = cand['cnpj'], cand['mes']; computador = computador or socket.gethostname()
    res = {'situacao': 'erro', 'arquivos': [], 'revisao': 0, 'erro': ''}
    pasta_repo = repo._pasta_repo(base)
    if repo.BLOQUEADO:          # V182: Exato mais velho que o formato do servidor não grava
        res['erro'] = 'Este Exato está desatualizado: atualize para voltar a gravar no servidor.'; return res
    if not repo.pasta_acessivel(base):
        res['erro'] = 'O servidor não respondeu.'; return res
    pasta_emp = nome_pasta_empresa or repo._Empresas(pasta_repo, nome_empresa).pasta(cnpj, cand.get('nome'))
    pasta_fech = _pasta_fechamento(pasta_repo, pasta_emp, mes)
    marca = ler_marca(pasta_fech)
    if marca and marca.get('assinatura') == cand['assinatura']:
        res['situacao'] = 'igual'; res['revisao'] = int(marca.get('revisao') or 0); return res
    try:
        if not _reservar(pasta_fech):
            res['situacao'] = 'ocupado'; return res
    except OSError as exc:
        res['erro'] = repo.erro_amigavel(exc); return res
    tmp = tempfile.mkdtemp(prefix='exato_fechamento_')
    try:
        marca = ler_marca(pasta_fech)           # relê já com a reserva: outro computador pode ter acabado de fechar
        if marca and marca.get('assinatura') == cand['assinatura']:
            res['situacao'] = 'igual'; res['revisao'] = int(marca.get('revisao') or 0); return res
        revisao = int(marca.get('revisao') or 0) + 1 if marca else 0
        sufixo = f" (revisado {datetime.now().strftime('%Y-%m-%d')})" if revisao else ''
        docs = _documentos(db_path, cnpj, mes)
        gerais, servicos = _linhas_relatorio(docs)
        empresa_nome = (nome_empresa(cnpj, cand.get('nome'))[0] if nome_empresa else cand.get('nome')) or cand.get('nome') or ''
        arquivos = []
        if any(r['family'] != 'nfse' for r in gerais) or not servicos:
            p = os.path.join(tmp, f'Fechamento {mes}{sufixo}.pdf')
            fpdf.gerar_fechamento_pdf(gerais, p, empresa_nome, cnpj, mes, logo, revisao, 'Revisão: chegou nota depois do primeiro fechamento.' if revisao else '')
            arquivos.append((p, os.path.basename(p)))
        if servicos:
            import exato_nfse_pdf as nfse_pdf
            ano, mm = mes.split('-'); p = os.path.join(tmp, f'Fechamento {mes} - NFS-e{sufixo}.pdf')
            nfse_pdf.generate_monthly_report_pdf(servicos, p, empresa_nome, cnpj, f'{mm}/{ano}', logo, f'Fechamento de NFS-e — {mm}/{ano}')
            arquivos.append((p, os.path.basename(p)))
        for nome, caminho in _montar_zips(docs, cnpj, mes, tmp, sufixo).items():
            arquivos.append((caminho, nome))
        gravados = []
        for origem, nome in arquivos:
            gravados.append(_guardar(origem, pasta_fech, nome))
        agora = datetime.now().isoformat(timespec='seconds')
        historico = list((marca or {}).get('historico') or []) + [{'revisao': revisao, 'em': agora, 'por': computador, 'assinatura': cand['assinatura'], 'arquivos': gravados}]
        dados = {'versao': 1, 'cnpj': cnpj, 'mes': mes, 'fechado_em': (marca or {}).get('fechado_em') or agora, 'por': (marca or {}).get('por') or computador,
                 'assinatura': cand['assinatura'], 'notas': cand['notas'], 'revisao': revisao, 'arquivos': gravados, 'historico': historico}
        tmp_marca = Path(pasta_fech) / ('.' + MARCA + '.tmp')
        with open(repo._longo(tmp_marca), 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=1); f.flush()
            try: os.fsync(f.fileno())
            except Exception: pass
        os.replace(repo._longo(tmp_marca), repo._longo(Path(pasta_fech) / MARCA))
        res.update(situacao='revisado' if revisao else 'fechado', arquivos=gravados, revisao=revisao)
        return res
    except Exception as exc:
        res['erro'] = repo.erro_amigavel(exc) or repo.erro_amigavel(repr(exc)) or str(exc)[:120]
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        _liberar(pasta_fech)


# ------------------------------------------------------------------ rodada
def fechar_pendentes(db_path, base, estado, dias=DIAS_PADRAO, forcar=False, computador=None, nome_empresa=None, logo=None, cancelar=None,
                     limite=LIMITE_RODADA, coberto=None, progresso=None):
    """Fecha os meses que podem ser fechados. `estado` ({'cnpj|mes': assinatura}) é a memória deste computador: mês já conferido não volta ao servidor.
    `coberto(cnpj, mes) -> bool` (opcional): a busca já passou do fim do mês. `limite=None`: sem limite (fecha tudo o que estiver pronto).
    Devolve {'fechados','revisados','ocupados','erros','empresas','conferidos','total','feitos_lista','mais'}; `mais` = ainda havia meses prontos (parou no limite)."""
    res = {'fechados': 0, 'revisados': 0, 'ocupados': 0, 'erros': [], 'empresas': set(), 'conferidos': 0, 'total': 0, 'feitos_lista': [], 'mais': False}
    feitos = 0
    fila = [c for c in candidatos(db_path, dias, forcar=forcar, coberto=coberto) if estado.get(f"{c['cnpj']}|{c['mes']}") != c['assinatura']]
    res['total'] = len(fila)
    for cand in fila:
        if cancelar and cancelar(): break
        if limite is not None and feitos >= limite:
            res['mais'] = True; break
        chave = f"{cand['cnpj']}|{cand['mes']}"
        r = fechar_mes(db_path, base, cand, computador, nome_empresa, logo)
        sit = r['situacao']
        if sit in ('fechado', 'revisado', 'igual'):
            estado[chave] = cand['assinatura']; res['empresas'].add(cand['cnpj']); res['feitos_lista'].append((cand['cnpj'], cand['mes'], r.get('revisao', 0)))
            if sit == 'fechado': res['fechados'] += 1; feitos += 1
            elif sit == 'revisado': res['revisados'] += 1; feitos += 1
            else: res['conferidos'] += 1
        elif sit == 'ocupado': res['ocupados'] += 1
        else:
            res['erros'].append(r['erro'] or 'erro')
            if len(res['erros']) >= 3: break          # servidor com problema: para e tenta na próxima rodada
        if progresso:
            try: progresso(dict(res, atual=cand))
            except Exception: pass
    return res


def mes_fechado(base, cnpj, mes, nome_pasta_empresa):
    return ler_marca(_pasta_fechamento(repo._pasta_repo(base), nome_pasta_empresa, mes))
