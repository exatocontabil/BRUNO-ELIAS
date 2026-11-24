"""Assistente de primeira instalação ("Primeiros passos"): leva o administrador, em poucas telas, do Exato recém-instalado até a primeira busca de notas.

Passos (todos medidos pelo que JÁ existe, nunca só por uma marca): 1) certificado digital A1; 2) empresas; 3) cópia de segurança; 4) primeira busca.
O Exato lê o CNPJ e o nome da empresa do próprio certificado (menos digitação). Só administrador. Nada aqui é obrigatório: dá para "fazer depois"."""
import re

PASSOS = (('certificado', 'Certificado digital'), ('empresas', 'Empresas'), ('copia', 'Cópia de segurança'), ('busca', 'Primeira busca'))


def memoria(cfg):
    return cfg.setdefault('primeiros_passos', {})


def estado(cfg, certificados, empresas, destino_copia):
    """Lista de passos com 'feito' e o próximo passo pendente. `certificados` e `empresas` são listas; `destino_copia` é o texto da pasta da cópia (ou '')."""
    m = memoria(cfg); pulados = set(m.get('pulados') or [])
    feito = {'certificado': bool(certificados), 'empresas': bool(empresas), 'copia': bool(destino_copia) or 'copia' in pulados, 'busca': bool(m.get('busca_feita'))}
    passos = [{'id': i, 'titulo': t, 'feito': feito[i]} for i, t in PASSOS]
    proximo = next((p['id'] for p in passos if not p['feito']), '')
    return {'passos': passos, 'proximo': proximo, 'concluido': not proximo}


def ler_cnpjs(texto, valido):
    """Separa o que a pessoa colou em CNPJs válidos (só dígitos, sem repetir) e pedaços que não são CNPJ. `valido(14 dígitos)` -> bool."""
    bons, ruins = [], []
    for t in re.split(r'[\s,;]+', texto or ''):
        if not t: continue
        d = re.sub(r'\D', '', t)
        if len(d) == 14 and valido(d):
            if d not in bons: bons.append(d)
        else: ruins.append(t[:30])
    return bons, ruins


def nome_do_certificado(titular):
    """O nome no certificado costuma vir como 'RAZAO SOCIAL:12345678000199'. Devolve só a razão social (ou '')."""
    t = str(titular or '').split(':')[0].strip()
    return t if t and not re.fullmatch(r'[\d.\-/ ]+', t) else ''
