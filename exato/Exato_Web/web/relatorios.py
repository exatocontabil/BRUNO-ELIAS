"""Relatório de documentos em PDF no Exato Web (o mesmo relatório do programa instalado: uma seção por tipo e movimentação, autorizadas e canceladas separadas).
Gerado em segundo plano (pode levar minutos com muitas notas); cada pedido vira um "trabalho" com situação e o PDF para baixar."""
import json, re, secrets, sys, threading, time
from datetime import datetime
from pathlib import Path

from . import config, nucleo

ID_RE = re.compile(r'^[0-9a-f]{16}$')
_trava = threading.Lock()


class RelatorioErro(Exception): pass


def pasta(): p = config.DADOS / 'relatorios'; p.mkdir(parents=True, exist_ok=True); return p


def _salvar(job):
    with _trava: (pasta() / f"{job['id']}.json").write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')


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


def caminho_pdf(jid):
    j = ler(jid)
    if not j or j.get('estado') != 'pronto': return None
    p = pasta() / f'{jid}.pdf'; return p if p.exists() else None


def _executar(job, filtros):
    core = nucleo.core(); relpdf = nucleo.modulo('exato_relatorio_docs_pdf')
    try:
        rows = core.db_list_documents(cnpj=filtros['empresa'], family=filtros['tipo'], direction=filtros['mov'], status='', query='', limit=1000000, date_from=filtros['de'], date_to=filtros['ate'], with_xml=False)
        rows = [r for r in rows if r.get('status') != 'Evento']
        if not rows: raise RelatorioErro('Não há documentos neste filtro para o relatório.')
        cnpjs = {re.sub(r'\D', '', str(r.get('cnpj') or '')) for r in rows}; unico = next(iter(cnpjs)) if len(cnpjs) == 1 else ''
        empresa = (core.db_get_company_name(unico) or '') if unico else ''
        job['total'] = len(rows); _salvar(job)
        linhas = core.relatorio_documentos_linhas(rows)
        periodo = (f"{filtros['de'][8:]}/{filtros['de'][5:7]}/{filtros['de'][:4]} a {filtros['ate'][8:]}/{filtros['ate'][5:7]}/{filtros['ate'][:4]}" if filtros['de'] and filtros['ate'] else 'Todo o período')
        rotulos = [x for x in (f"Tipo: {filtros['tipo']}" if filtros['tipo'] else '', f"Movimentação: {filtros['mov']}" if filtros['mov'] else '') if x]
        logo = core.LOGO_PATH if getattr(core, 'LOGO_PATH', None) and Path(core.LOGO_PATH).exists() else None
        relpdf.gerar(linhas, str(pasta() / f"{job['id']}.pdf"), empresa, unico, periodo, rotulos, logo)
        job.update(estado='pronto', fim=datetime.now().isoformat(timespec='seconds'), empresa=empresa or 'Várias empresas', periodo=periodo)
    except RelatorioErro as e:
        job.update(estado='erro', erro=str(e))
    except Exception:
        try: core.log_exception('Web: relatório de documentos', sys.exc_info())
        except Exception: pass
        job.update(estado='erro', erro='Não foi possível gerar o relatório. O detalhe foi guardado no registro de erros.')
    _salvar(job)


def _executar_nfse(job, filtros):
    """Relatório mensal de NFS-e (o mesmo do programa instalado): resumo por mês e lista de prestadas e tomadas, autorizadas e canceladas separadas."""
    core = nucleo.core(); pdf = nucleo.modulo('exato_nfse_pdf')
    try:
        rows = [r for r in core.db_list_documents(cnpj=filtros['empresa'], family='nfse', limit=200000, date_from=filtros['de'], date_to=filtros['ate']) if r.get('status') != 'Evento']
        data = []
        for r in rows:
            try: data.append(pdf.report_row_from_xml(bytes(r['xml']), filtros['empresa'], 'Cancelada' if r.get('status') == 'Cancelado' else 'Autorizada'))
            except Exception: continue
        if not data: raise RelatorioErro('Não há NFS-e neste filtro para o relatório.')
        job['total'] = len(data); _salvar(job); empresa = core.db_get_company_name(filtros['empresa']) or ''
        periodo = (f"{filtros['de'][8:]}/{filtros['de'][5:7]}/{filtros['de'][:4]} a {filtros['ate'][8:]}/{filtros['ate'][5:7]}/{filtros['ate'][:4]}" if filtros['de'] and filtros['ate'] else 'Todo o período')
        logo = core.LOGO_PATH if getattr(core, 'LOGO_PATH', None) and Path(core.LOGO_PATH).exists() else None
        pdf.generate_monthly_report_pdf(data, str(pasta() / f"{job['id']}.pdf"), empresa, filtros['empresa'], periodo, logo)
        job.update(estado='pronto', fim=datetime.now().isoformat(timespec='seconds'), empresa=empresa, periodo=periodo)
    except RelatorioErro as e: job.update(estado='erro', erro=str(e))
    except Exception:
        try: core.log_exception('Web: relatório mensal de NFS-e', sys.exc_info())
        except Exception: pass
        job.update(estado='erro', erro='Não foi possível gerar o relatório. O detalhe foi guardado no registro de erros.')
    _salvar(job)


def pedir_nfse(empresa, de='', ate='', por='', em_segundo_plano=True):
    core = nucleo.core(); d = re.sub(r'\D', '', empresa or '')
    if len(d) != 14 or not core._is_valid_cnpj(d): raise RelatorioErro('Escolha uma empresa válida.')
    for x in (de, ate):
        if x and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', x): raise RelatorioErro('Data inválida.')
    if de and ate and de > ate: raise RelatorioErro('A data inicial não pode ser maior que a final.')
    job = {'id': secrets.token_hex(8), 'estado': 'gerando', 'inicio': datetime.now().isoformat(timespec='seconds'), 'por': por, 'total': 0, 'empresa': '', 'periodo': '', 'erro': '', 'filtros': {'empresa': d, 'tipo': 'nfse', 'mov': '', 'de': de, 'ate': ate}}
    _salvar(job)
    if em_segundo_plano: threading.Thread(target=_executar_nfse, args=(job, job['filtros']), daemon=True, name='relatorio-nfse').start()
    else: _executar_nfse(job, job['filtros'])
    return job


def pedir(empresa='', tipo='', mov='', de='', ate='', por='', em_segundo_plano=True):
    """Cria o trabalho e começa a gerar. Devolve o trabalho (com o `id`)."""
    core = nucleo.core(); d = re.sub(r'\D', '', empresa or '')
    if d and (len(d) != 14 or not core._is_valid_cnpj(d)): raise RelatorioErro('Escolha uma empresa válida.')
    if tipo not in ('', 'nfe', 'nfce', 'cte', 'nfse'): raise RelatorioErro('Tipo inválido.')
    if mov not in ('', 'Entrada', 'Saída'): raise RelatorioErro('Movimentação inválida.')
    for x in (de, ate):
        if x and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', x): raise RelatorioErro('Data inválida.')
    if de and ate and de > ate: raise RelatorioErro('A data inicial não pode ser maior que a final.')
    job = {'id': secrets.token_hex(8), 'estado': 'gerando', 'inicio': datetime.now().isoformat(timespec='seconds'), 'por': por, 'total': 0, 'empresa': '', 'periodo': '', 'erro': '',
           'filtros': {'empresa': d, 'tipo': tipo, 'mov': mov, 'de': de, 'ate': ate}}
    _salvar(job); args = (job, job['filtros'])
    if em_segundo_plano: threading.Thread(target=_executar, args=args, daemon=True, name='relatorio-docs').start()
    else: _executar(*args)
    return job
