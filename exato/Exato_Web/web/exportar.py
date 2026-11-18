"""Exportar XMLs em ZIP (Exato Web): por empresa, período livre, tipo e movimentação; ou só as notas novas de uma busca (`desde`).

Regras (pedido do usuário, iguais às do Exato Central Fiscal):
  - o evento da nota (cancelamento) SEMPRE vai junto, na subpasta `Eventos` ao lado da nota, e é procurado pela CHAVE da nota, em qualquer mês;
  - o resumo do evento (`resEvento`) NUNCA entra; o Exato nunca fabrica um XML de evento (se faltar, avisa no AVISOS.txt do ZIP e na tela);
  - dois formatos: "organizado" (Tipo/Movimentação/…, com Eventos ao lado) e "dominio" (um ZIP por mês, tipo e movimentação, XMLs soltos e eventos
    soltos junto, no mesmo padrão do ZIP de importação da Domínio, tudo dentro de um ZIP só);
  - gerado em segundo plano, lendo o banco em lotes (nunca carrega tudo na memória), nunca grava nada fora da pasta de exportações do site.
"""
import json, os, re, secrets, sqlite3, sys, tempfile, threading, time, zipfile
from datetime import datetime
from pathlib import Path

from . import config, nucleo

ID_RE = re.compile(r'^[0-9a-f]{16}$')
ROTULOS = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}
FORMATOS = ('organizado', 'dominio')
LIMITE_NOTAS = 600000
_trava = threading.Lock()


class ExportarErro(Exception): pass


def pasta():
    p = config.DADOS / 'exportacoes'; p.mkdir(parents=True, exist_ok=True); return p


def _salvar(job):
    with _trava:          # gravação atômica: quem lê a lista nunca pega um arquivo pela metade
        alvo = pasta() / f"{job['id']}.json"; tmp = alvo.with_suffix('.tmp'); tmp.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8'); os.replace(tmp, alvo)


def ler(jid):
    if not ID_RE.match(str(jid or '')): return None
    try: return json.loads((pasta() / f'{jid}.json').read_text(encoding='utf-8'))
    except Exception: return None


def recentes(limite=30):
    out = []
    for p in sorted(pasta().glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True)[:limite]:
        try: out.append(json.loads(p.read_text(encoding='utf-8')))
        except Exception: pass
    return out


def caminho_zip(jid):
    j = ler(jid)
    if not j or j.get('estado') != 'pronto': return None
    p = pasta() / f'{jid}.zip'; return p if p.exists() else None


def limpar_antigos(dias=7):
    """Apaga só os ZIPs de exportação (do próprio site) com mais de `dias` dias; os XMLs do banco nunca são tocados."""
    limite = time.time() - dias * 86400
    for p in pasta().glob('*.zip'):
        try:
            if p.stat().st_mtime < limite: p.unlink()
        except OSError: pass


def direcao_visivel(familia, direcao):
    d = str(direcao or '')
    if str(familia).lower() == 'nfse': return {'Saída': 'Prestados', 'Entrada': 'Tomados'}.get(d, d or 'Sem movimentação')
    return d or 'Sem movimentação'


def _nome_arquivo(chave, numero, doc_id):
    chave = re.sub(r'\D', '', str(chave or ''))
    base = chave if chave else re.sub(r'[^0-9A-Za-z_.-]', '_', f'{numero or "sem-numero"}_{doc_id}')[:90]
    return base + '.xml'


def _chave_do_evento(nome):
    m = re.search(r'(\d{44,50})', nome); return m.group(1) if m else ''


def _filtro_sql(f):
    sql = ["cnpj=?", "COALESCE(status,'')<>'Evento'"]; args = [f['empresa']]
    fams = [t for t in f['tipos'] if t in ROTULOS]
    sql.append('family IN (%s)' % ','.join('?' * len(fams))); args += fams
    if f['mov']: sql.append('direction=?'); args.append(f['mov'])
    dia = "substr(COALESCE(NULLIF(issued_at,''),first_seen_at),1,10)"
    if f['de']: sql.append(dia + '>=?'); args.append(f['de'])
    if f['ate']: sql.append(dia + '<=?'); args.append(f['ate'])
    if f['desde']: sql.append('first_seen_at>=?'); args.append(f['desde'])
    return ' AND '.join(sql), args


def _executar(job, f):
    core = nucleo.core(); caminho = pasta() / f"{job['id']}.zip"; tmp_dir = None
    try:
        where, args = _filtro_sql(f); con = sqlite3.connect(str(core.DB_PATH), timeout=60)
        try:
            total = con.execute(f'SELECT COUNT(*) FROM documents WHERE {where}', args).fetchone()[0]
            if not total: raise ExportarErro('Não há notas neste filtro para exportar.')
            if total > LIMITE_NOTAS: raise ExportarErro(f'São {total} notas: divida em períodos menores (limite de {LIMITE_NOTAS} por ZIP).')
            job['total'] = total; _salvar(job)
            empresa = core.db_get_company_name(f['empresa']) or f['empresa']; zip_mod = nucleo.modulo('exato_zip_importacao')
            tmp_dir = tempfile.TemporaryDirectory(prefix='exato_exp_', dir=str(config.DADOS))
            cur = con.execute(f"SELECT doc_id, family, direction, number, access_key, status, substr(COALESCE(NULLIF(issued_at,''),first_seen_at),1,7) AS ym, xml FROM documents WHERE {where} ORDER BY ym, family, direction, issued_at, number", args)
            resumo = {'notas': 0, 'eventos': 0, 'canceladas': 0, 'sem_evento': [], 'sem_xml': 0}
            grupo_atual = None; itens = []          # itens: (nome, bytes, chave, status) do grupo (mês, tipo, movimentação)
            with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as out:
                def fechar(grupo, lista):
                    if not lista: return
                    ym, fam, direc = grupo; tipo = ROTULOS.get(fam, fam.upper()); dv = direcao_visivel(fam, direc)
                    canc = sorted({c for (_n, _b, c, st) in lista if st == 'Cancelado' and c})
                    eventos = []
                    if canc:
                        try: eventos = list(core._zip_eventos(f['empresa'], canc) or [])          # eventos pela CHAVE da nota, em qualquer mês; sem resumo (mesma rotina do ZIP da Domínio no Central Fiscal)
                        except Exception: eventos = []
                    com_evento = {_chave_do_evento(n) for n, _d in eventos if _d}
                    resumo['canceladas'] += len(canc); resumo['eventos'] += len([1 for _n, d in eventos if d])
                    resumo['sem_evento'] += [(tipo, dv, c) for c in canc if c not in com_evento]
                    if f['formato'] == 'dominio':
                        ano, mes = (ym.split('-') + ['00'])[:2]; nome_zip = zip_mod.nome_do_zip(f['empresa'], ano if re.fullmatch(r'\d{4}', ano) else 'Sem-data', mes, tipo, dv)
                        interno = Path(tmp_dir.name) / nome_zip
                        with zipfile.ZipFile(interno, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                            usados = set()
                            for nome, dados, _c, _s in lista:
                                n = nome if nome not in usados else f'{Path(nome).stem}_{len(usados)}.xml'; usados.add(n); z.writestr(n, dados)
                            for nome, dados in eventos:
                                if dados: n = nome if nome not in usados else f'evento_{len(usados)}_{nome}'; usados.add(n); z.writestr(n, dados)
                        out.write(interno, nome_zip, compress_type=zipfile.ZIP_STORED); interno.unlink(missing_ok=True)
                    else:
                        usados = set(); base = f'{tipo}/{dv}'
                        for nome, dados, _c, _s in lista:
                            n = nome if nome not in usados else f'{Path(nome).stem}_{len(usados)}.xml'; usados.add(n); out.writestr(f'{base}/{n}', dados)
                        for nome, dados in eventos:
                            if dados: n = nome if nome not in usados else f'evento_{len(usados)}_{nome}'; usados.add(n); out.writestr(f'{base}/Eventos/{n}', dados)
                feitos = 0; ultimo_salvo = time.time()
                for doc_id, fam, direc, num, chave, status, ym, xml in cur:
                    grupo = (ym or 'Sem-data', str(fam or ''), str(direc or ''))
                    if grupo != grupo_atual:
                        if grupo_atual is not None: fechar(grupo_atual, itens)
                        grupo_atual, itens = grupo, []
                    feitos += 1
                    if not xml: resumo['sem_xml'] += 1
                    else:
                        itens.append((_nome_arquivo(chave, num, doc_id), xml if isinstance(xml, bytes) else (xml.encode('utf-8') if isinstance(xml, str) else bytes(xml)), re.sub(r'\D', '', str(chave or '')), status)); resumo['notas'] += 1
                    if time.time() - ultimo_salvo > 1.5: job['feito'] = feitos; _salvar(job); ultimo_salvo = time.time()
                if grupo_atual is not None: fechar(grupo_atual, itens)
                linhas = [f'Exato Web — exportação de XMLs', f'Empresa: {empresa} ({f["empresa"]})', f'Gerado em: {datetime.now():%d/%m/%Y %H:%M}',
                          'Período: ' + (f"{f['de'] or 'início'} a {f['ate'] or 'hoje'}" if not f['desde'] else f"notas novas desde {f['desde'].replace('T', ' ')}"),
                          f"Tipos: {', '.join(ROTULOS[t] for t in f['tipos'] if t in ROTULOS)}", f"Movimentação: {f['mov'] or 'entrada e saída'}",
                          f"Formato: {'um ZIP por mês, tipo e movimentação (padrão da Domínio)' if f['formato'] == 'dominio' else 'pastas por tipo e movimentação, com a subpasta Eventos ao lado das notas'}",
                          '', f"XMLs de notas: {resumo['notas']}", f"XMLs de eventos (cancelamentos das notas canceladas): {resumo['eventos']}", f"Notas canceladas no ZIP: {resumo['canceladas']}"]
                if resumo['sem_xml']: linhas.append(f"Notas sem o XML guardado (ficaram de fora): {resumo['sem_xml']}")
                if resumo['sem_evento']:
                    linhas += ['', f"ATENÇÃO: {len(resumo['sem_evento'])} nota(s) cancelada(s) SEM o XML do cancelamento. O Exato nunca inventa esse arquivo: busque de novo a empresa (ou peça o evento ao cliente).", 'Notas:'] + [f'  {t} / {d}: {c}' for t, d, c in resumo['sem_evento'][:500]]
                    if len(resumo['sem_evento']) > 500: linhas.append(f"  ... e mais {len(resumo['sem_evento']) - 500}")
                out.writestr('AVISOS.txt', '\n'.join(linhas) + '\n')
        finally:
            con.close()
        job.update(estado='pronto', fim=datetime.now().isoformat(timespec='seconds'), empresa=empresa, feito=job['total'], notas=resumo['notas'], eventos=resumo['eventos'], canceladas=resumo['canceladas'],
                   sem_evento=len(resumo['sem_evento']), sem_xml=resumo['sem_xml'], tamanho=caminho.stat().st_size)
    except ExportarErro as e:
        caminho.unlink(missing_ok=True); job.update(estado='erro', erro=str(e))
    except Exception:
        caminho.unlink(missing_ok=True)
        try: core.log_exception('Web: exportar XMLs', sys.exc_info())
        except Exception: pass
        job.update(estado='erro', erro='Não foi possível gerar o ZIP. O detalhe foi guardado no registro de erros.')
    finally:
        if tmp_dir is not None:
            try: tmp_dir.cleanup()
            except Exception: pass
    _salvar(job)


def _data(x):
    x = str(x or '').strip()
    if x and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', x): raise ExportarErro('Data inválida.')
    return x


def pedir(empresa, de='', ate='', tipos=None, mov='', formato='organizado', desde='', por='', em_segundo_plano=True):
    """Cria o trabalho e começa a gerar o ZIP. Devolve o trabalho (com o `id`). `desde`: só notas guardadas a partir desse instante (as novas de uma busca)."""
    core = nucleo.core(); d = re.sub(r'\D', '', empresa or '')
    if len(d) != 14 or not core._is_valid_cnpj(d): raise ExportarErro('Escolha a empresa.')
    tipos = [t for t in (tipos or list(ROTULOS)) if t in ROTULOS]
    if not tipos: raise ExportarErro('Marque pelo menos um tipo de nota.')
    if mov not in ('', 'Entrada', 'Saída'): raise ExportarErro('Movimentação inválida.')
    if formato not in FORMATOS: raise ExportarErro('Formato inválido.')
    de, ate = _data(de), _data(ate)
    if de and ate and de > ate: raise ExportarErro('A data inicial não pode ser maior que a final.')
    desde = str(desde or '').strip()
    if desde and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', desde): raise ExportarErro('Instante inválido.')
    job = {'id': secrets.token_hex(8), 'estado': 'gerando', 'inicio': datetime.now().isoformat(timespec='seconds'), 'por': por, 'total': 0, 'feito': 0, 'empresa': '', 'erro': '',
           'filtros': {'empresa': d, 'de': de, 'ate': ate, 'tipos': tipos, 'mov': mov, 'formato': formato, 'desde': desde}}
    _salvar(job); limpar_antigos()
    if em_segundo_plano: threading.Thread(target=_executar, args=(job, job['filtros']), daemon=True, name='exportar-zip').start()
    else: _executar(job, job['filtros'])
    return job
