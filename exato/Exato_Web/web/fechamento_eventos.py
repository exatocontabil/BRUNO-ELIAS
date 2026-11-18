"""Eventos no Fechamento do mês (correção do site, sem mexer no Exato instalado).

O fechamento do Central Fiscal V190 monta o ZIP "Eventos" do mês com todas as linhas de evento que têm a DATA DO EVENTO naquele mês, inclusive o RESUMO
do evento (`resEvento`), e deixa de fora o cancelamento feito em outro mês. As regras do usuário são: o evento da nota vai junto, procurado pela CHAVE da
nota (em qualquer mês); o resumo nunca entra; evento nunca é inventado. Aqui a montagem dos ZIPs do mês é trocada por uma que cumpre isso."""
import re

_MARCA = '_exato_web_eventos'


def instalar(core, fech):
    if getattr(fech, _MARCA, False): return
    original = fech._montar_zips

    def montar(docs, cnpj, mes, pasta_tmp, sufixo=''):
        notas = [d for d in docs if d['status'] != 'Evento']          # saem todos os "eventos" do mês (inclusive resumos); os certos entram abaixo, pela chave da nota
        fam_da_chave = {}
        for d in notas:
            chave = re.sub(r'\D', '', str(d['access_key'] or ''))
            if chave and d['status'] == 'Cancelado': fam_da_chave[chave] = d['family']
        eventos = []
        if fam_da_chave:
            try: achados = list(core._zip_eventos(cnpj, sorted(fam_da_chave)) or [])          # só o evento completo de nota cancelada, em qualquer mês; sem resumo
            except Exception: achados = []
            for nome, dados in achados:
                m = re.search(r'(\d{44,50})', nome)
                if not dados or not m: continue
                eventos.append({'doc_id': nome[:-4] if nome.lower().endswith('.xml') else nome, 'cnpj': cnpj, 'family': fam_da_chave.get(m.group(1), 'nfe'), 'direction': '', 'number': '', 'series': '',
                                'issued_at': mes + '-01', 'first_seen_at': '', 'status': 'Evento', 'doc_type': 'Evento', 'access_key': m.group(1), 'xml': dados, 'value': ''})
        return original(notas + eventos, cnpj, mes, pasta_tmp, sufixo)
    fech._montar_zips = montar; setattr(fech, _MARCA, True)
