"""Conferência de NFS-e (site): para uma empresa e período, mostra o que existe (prestadas x tomadas, autorizadas x canceladas), o que merece olhar
(cancelada sem o XML do cancelamento, numeração de prestadas faltando, ISS retido e ISS fora do município) e a situação da última busca.
Só lê o banco; nunca fabrica nota nem evento."""
import re
from decimal import Decimal

from . import nucleo


def _d(x):
    try: return Decimal(str(x or 0).replace(',', '.'))
    except Exception: return Decimal(0)


def conferir(cnpj, de='', ate=''):
    core = nucleo.core(); pdf = nucleo.modulo('exato_nfse_pdf'); num = nucleo.modulo('exato_numeracao'); d = re.sub(r'\D', '', cnpj or '')
    rows = [r for r in core.db_list_documents(cnpj=d, family='nfse', limit=200000, date_from=de, date_to=ate) if r.get('status') != 'Evento']
    out = {'cnpj': d, 'total': len(rows), 'prestadas': {'aut': 0, 'canc': 0, 'valor': Decimal(0)}, 'tomadas': {'aut': 0, 'canc': 0, 'valor': Decimal(0)},
           'iss_retido': Decimal(0), 'iss_fora': {'qtd': 0, 'valor': Decimal(0)}, 'sem_dado': 0, 'canc_sem_evento': 0, 'lacunas': '', 'lacunas_total': 0, 'avisos': []}
    numeros = []
    for r in rows:
        try: x = pdf.report_row_from_xml(bytes(r['xml']), d, 'Cancelada' if r.get('status') == 'Cancelado' else 'Autorizada')
        except Exception: out['sem_dado'] += 1; continue
        lado = out['prestadas'] if x['tipo'] == 'Prestado' else out['tomadas']
        if x['situacao'] == 'Cancelada': lado['canc'] += 1; continue
        lado['aut'] += 1; lado['valor'] += _d(x['valor'])
        if str(x.get('iss_retido')).strip().lower() in ('sim', 's', 'true'): out['iss_retido'] += _d(x.get('iss'))
        if x.get('iss_fora') == 'SIM': out['iss_fora']['qtd'] += 1; out['iss_fora']['valor'] += _d(x.get('iss'))
        if x['tipo'] == 'Prestado': numeros.append({'serie': '', 'numero': x['numero']})
    try:
        out['canc_sem_evento'] = len(core.db_canceladas_sem_evento(d)) if d else 0
    except Exception: pass
    faixas = num.lacunas(numeros).get('—', []) if numeros else []
    out['lacunas'] = num.texto_faixas(faixas) if faixas else ''; out['lacunas_total'] = num.total_faltando(faixas)
    if out['canc_sem_evento']: out['avisos'].append(f"{out['canc_sem_evento']} nota(s) cancelada(s) sem o XML do cancelamento: o Exato não inventa esse arquivo; busque de novo ou peça ao cliente.")
    if out['lacunas_total']: out['avisos'].append(f"Numeração de prestadas com {out['lacunas_total']} número(s) faltando: pode ser nota não recebida ou número não usado. Confira.")
    if out['sem_dado']: out['avisos'].append(f"{out['sem_dado']} nota(s) não puderam ser lidas.")
    if not rows: out['avisos'].append('Nenhuma NFS-e neste período.')
    return out
