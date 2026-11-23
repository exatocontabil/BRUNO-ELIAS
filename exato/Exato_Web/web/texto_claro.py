"""Texto em português claro para quem usa o Exato Web: tira da tela termos de programação ou de rede que vêm de módulos do Exato instalado
(os módulos do programa instalado não são alterados; as mensagens são limpas aqui, na hora de mostrar). Termos do ofício fiscal (NF-e, XML, SEFAZ, certificado A1) ficam."""
import re

SUBS = [
    (r'Manutenção\s*>\s*Abrir registro de erros e envie o arquivo exato\.log ao suporte', 'Fale com o suporte informando o dia e a hora em que aconteceu'),
    (r'Instale o Microsoft Edge e abra o arquivo INSTALAR_COMPONENTE_NFSE\.bat na pasta ferramentas\.', 'Este computador precisa do Microsoft Edge para essa consulta. Fale com o suporte.'),
    (r'O detalhe técnico foi guardado no registro de erros', 'O detalhe foi guardado para o suporte'),
    (r'guardado no registro de erros', 'guardado para o suporte'),
    (r'registro de erros', 'registro do suporte'),
    (r'o arquivo exato\.log|arquivo exato\.log|exato\.log', 'o registro do suporte'),
    (r'Tente trocar a segurança \(STARTTLS ou SSL\) e a porta \(587 com STARTTLS, ou 465 com SSL\)', 'Tente trocar a segurança da conexão ("Segura (recomendada)" com a porta 587, ou "Segura (conexão direta)" com a porta 465)'),
    (r'tente a porta 465 com segurança SSL', 'tente a porta 465 com a segurança "Segura (conexão direta)"'),
    (r'Tente a porta 465 com segurança SSL', 'Tente a porta 465 com a segurança "Segura (conexão direta)"'),
    (r'firewall ou proxy', 'firewall ou configuração da rede'),
    (r'\bSTARTTLS\b', 'Segura (recomendada)'),
    (r'\bSSL\b', 'Segura (conexão direta)'),
    (r'\bSMTP\b', 'e-mail'),
    (r'\bcStat\b', 'código'),
]
_COMP = [(re.compile(p), r) for p, r in SUBS]


def limpar(texto):
    """Troca termos técnicos por português claro. Aceita qualquer coisa: o que não é texto volta igual."""
    if not isinstance(texto, str): return texto
    for rx, r in _COMP: texto = rx.sub(r, texto)
    return texto


def limpar_causas(causas):
    """Aplica `limpar` a todas as explicações do dicionário de causas da busca ({codigo: (titulo, explicacao, acao, gravidade)})."""
    for k, v in list(causas.items()):
        try: causas[k] = tuple(limpar(x) if isinstance(x, str) else x for x in v)
        except Exception: pass


def embrulhar(modulo, nome):
    """Faz a função `nome` do módulo devolver o texto já limpo (idempotente)."""
    f = getattr(modulo, nome, None)
    if f is None or getattr(f, '_texto_claro', False): return
    def nova(*a, **k): return limpar(f(*a, **k))
    nova._texto_claro = True; setattr(modulo, nome, nova)
