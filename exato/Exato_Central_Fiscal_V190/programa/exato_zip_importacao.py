"""ZIP para importação (V168): um ZIP por empresa, mês, tipo e direção, na própria pasta dos XMLs.

A Domínio importa mais rápido quando os XMLs chegam zipados. Depois de salvar os XMLs na pasta dos clientes, cada pasta
`<Empresa>/<Ano>/<MM - Mês>/<Entrada|Saída|Prestados|Tomados>/<NF-e|NFC-e|CT-e|NFS-e>/` ganha, ao lado dos XMLs soltos, o arquivo
`<CNPJ>_<AAAA-MM>_<Tipo>_<Direção>.zip` com TODOS os XMLs daquela pasta (soltos, sem subpastas) e, quando houver, os eventos de
cancelamento das notas da pasta. O ZIP só é refeito quando o conjunto de XMLs muda; é gravado num arquivo temporário e trocado no fim
(nunca fica um ZIP pela metade). Os XMLs soltos nunca são alterados. Sem Tkinter.
"""
from __future__ import annotations
import hashlib, os, re, tempfile, zipfile
from pathlib import Path

TIPOS = ('NF-e', 'NFC-e', 'CT-e', 'NFS-e')
DIRECOES = ('Entrada', 'Saída', 'Prestados', 'Tomados')


def _nome(texto):
    t = re.sub(r'[\\/:*?"<>|\s]+', '-', str(texto or '').strip()).strip('-.')
    return t or 'sem-nome'


def _identificar(pasta):
    """(ano, mês, direção, tipo) a partir do caminho .../<Ano>/<MM - Mês>/<Direção>/<Tipo>; None se a pasta não segue o padrão."""
    p = Path(pasta); partes = p.parts
    if len(partes) < 4: return None
    tipo, direcao, mes_nome, ano = partes[-1], partes[-2], partes[-3], partes[-4]
    if tipo not in TIPOS or direcao not in DIRECOES: return None
    m = re.match(r'(\d{2})\b', mes_nome)
    mes = m.group(1) if m else '00'
    ano = ano if re.fullmatch(r'\d{4}', ano) else 'Sem-data'
    return ano, mes, direcao, tipo


def nome_do_zip(cnpj, ano, mes, tipo, direcao):
    digitos = re.sub(r'\D', '', str(cnpj or '')) or 'sem-cnpj'
    return f"{digitos}_{ano}-{mes}_{_nome(tipo)}_{_nome(direcao)}.zip"


def _chave_do_arquivo(nome):
    m = re.search(r'(\d{44,50})', nome)
    return m.group(1) if m else ''


PASTA_EVENTOS = 'Eventos'


def gravar_eventos_pasta(pasta, cnpj, eventos_fn):
    """Grava os XMLs dos EVENTOS (cancelamento) das notas da pasta numa subpasta `Eventos`, ao lado dos XMLs, para a nota cancelada e o seu evento
    irem juntos na importação. Nunca sobrescreve: arquivo já existente com o mesmo tamanho fica como está. Devolve quantos gravou."""
    if not eventos_fn: return 0
    try:
        if not _identificar(pasta): return 0
        chaves = sorted({c for c in (_chave_do_arquivo(f.name) for f in Path(pasta).glob('*.xml')) if c})
        eventos = list(eventos_fn(cnpj, chaves) or []) if chaves else []
    except Exception:
        return 0
    feitos = 0
    for nome, dados in eventos:
        try:
            if not dados: continue
            destino_dir = Path(pasta) / PASTA_EVENTOS; destino_dir.mkdir(exist_ok=True); alvo = destino_dir / re.sub(r'[\\/:*?"<>|]+', '_', nome)
            if alvo.exists() and alvo.stat().st_size == len(dados): continue
            if alvo.exists(): alvo = alvo.with_name(f'{alvo.stem}_{hashlib.sha256(dados).hexdigest()[:6]}{alvo.suffix}')
            tmp = alvo.with_name('.' + alvo.name + '.tmp'); tmp.write_bytes(dados); os.replace(tmp, alvo); feitos += 1
        except OSError:
            continue
    return feitos


def gravar_eventos(arquivos_salvos, cnpj, eventos_fn):
    """`gravar_eventos_pasta` para cada pasta onde foram salvos XMLs. Devolve o total gravado."""
    pastas = sorted({str(Path(p).parent) for p in (arquivos_salvos or []) if str(p).lower().endswith('.xml')})
    return sum(gravar_eventos_pasta(p, cnpj, eventos_fn) for p in pastas)


def montar_zips(arquivos_salvos, cnpj, eventos_fn=None):
    """Cria/atualiza os ZIPs das pastas onde foram salvos XMLs. `arquivos_salvos`: caminhos devolvidos pelo salvamento.
    `eventos_fn(cnpj, chaves) -> [(nome_do_arquivo, bytes)]` (opcional) devolve os eventos de cancelamento das notas.
    Devolve {'criados', 'atualizados', 'iguais', 'erros': [..], 'zips': [..]}."""
    res = {'criados': 0, 'atualizados': 0, 'iguais': 0, 'erros': [], 'zips': []}
    pastas = sorted({str(Path(p).parent) for p in (arquivos_salvos or []) if str(p).lower().endswith('.xml')})
    for pasta in pastas:
        try:
            ident = _identificar(pasta)
            if not ident:
                continue
            ano, mes, direcao, tipo = ident
            xmls = sorted(f for f in Path(pasta).glob('*.xml') if f.is_file())
            if not xmls:
                continue
            chaves = sorted({c for c in (_chave_do_arquivo(f.name) for f in xmls) if c})
            eventos = []
            if eventos_fn and chaves:
                try: eventos = list(eventos_fn(cnpj, chaves) or [])
                except Exception: eventos = []
            assinatura = hashlib.sha256()
            for f in xmls:
                assinatura.update(f.name.encode('utf-8')); assinatura.update(str(f.stat().st_size).encode())
            for nome, dados in eventos:
                assinatura.update(b'E' + nome.encode('utf-8')); assinatura.update(hashlib.sha256(dados).digest())
            marca = ('exato:' + assinatura.hexdigest()).encode('ascii')
            destino = Path(pasta) / nome_do_zip(cnpj, ano, mes, tipo, direcao)
            existia = destino.exists()
            if existia:
                try:
                    with zipfile.ZipFile(destino) as z:
                        if z.comment == marca:
                            res['iguais'] += 1; res['zips'].append(str(destino)); continue
                except zipfile.BadZipFile:
                    pass                       # ZIP danificado: refaz
            fd, tmp = tempfile.mkstemp(prefix='.' + destino.name + '.', suffix='.tmp', dir=str(pasta)); os.close(fd)
            try:
                with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                    usados = set()
                    for f in xmls:
                        z.write(f, f.name); usados.add(f.name)
                    for nome, dados in eventos:
                        n = nome if nome not in usados else f'evento_{len(usados)}_{nome}'
                        z.writestr(n, dados); usados.add(n)
                    z.comment = marca
                os.replace(tmp, destino)
            finally:
                try: os.remove(tmp)
                except OSError: pass
            res['atualizados' if existia else 'criados'] += 1; res['zips'].append(str(destino))
        except Exception as exc:
            res['erros'].append(f'{pasta}: {str(exc)[:120]}')
    return res


def gerar_todos(raiz, progresso=None, cancelar=None, eventos_fn=None, resolver_cnpj=None):
    """ZIPs de tudo que já está salvo (meses guardados antes da V168): percorre `<raiz>/<Empresa>/<Ano>/<MM - Mês>/<Direção>/<Tipo>`.
    O CNPJ vem do número no nome da pasta da empresa (`Empresa_<CNPJ>` ou `<CNPJ> - Nome`) ou, quando a pasta tem só o nome da empresa (o padrão do Exato),
    de `resolver_cnpj(nome_da_pasta)`. ZIP que já está igual não é refeito.
    Devolve {'criados','atualizados','iguais','erros','pastas','sem_cnpj'}."""
    res = {'criados': 0, 'atualizados': 0, 'iguais': 0, 'erros': [], 'pastas': 0, 'sem_cnpj': 0}
    raiz = Path(raiz)
    if not raiz.is_dir(): return res
    for empresa in sorted(p for p in raiz.iterdir() if p.is_dir()):
        m = re.search(r'(\d{14})', empresa.name)
        cnpj = m.group(1) if m else ''
        if not cnpj and resolver_cnpj:
            try: cnpj = re.sub(r'\D', '', str(resolver_cnpj(empresa.name) or ''))
            except Exception: cnpj = ''
        if len(cnpj) != 14: res['sem_cnpj'] += 1; continue
        pastas = set()
        for pasta, _dirs, nomes in os.walk(empresa):
            if any(n.lower().endswith('.xml') for n in nomes) and _identificar(pasta): pastas.add(pasta)
        for pasta in sorted(pastas):
            if cancelar and cancelar(): return res
            gravar_eventos_pasta(pasta, cnpj, eventos_fn)
            r = montar_zips([str(Path(pasta) / n) for n in os.listdir(pasta) if n.lower().endswith('.xml')][:1], cnpj, eventos_fn)
            for k in ('criados', 'atualizados', 'iguais'): res[k] += r[k]
            res['erros'] += r['erros']; res['pastas'] += 1
            if progresso:
                try: progresso(dict(res, atual=str(pasta)))
                except Exception: pass
    return res
