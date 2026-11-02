"""V190: NFS-e pelo certificado do escritório, por procuração (Emissor Nacional). Sem Tkinter, sem banco.

O Emissor Nacional passou a aceitar atuação em nome de terceiros com procuração eletrônica (cadastrada na Receita Federal para os serviços da NFS-e) ou por vínculo
na base do CNPJ. Para uma empresa sem certificado próprio neste computador, o Exato tenta a consulta com o certificado escolhido na NFS-e (o do contador),
informando o CNPJ da empresa. Se o Emissor Nacional aceitar, a empresa passa a ser buscada assim também nas rodadas automáticas; se recusar, o motivo é explicado
e o Exato só tenta de novo depois de algumas horas (nunca insiste a cada rodada).

O que se sabe de cada empresa fica em `config['nfse_acesso'][cnpj] = {'modo': 'proprio'|'procuracao', 'ok': bool, 'em': iso, 'detalhe': texto}`."""
import re
from datetime import datetime, timedelta

ESPERA_RECUSA_HORAS = 12          # depois de uma recusa, a rodada automática só tenta de novo depois disso (a busca manual tenta sempre)
CODIGO_RECUSA = 'procuracao_nao_aceita'


def _d(x):
    return re.sub(r'\D', '', str(x or ''))


def ligada(config):
    """Opção da tela NFS-e (padrão: ligada)."""
    return ((config or {}).get('nfse_prefs') or {}).get('procuracao', True) is not False


def raiz(cnpj):
    d = _d(cnpj)
    return d[:8] if len(d) == 14 else ''


def modo_para(cert_cnpj, cnpj):
    """'proprio' quando o certificado é da empresa (ou de outro estabelecimento da mesma raiz de CNPJ); 'procuracao' nos demais casos (inclui CPF)."""
    a, b = raiz(cert_cnpj), raiz(cnpj)
    return 'proprio' if (a and a == b) else 'procuracao'


def estado(config, cnpj):
    return dict(((config or {}).get('nfse_acesso') or {}).get(_d(cnpj)) or {})


def registrar(config, cnpj, modo, ok, detalhe='', agora=None):
    """Anota (na memória da configuração; quem chama grava) como a última tentativa de NFS-e por certificado foi para a empresa."""
    d = _d(cnpj)
    if len(d) != 14: return None
    item = {'modo': modo, 'ok': bool(ok), 'em': (agora or datetime.now()).isoformat(timespec='seconds'), 'detalhe': str(detalhe or '')[:300]}
    config.setdefault('nfse_acesso', {})[d] = item
    return item


def tentar_agora(config, cnpj, manual=False, agora=None):
    """A rodada automática deve tentar a procuração desta empresa agora? Depois de uma recusa, espera `ESPERA_RECUSA_HORAS`. Busca manual tenta sempre."""
    if manual: return True
    st = estado(config, cnpj)
    if st.get('modo') != 'procuracao' or st.get('ok', True): return True
    try: quando = datetime.fromisoformat(st.get('em'))
    except Exception: return True
    return (agora or datetime.now()) - quando >= timedelta(hours=ESPERA_RECUSA_HORAS)


def parece_recusa(texto):
    """A recusa é de relação entre certificado e empresa (e não de rede ou de instabilidade)?"""
    return bool(re.search(r'cnpj base|procura[cç][aã]o|n[aã]o pertence|n[aã]o autoriz|sem permiss|acesso negado|forbidden|\b40[13]\b|\b403\b', str(texto or ''), re.I))


def texto_recusa(detalhe=''):
    """Mensagem para a tela quando o Emissor Nacional não aceitou o certificado do escritório para a empresa."""
    return ('O Emissor Nacional não aceitou o certificado do escritório para esta empresa. Confira se a procuração eletrônica na Receita Federal está ativa e '
            'vale para os serviços da NFS-e, ou use o certificado da própria empresa. O Exato tenta de novo mais tarde.')


def mensagem(modo, erro):
    """Troca a recusa técnica do Emissor Nacional pelo texto de procuração quando a busca foi pelo certificado do escritório."""
    if modo == 'procuracao' and parece_recusa(erro): return texto_recusa(erro)
    return str(erro)


def rotulo(config, cnpj):
    """Texto curto para a Situação da busca ('por procuração') quando a NFS-e da empresa é buscada assim e deu certo; senão vazio."""
    st = estado(config, cnpj)
    return 'por procuração (certificado do escritório)' if st.get('modo') == 'procuracao' and st.get('ok') else ''
