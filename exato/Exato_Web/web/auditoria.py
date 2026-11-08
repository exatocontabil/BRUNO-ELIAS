"""Auditoria Fiscal no Exato Web: confere o Excel do SAT com os XMLs guardados e gera o PDF do comparativo (o que o setor fiscal anexa na Acessórias).

Espelha o que o programa instalado faz em `_import_sat_audit` e `_finish_sat_audit` (V190) usando as mesmas rotinas de leitura, conferência, análise e PDF.
Cada auditoria fica numa pasta própria (`<dados>/auditorias/<AAAAMMDD_HHMMSS_CNPJ>/`) com o resumo, o PDF e uma cópia dos Excels do SAT."""
import json, re, shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from . import config, nucleo

ID_RE = re.compile(r'^\d{8}_\d{6}_\d{14}$')
FAMILIAS = ('nfe', 'nfce')
MAX_ARQUIVO = 25 * 1024 * 1024
MAX_ARQUIVOS = 6


class AuditoriaErro(Exception):
    """Texto pronto para mostrar ao usuário."""


def pasta_auditorias(): p = config.DADOS / 'auditorias'; p.mkdir(parents=True, exist_ok=True); return p


def _d(x): return re.sub(r'\D', '', str(x or ''))


def _dec(x):
    try: return str(Decimal(str(x or 0)).quantize(Decimal('0.01')))
    except Exception: return '0.00'


def auditar(cnpj, arquivos, familias, data_ini, data_fim, enviado_por='', agora=None):
    """Roda a auditoria. `arquivos`: caminhos dos .xlsx do SAT; `familias`: ['nfe'] / ['nfce'] / ambos; datas 'AAAA-MM-DD'. Devolve o resumo gravado (com o `id`)."""
    core = nucleo.core(); cnpj = _d(cnpj)
    if len(cnpj) != 14 or not core._is_valid_cnpj(cnpj): raise AuditoriaErro('Escolha a empresa da auditoria.')
    selected = [f for f in FAMILIAS if f in set(familias or [])]
    if not selected: raise AuditoriaErro('Escolha NF-e, NFC-e ou os dois.')
    if not data_ini or not data_fim or data_ini > data_fim: raise AuditoriaErro('Informe o período da auditoria (a data inicial não pode ser maior que a final).')
    arquivos = [Path(a) for a in arquivos]
    if not arquivos: raise AuditoriaErro('Envie o Excel do SAT.')
    grouped = {f: [] for f in selected}; headers = {f: set() for f in selected}; file_family = {}
    for path in arquivos:
        try: parsed = core._xlsx_read_values(path)
        except Exception as exc: raise AuditoriaErro(f'Não consegui ler "{path.name}": {exc}')
        rows = parsed['rows']
        if not rows: raise AuditoriaErro(f'O arquivo "{path.name}" não tem documentos utilizáveis do SAT.')
        detectadas = {core._audit_row_detected_family(r) for r in rows if core._audit_row_detected_family(r)}
        if not detectadas: raise AuditoriaErro(f'Não consegui identificar com segurança o tipo de documento do arquivo "{path.name}".')
        if len(detectadas) > 1: raise AuditoriaErro(f'O arquivo "{path.name}" mistura tipos de documento. Separe os arquivos do SAT por tipo.')
        fam = next(iter(detectadas))
        if fam not in selected: raise AuditoriaErro(f'O arquivo "{path.name}" parece conter {core.SUPPORTED_FAMILIES.get(fam, fam)}, que não está escolhido nesta auditoria.')
        file_family[str(path)] = fam; grouped[fam].extend(rows); headers[fam].update(parsed['headers'])
    faltam = [core.SUPPORTED_FAMILIES[f] for f in selected if not grouped[f]]
    if faltam: raise AuditoriaErro('Nenhum documento foi encontrado no Excel para: ' + ', '.join(faltam) + '.')
    results = {}
    for fam in selected:
        vistos = set(); sat_rows = []
        for r in grouped[fam]:
            k = core._audit_key(r)
            if k in vistos: continue
            vistos.add(k); sat_rows.append(r)
        res = core.audit_sat_excel_against_xml(cnpj, sat_rows, data_ini, data_fim, family=fam)
        res['family'] = fam; res['family_label'] = core.SUPPORTED_FAMILIES[fam]; res['source_file'] = 'Excel SAT (enviado pelo site)'
        res['source_files'] = [p for p, f in file_family.items() if f == fam]; res['headers'] = sorted(headers[fam]); results[fam] = res
    combined = core._combine_audit_results(results, selected, [str(a) for a in arquivos], data_ini, data_fim)
    nome = core.db_get_company_name(cnpj) or 'Empresa não identificada'
    try: core._audit_separar_cancelados(combined, cnpj)          # nota cancelada não é "sem correspondência"
    except Exception: pass
    combined['ai_analysis'] = core.analyze_audit_result(combined, nome, data_ini, data_fim)
    agora = agora or datetime.now(); aid = f"{agora.strftime('%Y%m%d_%H%M%S')}_{cnpj}"; pasta = pasta_auditorias() / aid; pasta.mkdir(parents=True, exist_ok=True)
    copias = []
    for i, a in enumerate(arquivos, 1):
        dest = pasta / f'SAT_{i}.xlsx'; shutil.copyfile(a, dest); copias.append(str(dest))
    combined['source_files'] = copias
    try: core._audit_history_save(combined, nome, cnpj, copias)
    except Exception: pass
    pdf = pasta / f'Auditoria_Fiscal_{cnpj}_{agora.strftime("%Y%m%d")}.pdf'
    core.generate_audit_pdf(combined, str(pdf), nome, cnpj, data_ini, data_fim, [Path(c).name for c in copias])
    ai = combined.get('ai_analysis') or {}
    linhas = []
    for r in combined.get('display_rows') or []:
        linhas.append({'situacao': core._audit_status_label_for_row(r), 'numero': str(r.get('numero') or ''), 'data': str(r.get('data') or '')[:10], 'modelo': str(r.get('modelo') or ''),
                       'documento': str(r.get('situacao_doc') or ''), 'valor_sat': '' if r.get('valor_sat') is None else _dec(r.get('valor_sat')), 'valor_xml': '' if r.get('valor_xml') is None else _dec(r.get('valor_xml')),
                       'observacao': str(r.get('observacao') or '')})
    resumo = {'id': aid, 'cnpj': cnpj, 'empresa': nome, 'periodo': [data_ini, data_fim], 'tipos': selected, 'criada_em': agora.isoformat(timespec='seconds'), 'por': enviado_por,
              'status': ai.get('status', ''), 'titulo': ai.get('title', ''), 'mensagem': ai.get('message', ''), 'conciliados': len(combined.get('matched') or []),
              'sem_xml': len(combined.get('sat_only') or []), 'so_xml': len(combined.get('xml_only') or []), 'canceladas': len(combined.get('cancelled_xml') or []),
              'divergencias': sum(1 for r in combined.get('audit_rows') or [] if r.get('status') == 'Divergência'), 'sat_total': _dec(combined.get('sat_total')),
              'valor_conciliado': _dec(combined.get('matched_xml_total')), 'pdf': pdf.name, 'linhas': linhas}
    (pasta / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding='utf-8')
    return resumo


def ler(aid):
    """Resumo de uma auditoria já feita (None se o id não existe ou não é válido)."""
    if not ID_RE.match(str(aid or '')): return None
    arq = pasta_auditorias() / aid / 'resumo.json'
    try: return json.loads(arq.read_text(encoding='utf-8'))
    except Exception: return None


def historico(limite=100, cnpj=''):
    """As auditorias mais recentes primeiro (sem as linhas, para a lista ficar leve)."""
    out = []
    for p in sorted(pasta_auditorias().iterdir(), reverse=True):
        if not p.is_dir() or not ID_RE.match(p.name): continue
        r = ler(p.name)
        if not r or (cnpj and r.get('cnpj') != _d(cnpj)): continue
        out.append({k: v for k, v in r.items() if k != 'linhas'})
        if len(out) >= limite: break
    return out


def caminho_pdf(aid):
    r = ler(aid)
    if not r: return None
    p = pasta_auditorias() / aid / r['pdf']
    return p if p.exists() else None
