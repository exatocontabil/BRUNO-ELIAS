"""Repositório de XML no servidor do escritório (V164).

Cada XML guardado no banco do Exato também é copiado, como arquivo próprio, para uma pasta do servidor:

    <pasta>\\Repositório\\<CNPJ> - <Empresa>\\<Ano>\\<Mês>\\<Tipo>\\[Prestados|Tomados|Entrada|Saída]\\<chave>.xml

Regras de segurança:
- um arquivo por XML; vários computadores podem gravar ao mesmo tempo sem se atrapalhar;
- se o arquivo já existe com o mesmo conteúdo, nada é feito; se existe com conteúdo DIFERENTE, nunca se sobrescreve (o novo é
  guardado ao lado com o final do código de verificação) e o caso é contado como "diferente";
- se o servidor não responde, o XML continua na fila (tabela repositorio_copias) e é copiado quando ele voltar;
- nada aqui apaga arquivos sozinho: o prazo de guarda só avisa (a limpeza precisa de confirmação);
- sem Tkinter: tudo roda em segundo plano e pode ser testado sozinho.

V169: os números da tela vêm do próprio servidor (Repositório\\.indice\\resumo.json), por empresa e mês, então todos os computadores
mostram os MESMOS números: o que está no servidor, o que ainda falta e o que tem conteúdo diferente.
"""
from __future__ import annotations
import hashlib, json, os, random, re, shutil, socket, sqlite3, tempfile, threading, time, zipfile
from datetime import datetime, timedelta
from pathlib import Path

BLOQUEADO = ''          # V182: motivo de NÃO gravar no servidor (ex.: 'versao_antiga' = este Exato é mais velho que o formato do servidor); '' = pode gravar

PASTA_PADRAO = r'\\SERVER\Arquivos Compartilhados\Clientes\Exato Serviços Contábeis Ltda\Exato Central Fiscal'
SUBPASTA = 'Repositório'
SUBPASTA_BACKUP = 'Backups'
MESES_PADRAO = 12
TIPOS = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}
_TIPOS_REVERSO = {v: k for k, v in TIPOS.items()}
_PAUSA_ERRO = timedelta(hours=1)          # depois de uma falha, só tenta o mesmo XML de novo após esta pausa


def nome_seguro(texto, limite=60):
    t = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', str(texto or '')).strip(' .')
    t = re.sub(r'\s+', ' ', t)
    return (t[:limite].strip(' .')) or 'sem nome'


def _longo(caminho):
    """Windows: caminhos de rede longos (mais de 260 caracteres) precisam do prefixo especial."""
    p = str(caminho)
    if os.name != 'nt' or p.startswith('\\\\?\\'):
        return p
    p = os.path.abspath(p)
    if p.startswith('\\\\'):
        return '\\\\?\\UNC\\' + p[2:]
    return '\\\\?\\' + p


_MSG_PERMISSAO = 'Sem permissão para gravar na pasta do servidor. Peça ao responsável pela rede para liberar a gravação para este usuário.'
_MSG_EM_USO = 'O arquivo está em uso por outro programa ou computador. O Exato tenta de novo.'
_MSG_ESPACO = 'Acabou o espaço no servidor.'
_MSG_REDE = 'O servidor não respondeu (a rede caiu ou o caminho não foi encontrado). O Exato tenta de novo.'
_MSG_LONGO = 'O nome da pasta ou do arquivo ficou longo demais para o servidor.'
_MSG_SEM_XML = 'Documento sem o conteúdo do XML no banco deste computador.'
_MSG_INCOMPLETO = 'O arquivo foi gravado incompleto no servidor. O Exato tenta de novo.'
_MSG_SUMIU = 'O arquivo sumiu do servidor e voltou para a fila.'
_MSG_OUTRO = 'Não foi possível gravar este documento no servidor. O Exato tenta de novo.'
_MENSAGENS = (_MSG_PERMISSAO, _MSG_EM_USO, _MSG_ESPACO, _MSG_REDE, _MSG_LONGO, _MSG_SEM_XML, _MSG_INCOMPLETO, _MSG_SUMIU, _MSG_OUTRO)


def erro_amigavel(erro):
    """Motivo da falha em português claro (aceita a exceção ou o texto gravado antes). Sem siglas nem nomes técnicos."""
    texto = str(erro or '').strip()
    if not texto:
        return ''
    if texto in _MENSAGENS:
        return texto                      # já gravado por esta versão
    cod = getattr(erro, 'winerror', None) or getattr(erro, 'errno', None)
    t = texto.lower()
    if cod in (5, 13, 1314) or any(k in t for k in ('permission', 'acesso negado', 'access is denied', 'access denied')):
        return _MSG_PERMISSAO
    if cod in (32, 33) or any(k in t for k in ('being used by another', 'em uso', 'sharing violation')):
        return _MSG_EM_USO
    if cod in (112, 28) or any(k in t for k in ('no space', 'espaço', 'espaco', 'disk full')):
        return _MSG_ESPACO
    if cod in (206, 36) or 'too long' in t or 'muito longo' in t:
        return _MSG_LONGO
    if cod in (3, 53, 55, 64, 67, 121, 1231, 1219) or any(k in t for k in ('network', 'rede', 'semaphore', 'semáforo', 'no such file', 'não pode encontrar', 'nao pode encontrar', 'host is down', 'timed out')):
        return _MSG_REDE
    if 'sem xml' in t:
        return _MSG_SEM_XML
    if 'incompleto' in t:
        return _MSG_INCOMPLETO
    if 'arquivo sumiu' in t:
        return _MSG_SUMIU
    return _MSG_OUTRO


def pasta_acessivel(base, espera=6.0):
    """A pasta existe e responde? (Roda numa linha separada: pasta de rede fora do ar pode demorar muito para responder.)"""
    base = str(base or '').strip()
    if not base:
        return False
    resultado = []
    def teste():
        try: resultado.append(os.path.isdir(_longo(base)))
        except Exception: resultado.append(False)
    t = threading.Thread(target=teste, daemon=True); t.start(); t.join(espera)
    return bool(resultado and resultado[0])


def preparar_banco(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS repositorio_copias(
        doc_id TEXT PRIMARY KEY, caminho TEXT, sha256 TEXT, copiado_em TEXT,
        tentativas INTEGER DEFAULT 0, ultima_tentativa TEXT, erro TEXT, conflito INTEGER DEFAULT 0, removido INTEGER DEFAULT 0)""")
    conn.commit()


def _sha(dados):
    return hashlib.sha256(dados).hexdigest()


def _ler(caminho):
    with open(_longo(caminho), 'rb') as f:
        return f.read()


def _partes(linha, pasta_empresa):
    """Pastas (relativas à pasta do repositório) onde o XML fica."""
    familia = str(linha['family'] or 'nfe').lower()
    tipo = TIPOS.get(familia, familia.upper())
    evento = str(linha['status'] or '') == 'Evento' or str(linha['doc_type'] or '') == 'Evento'
    if evento:
        tipo = 'Eventos ' + tipo
    data = str(linha['issued_at'] or '') or str(linha['first_seen_at'] or '')
    m = re.match(r'(\d{4})-(\d{2})', data)
    ano, mes = (m.group(1), m.group(2)) if m else ('Sem data', '00')
    partes = [pasta_empresa, ano, mes, tipo]
    direcao = str(linha['direction'] or '')
    if direcao and not evento:
        if familia == 'nfse':
            direcao = {'Saída': 'Prestados', 'Entrada': 'Tomados'}.get(direcao, direcao)
        partes.append(nome_seguro(direcao, 20))
    chave = re.sub(r'\D', '', str(linha['access_key'] or ''))
    nome = chave if (chave and not evento) else nome_seguro(linha['doc_id'], 80)
    if evento and chave:
        nome = nome_seguro(f"{chave}_{linha['doc_id']}", 100)
    partes.append(nome + '.xml')
    return partes


_NOME_SEM_VALOR = ('', 'empresa não identificada', 'sem nome')


def _nome_valido(nome):
    n = str(nome or '').strip()
    return bool(n) and n.casefold() not in _NOME_SEM_VALOR and not re.match(r'(?i)^empresa_\d+$', n)


_RE_CNPJ_INICIO = re.compile(r'^(\d{14})(?:\s|$)')
_RE_CNPJ_FIM = re.compile(r'(?:^|\s-\s)(\d{14})\s*$')


def cnpj_no_nome(nome):
    """CNPJ (14 dígitos) do nome de uma pasta de empresa, nos dois formatos: 'Nome - CNPJ' (V182, ordem alfabética) e o antigo 'CNPJ - Nome'. '' se não houver."""
    nome = str(nome or '')
    m = _RE_CNPJ_FIM.search(nome) or _RE_CNPJ_INICIO.match(nome)
    return m.group(1) if m else ''


def nome_no_nome(nome):
    """Nome da empresa contido no nome da pasta (nos dois formatos); '' se a pasta só tem o CNPJ."""
    nome = str(nome or ''); cnpj = cnpj_no_nome(nome)
    if not cnpj: return ''
    texto = re.sub(r'\s*-\s*' + cnpj + r'\s*$', '', nome) if _RE_CNPJ_FIM.search(nome) and not _RE_CNPJ_INICIO.match(nome) else re.sub(r'^' + cnpj + r'\s*-\s*', '', nome)
    return '' if texto.strip() == cnpj else texto.strip()


class _Empresas:
    """Nome da pasta de cada empresa: 'Nome - CNPJ' (V182: o nome vem primeiro e a lista fica em ordem alfabética; antes era 'CNPJ - Nome', que continua reconhecido e é migrado). O nome da pasta SEGUE o nome correto da empresa (V167):
    quando o nome verificado (vindo dos próprios XMLs) é diferente do da pasta, a pasta é renomeada, e se já existirem as duas, os arquivos são
    unidos. Sem nome verificado, uma pasta que já existe não é mexida (evita trocas de nome indo e voltando entre computadores)."""
    def __init__(self, pasta_repo, nome_empresa=None):
        self.pasta_repo = Path(pasta_repo); self.cache = {}; self.nome_empresa = nome_empresa; self.renomeadas = []; self._verificados = {}
        try:
            for nome in sorted(os.listdir(_longo(self.pasta_repo))):
                c = cnpj_no_nome(nome)
                if c and not nome.startswith('.'): self.cache.setdefault(c, []).append(nome)
        except Exception:
            pass

    @staticmethod
    def _nome_pasta(cnpj, nome):
        return f"{nome_seguro(nome, 60)} - {cnpj}" if _nome_valido(nome) else cnpj

    def _verificado(self, cnpj, nome_banco):
        if cnpj not in self._verificados:
            nome, ok = nome_banco, False
            if self.nome_empresa:
                try: nome, ok = self.nome_empresa(cnpj, nome_banco)
                except Exception: nome, ok = nome_banco, False
            self._verificados[cnpj] = (nome, bool(ok and _nome_valido(nome)))
        return self._verificados[cnpj]

    def pasta(self, cnpj, nome_banco):
        cnpj = re.sub(r'\D', '', str(cnpj or '')) or 'sem CNPJ'
        existentes = self.cache.get(cnpj) or []
        nome, ok = self._verificado(cnpj, nome_banco)
        if not existentes:
            destino = self._nome_pasta(cnpj, nome if _nome_valido(nome) else nome_banco)
            self.cache[cnpj] = [destino]; return destino
        if ok:
            destino = self._nome_pasta(cnpj, nome)
            if existentes != [destino]:
                self._acertar(cnpj, existentes, destino)
            return destino
        antigos = [e for e in existentes if _RE_CNPJ_INICIO.match(e) and nome_no_nome(e)]
        if antigos:          # V182: só reordena ("CNPJ - Nome" -> "Nome - CNPJ"), sem trocar o nome
            destino = self._nome_pasta(cnpj, nome_no_nome(antigos[0]))
            if destino not in existentes or len(existentes) > 1:
                self._acertar(cnpj, existentes, destino)
            return self.cache.get(cnpj, [destino])[0]
        return existentes[0]

    def _acertar(self, cnpj, existentes, destino):
        for velho in existentes:
            if velho == destino: continue
            origem = self.pasta_repo / velho; alvo = self.pasta_repo / destino
            try:
                if not os.path.exists(_longo(alvo)):
                    os.rename(_longo(origem), _longo(alvo))
                else:
                    _unir(origem, alvo)
                self.renomeadas.append((velho, destino))
            except OSError:
                return              # não conseguiu agora (arquivo em uso): tenta na próxima rodada
        self.cache[cnpj] = [destino]

    def acertar_todas(self, cnpjs_nomes):
        """Confere as pastas que já existem contra o nome verificado de cada empresa (mesmo sem documento novo para copiar)."""
        for cnpj, nome_banco in cnpjs_nomes:
            if self.cache.get(cnpj): self.pasta(cnpj, nome_banco)


def _unir(origem, alvo):
    """Move o conteúdo de uma pasta para outra já existente, sem sobrescrever nada (arquivo repetido fica onde estava se for diferente)."""
    for raiz, dirs, nomes in os.walk(_longo(origem), topdown=False):
        rel = os.path.relpath(raiz, _longo(origem))
        destino_dir = Path(_longo(alvo)) / rel if rel != '.' else Path(_longo(alvo))
        os.makedirs(str(destino_dir), exist_ok=True)
        for n in nomes:
            de = os.path.join(raiz, n); para = destino_dir / n
            if not os.path.exists(str(para)):
                os.replace(de, str(para))
            elif os.path.getsize(str(para)) == os.path.getsize(de):
                os.remove(de)                    # é o mesmo arquivo (mesmo tamanho): sobra só uma cópia
        try: os.rmdir(raiz)
        except OSError: pass


def _atualizar_caminhos(fila, velho, novo):
    """Os caminhos gravados no banco acompanham a pasta renomeada."""
    prefixo_velho = f'{SUBPASTA}/{velho}/'; prefixo_novo = f'{SUBPASTA}/{novo}/'
    fila.append(("UPDATE repositorio_copias SET caminho=? || substr(caminho, ?) WHERE substr(caminho,1,?)=?", (prefixo_novo, len(prefixo_velho) + 1, len(prefixo_velho), prefixo_velho)))


def _listar(pasta):
    """{nome: tamanho} de uma pasta, numa única ida ao servidor (no Windows a lista já traz o tamanho: não abre arquivo nenhum)."""
    achados = {}
    try:
        with os.scandir(_longo(pasta)) as it:
            for e in it:
                try:
                    if e.is_file(): achados[e.name] = e.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return achados


def copiar_arquivo(pasta_repo, partes, xml):
    """Grava um XML. Devolve ('novo' | 'existe' | 'diferente', caminho relativo com /).

    Arquivo já existente com o MESMO TAMANHO é considerado o mesmo (passada rápida: não lê o conteúdo pela rede; a conferência por SHA-256
    é feita por amostra, todo dia, em `verificar`). Tamanho diferente: compara o conteúdo e, se for outro XML, guarda os dois."""
    pasta_repo = Path(pasta_repo)
    destino = pasta_repo.joinpath(*partes)
    sha = _sha(xml)
    os.makedirs(_longo(destino.parent), exist_ok=True)
    estado = 'novo'
    if os.path.exists(_longo(destino)):
        if os.path.getsize(_longo(destino)) == len(xml) or _sha(_ler(destino)) == sha:
            return 'existe', '/'.join([SUBPASTA] + list(partes))
        estado = 'diferente'
        partes = list(partes[:-1]) + [f"{Path(partes[-1]).stem}.{sha[:8]}.xml"]
        destino = pasta_repo.joinpath(*partes)
        if os.path.exists(_longo(destino)) and _sha(_ler(destino)) == sha:
            return 'diferente', '/'.join([SUBPASTA] + list(partes))
    temporario = destino.with_name('.' + destino.name + '.tmp')
    with open(_longo(temporario), 'wb') as f:
        f.write(xml); f.flush()
        try: os.fsync(f.fileno())
        except Exception: pass
    if os.path.getsize(_longo(temporario)) != len(xml):
        raise OSError('arquivo gravado incompleto')
    os.replace(_longo(temporario), _longo(destino))
    return estado, '/'.join([SUBPASTA] + list(partes))


def _pasta_repo(base):
    return Path(str(base)) / SUBPASTA


_SQL_ERRO = ("INSERT INTO repositorio_copias(doc_id,erro,ultima_tentativa,tentativas) VALUES(?,?,?,1) "
             "ON CONFLICT(doc_id) DO UPDATE SET erro=excluded.erro,ultima_tentativa=excluded.ultima_tentativa,tentativas=tentativas+1")
_SQL_OK = ("INSERT INTO repositorio_copias(doc_id,caminho,sha256,copiado_em,ultima_tentativa,erro,conflito,tentativas) VALUES(?,?,?,?,?,'',?,1) "
           "ON CONFLICT(doc_id) DO UPDATE SET caminho=excluded.caminho,sha256=excluded.sha256,copiado_em=excluded.copiado_em,ultima_tentativa=excluded.ultima_tentativa,erro='',conflito=excluded.conflito,removido=0")


def _gravar(conn, fila):
    """Grava de uma vez (em milissegundos) o que já foi copiado. O banco NUNCA fica travado durante a cópia de arquivos pela rede: antes a
    transação ficava aberta por minutos e as outras telas/buscas davam "database is locked" (V166)."""
    if not fila: return
    for tentativa in range(6):
        try:
            for sql, params in fila: conn.execute(sql, params)
            conn.commit(); fila.clear(); return
        except sqlite3.OperationalError:
            try: conn.rollback()
            except Exception: pass
            time.sleep(0.4 * (tentativa + 1))
    fila.clear()          # não conseguiu gravar agora: esses documentos continuam na fila e são refeitos na próxima rodada


def pendentes(db_path):
    """Quantos documentos do banco ainda não foram copiados."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        preparar_banco(conn)
        return int(conn.execute("SELECT COUNT(*) FROM documents d LEFT JOIN repositorio_copias r ON r.doc_id=d.doc_id WHERE r.copiado_em IS NULL").fetchone()[0] or 0)
    finally:
        conn.close()


def copiar_pendentes(db_path, base, cancelar=None, progresso=None, lote=300, maximo=None, nome_empresa=None, ignorar_pausa=False, prioridade=None, somente=None):
    """Copia para o servidor os documentos ainda não copiados. Pode ser interrompido e retomado a qualquer momento.

    `ignorar_pausa`: "Copiar agora" tenta de novo na hora até os documentos que falharam há pouco (sem isso, quem falhou espera 1 hora).
    `prioridade`: CNPJs copiados antes dos outros; `somente`: copia só esta empresa (V183).
    Devolve {'ok','motivo','novos','existentes','diferentes','erros','restantes'}.
    """
    res = {'ok': True, 'motivo': '', 'novos': 0, 'existentes': 0, 'diferentes': 0, 'erros': 0, 'restantes': 0}
    if BLOQUEADO:
        res.update(ok=False, motivo=BLOQUEADO); return res
    if not pasta_acessivel(base):
        res.update(ok=False, motivo='inacessivel'); return res
    conn = sqlite3.connect(db_path, timeout=30); conn.row_factory = sqlite3.Row
    try:
        preparar_banco(conn)
        res['restantes'] = pendentes(db_path)
        pasta_repo = _pasta_repo(base)
        os.makedirs(_longo(pasta_repo), exist_ok=True)
        empresas = _Empresas(pasta_repo, nome_empresa); falhas_seguidas = 0; feitos = 0; listagens = {}
        try:        # pastas que já existem com nome desatualizado: corrige mesmo sem documento novo
            nomes = [(re.sub(r'\D', '', str(r[0])), r[1]) for r in conn.execute("SELECT cnpj,name FROM companies").fetchall()]
            empresas.acertar_todas(nomes)
            fila_nomes = []
            for velho, novo in empresas.renomeadas: _atualizar_caminhos(fila_nomes, velho, novo)
            _gravar(conn, fila_nomes); empresas.renomeadas.clear()
        except Exception:
            pass
        # pausa normal: quem falhou há menos de 1 hora espera; "Copiar agora": tenta tudo, até o que falhou há pouco (o que falhar agora não volta no mesmo ciclo: a lista anda por doc_id)
        limite_tempo = '9999' if ignorar_pausa else (datetime.now() - _PAUSA_ERRO).isoformat(timespec='seconds')
        fases = [re.sub(r'\D', '', str(c)) for c in (prioridade or []) if c] + ([None] if not somente else [])          # V183: primeiro as empresas com prioridade, depois o resto
        if somente: fases = [re.sub(r'\D', '', str(somente))]
        for fase in fases:
            ultimo_id = ''; filtro_cnpj = ' AND d.cnpj=?' if fase else ''
            while True:
                if cancelar and cancelar():
                    res['motivo'] = 'cancelado'; break
                if maximo is not None and feitos >= maximo: break
                linhas = conn.execute(
                    f"""SELECT d.doc_id,d.cnpj,d.family,d.doc_type,d.direction,d.issued_at,d.first_seen_at,d.status,d.access_key,d.xml,c.name AS empresa
                       FROM documents d LEFT JOIN companies c ON c.cnpj=d.cnpj LEFT JOIN repositorio_copias r ON r.doc_id=d.doc_id
                       WHERE r.copiado_em IS NULL AND (r.ultima_tentativa IS NULL OR r.ultima_tentativa<?) AND d.doc_id>?{filtro_cnpj}
                       ORDER BY d.doc_id LIMIT ?""", (limite_tempo, ultimo_id) + ((fase,) if fase else ()) + (lote,)).fetchall()
                if not linhas: break
                ultimo_id = linhas[-1]['doc_id']
                agora = datetime.now().isoformat(timespec='seconds')
                fila = []; ultimo_flush = time.monotonic()
                for linha in linhas:
                    if fila and (len(fila) >= 25 or time.monotonic() - ultimo_flush > 2.0):
                        _gravar(conn, fila); ultimo_flush = time.monotonic()
                    if cancelar and cancelar():
                        res['motivo'] = 'cancelado'; break
                    xml = bytes(linha['xml'] or b'')
                    doc_id = linha['doc_id']
                    if not xml:
                        fila.append((_SQL_ERRO, (doc_id, _MSG_SEM_XML, agora)))
                        res['erros'] += 1; feitos += 1; continue
                    try:
                        partes = _partes(linha, empresas.pasta(linha['cnpj'], linha['empresa']))
                        pasta_doc = str(pasta_repo.joinpath(*partes[:-1]))
                        if pasta_doc not in listagens:
                            listagens[pasta_doc] = _listar(pasta_doc)           # uma ida ao servidor por pasta, não uma por arquivo
                        if listagens[pasta_doc].get(partes[-1]) == len(xml):
                            estado, rel = 'existe', '/'.join([SUBPASTA] + list(partes))      # já está lá (por exemplo, copiado por outro computador)
                        else:
                            estado, rel = copiar_arquivo(pasta_repo, partes, xml)
                            if estado == 'novo': listagens[pasta_doc][partes[-1]] = len(xml)
                    except Exception as exc:       # rede caiu, sem permissão, disco cheio...
                        fila.append((_SQL_ERRO, (doc_id, erro_amigavel(exc) or erro_amigavel(repr(exc)), agora)))
                        res['erros'] += 1; falhas_seguidas += 1; feitos += 1
                        if falhas_seguidas >= 3:
                            res.update(ok=False, motivo='falha'); _gravar(conn, fila); res['restantes'] = pendentes(db_path); return res
                        continue
                    falhas_seguidas = 0
                    fila.append((_SQL_OK, (doc_id, rel, _sha(xml), agora, agora, 1 if estado == 'diferente' else 0)))
                    res[{'novo': 'novos', 'existe': 'existentes', 'diferente': 'diferentes'}[estado]] += 1; feitos += 1
                for velho, novo in empresas.renomeadas: _atualizar_caminhos(fila, velho, novo)
                empresas.renomeadas.clear()
                _gravar(conn, fila)
                res['restantes'] = pendentes(db_path)
                if progresso:
                    try: progresso(dict(res))
                    except Exception: pass
                if res['motivo'] == 'cancelado': break
            if res['motivo'] == 'cancelado' or (maximo is not None and feitos >= maximo): break
        res['restantes'] = pendentes(db_path)
        return res
    finally:
        conn.close()


def resumo(db_path):
    """Números para a tela: documentos guardados, copiados, na fila, diferentes, com erro."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        preparar_banco(conn)
        total = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] or 0)
        copiados = int(conn.execute("SELECT COUNT(*) FROM repositorio_copias r JOIN documents d ON d.doc_id=r.doc_id WHERE r.copiado_em IS NOT NULL").fetchone()[0] or 0)
        diferentes = int(conn.execute("SELECT COUNT(*) FROM repositorio_copias WHERE conflito=1").fetchone()[0] or 0)
        erros = int(conn.execute("SELECT COUNT(*) FROM repositorio_copias r JOIN documents d ON d.doc_id=r.doc_id WHERE r.copiado_em IS NULL AND COALESCE(r.erro,'')<>''").fetchone()[0] or 0)
        ultima = conn.execute("SELECT MAX(copiado_em) FROM repositorio_copias").fetchone()[0] or ''
        motivos = {}
        for texto, n in conn.execute("SELECT r.erro, COUNT(*) FROM repositorio_copias r JOIN documents d ON d.doc_id=r.doc_id WHERE r.copiado_em IS NULL AND COALESCE(r.erro,'')<>'' GROUP BY r.erro").fetchall():
            m = erro_amigavel(texto); motivos[m] = motivos.get(m, 0) + int(n)
        antiga = conn.execute("SELECT MIN(r.ultima_tentativa) FROM repositorio_copias r JOIN documents d ON d.doc_id=r.doc_id WHERE r.copiado_em IS NULL AND COALESCE(r.erro,'')<>'' AND r.ultima_tentativa IS NOT NULL").fetchone()[0] or ''
        try: proxima = (datetime.fromisoformat(antiga) + _PAUSA_ERRO).isoformat(timespec='seconds') if antiga else ''
        except ValueError: proxima = ''
        return {'total': total, 'copiados': copiados, 'fila': max(total - copiados, 0), 'diferentes': diferentes, 'erros': erros, 'ultima_copia': ultima,
                'motivos': sorted(motivos.items(), key=lambda x: -x[1])[:4], 'proxima_tentativa': proxima}
    finally:
        conn.close()


_SQL_MES = ("CASE WHEN substr(COALESCE(NULLIF(d.issued_at,''),d.first_seen_at),1,7) GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]' "
            "THEN substr(COALESCE(NULLIF(d.issued_at,''),d.first_seen_at),1,7) ELSE 'Sem data' END")


def por_empresa_mes(db_path):
    """[(cnpj, empresa, 'AAAA-MM', documentos, copiados)] — mais recentes primeiro (só o que ESTE computador conhece)."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        preparar_banco(conn)
        linhas = conn.execute(
            f"""SELECT d.cnpj, COALESCE(c.name,''), {_SQL_MES} AS mes,
                      COUNT(*), SUM(CASE WHEN r.copiado_em IS NOT NULL THEN 1 ELSE 0 END)
               FROM documents d LEFT JOIN companies c ON c.cnpj=d.cnpj LEFT JOIN repositorio_copias r ON r.doc_id=d.doc_id
               WHERE COALESCE(r.removido,0)=0
               GROUP BY d.cnpj, mes ORDER BY mes DESC, 2""").fetchall()
        return [(a, b, c, int(d or 0), int(e or 0)) for a, b, c, d, e in linhas]
    finally:
        conn.close()


# ------------------------------------------------------------------ índice no servidor: os mesmos números em todos os computadores (V169)
PASTA_INDICE = '.indice'
ARQ_INDICE = 'resumo.json'
INDICE_VALIDADE = 300                 # segundos: um índice mais novo que isso não precisa ser refeito
_RE_DIFERENTE = re.compile(r'^(\d{10,}.*)\.([0-9a-f]{8})\.xml$')
_MAX_LISTA_DIFERENTES = 500


def _chave_mes(ano, mes):
    return f'{ano}-{mes}' if re.fullmatch(r'\d{4}', str(ano)) and re.fullmatch(r'\d{2}', str(mes)) else 'Sem data'


def _cnpj_da_pasta(nome):
    return cnpj_no_nome(nome) or nome


def _nome_da_pasta(nome):
    return nome_no_nome(nome)


def _varrer_pasta(pasta, falhas=None):
    """({arquivo: tamanho}, [subpastas]) numa única ida ao servidor. Pasta que não existe é só vazia; erro de rede entra em `falhas`."""
    arquivos, subs = {}, []
    try:
        with os.scandir(_longo(pasta)) as it:
            for e in it:
                try:
                    if e.is_dir(): subs.append(e.name)
                    elif e.is_file(): arquivos[e.name] = e.stat().st_size
                except OSError as exc:
                    if falhas is not None: falhas.append(exc)
    except FileNotFoundError:
        pass
    except OSError as exc:
        if falhas is not None: falhas.append(exc)
    return arquivos, subs


def varrer_servidor(base, cancelar=None):
    """Conta o que existe no servidor: {'contagem': {(cnpj, mês): {'nome','xmls','diferentes'}}, 'diferentes': [...]}. Só lista pastas (não abre arquivos).
    Devolve None se o servidor não responde ou se a contagem ficou incompleta (melhor não gravar números errados do que gravar pela metade)."""
    pasta_repo = _pasta_repo(base)
    if not pasta_acessivel(base):
        return None
    contagem, lista, falhas = {}, [], []
    _, empresas = _varrer_pasta(pasta_repo, falhas)
    for emp in sorted(empresas):
        if emp.startswith('.'): continue
        if cancelar and cancelar(): return None
        cnpj = _cnpj_da_pasta(emp); nome = _nome_da_pasta(emp)
        for ano in _varrer_pasta(pasta_repo / emp, falhas)[1]:
            for mes in _varrer_pasta(pasta_repo / emp / ano, falhas)[1]:
                chave = (cnpj, _chave_mes(ano, mes)); reg = contagem.setdefault(chave, {'nome': nome, 'xmls': 0, 'diferentes': 0, 'fechado': False, 'revisoes': 0})
                if nome and not reg['nome']: reg['nome'] = nome
                pilha = [pasta_repo / emp / ano / mes]
                while pilha:
                    atual = pilha.pop(); arquivos, subs = _varrer_pasta(atual, falhas)
                    pilha.extend(atual / x for x in subs)
                    if atual.name == 'Fechamento' and atual.parent == pasta_repo / emp / ano / mes:
                        reg['fechado'] = reg['fechado'] or '.fechamento.json' in arquivos
                        reg['revisoes'] += sum(1 for x in arquivos if x.startswith('Fechamento ') and x.endswith('.pdf') and '(revisado' in x and ' - NFS-e' not in x)
                    for nome_arq, tam in arquivos.items():
                        if not nome_arq.endswith('.xml') or nome_arq.startswith('.'): continue
                        reg['xmls'] += 1
                        m = _RE_DIFERENTE.match(nome_arq)
                        if m:
                            reg['diferentes'] += 1
                            if len(lista) < _MAX_LISTA_DIFERENTES:
                                rel = str(atual.relative_to(pasta_repo)).replace('\\', '/')
                                lista.append({'cnpj': cnpj, 'nome': nome, 'mes': chave[1], 'pasta': rel, 'arquivo': nome_arq, 'tamanho': tam,
                                              'original': m.group(1) + '.xml', 'tamanho_original': arquivos.get(m.group(1) + '.xml')})
    if falhas:
        return None
    return {'contagem': contagem, 'diferentes': lista}


def _caminho_indice(base):
    return _pasta_repo(base) / PASTA_INDICE / ARQ_INDICE


def ler_indice(base=None, cache=None):
    """O índice do servidor (ou, sem acesso, a última cópia guardada neste computador). Devolve (indice | None, origem 'servidor' | 'local' | '')."""
    if base:
        try:
            if pasta_acessivel(base, 4):
                with open(_longo(_caminho_indice(base)), 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                if isinstance(dados, dict) and isinstance(dados.get('empresas'), dict):
                    if cache: guardar_cache(dados, cache)
                    return dados, 'servidor'
        except Exception:
            pass
    if cache:
        try:
            with open(cache, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            if isinstance(dados, dict) and isinstance(dados.get('empresas'), dict):
                return dados, 'local'
        except Exception:
            pass
    return None, ''


def guardar_cache(indice, cache):
    try:
        tmp = str(cache) + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f: json.dump(indice, f, ensure_ascii=False)
        os.replace(tmp, str(cache))
    except Exception:
        pass


def indice_idade(indice):
    """Segundos desde que o índice foi gerado (computadores com relógios um pouco diferentes: nunca negativo)."""
    try: return max((datetime.now() - datetime.fromisoformat(str(indice.get('gerado_em')))).total_seconds(), 0.0)
    except Exception: return float('inf')


def _locais(db_path):
    """{(cnpj, mês): (nome, documentos conhecidos por ESTE computador)}"""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        preparar_banco(conn); saida = {}
        for cnpj, nome, mes, n in conn.execute(
                f"""SELECT d.cnpj, COALESCE(c.name,''), {_SQL_MES} AS mes, COUNT(*) FROM documents d LEFT JOIN companies c ON c.cnpj=d.cnpj
                    LEFT JOIN repositorio_copias r ON r.doc_id=d.doc_id WHERE COALESCE(r.removido,0)=0 GROUP BY d.cnpj, mes""").fetchall():
            chave = (re.sub(r'\D', '', str(cnpj or '')) or 'sem CNPJ', mes)
            antigo = saida.get(chave, ('', 0)); saida[chave] = (nome or antigo[0], antigo[1] + int(n or 0))
        return saida
    finally:
        conn.close()


def montar_indice(anterior, varrido, locais, computador):
    """Junta o que o servidor tem agora com o que já era conhecido: `conhecidos` é o MAIOR número de documentos que algum computador
    (ou o índice anterior) conhece daquela empresa/mês; `no_servidor` vem da varredura. `faltam = conhecidos - no_servidor` é igual para todos."""
    removidos = set(str(x) for x in ((anterior or {}).get('removidos') or []))
    antes = {}
    for cnpj, emp in ((anterior or {}).get('empresas') or {}).items():
        for mes, d in (emp.get('meses') or {}).items():
            antes[(cnpj, mes)] = (emp.get('nome') or '', int(d.get('conhecidos') or 0))
    chaves = set(antes) | set(varrido['contagem']) | set(locais)
    empresas = {}
    for cnpj, mes in sorted(chaves):
        srv = varrido['contagem'].get((cnpj, mes), {'nome': '', 'xmls': 0, 'diferentes': 0, 'fechado': False, 'revisoes': 0})
        no_servidor = max(int(srv['xmls']) - int(srv['diferentes']), 0)
        marca = f'{cnpj}|{mes}'
        if marca in removidos:
            if no_servidor == 0: continue            # mês apagado do servidor por prazo: não conta como "falta"
            removidos.discard(marca)
        nome_l, n_local = locais.get((cnpj, mes), ('', 0)); nome_a, n_ant = antes.get((cnpj, mes), ('', 0))
        conhecidos = max(no_servidor, n_local, n_ant)
        emp = empresas.setdefault(cnpj, {'nome': '', 'meses': {}})
        emp['nome'] = emp['nome'] or srv.get('nome') or nome_l or nome_a
        emp['meses'][mes] = {'conhecidos': conhecidos, 'no_servidor': no_servidor, 'diferentes': int(srv['diferentes']), 'fechado': bool(srv.get('fechado')), 'revisoes': int(srv.get('revisoes') or 0)}
    return {'versao': 1, 'gerado_em': datetime.now().isoformat(timespec='seconds'), 'computador': nome_seguro(computador or socket.gethostname(), 30),
            'empresas': empresas, 'removidos': sorted(removidos), 'diferentes': varrido['diferentes']}


def _gravar_indice(base, indice, computador):
    destino = _caminho_indice(base)
    os.makedirs(_longo(destino.parent), exist_ok=True)
    tmp = destino.with_name(f'.resumo.{nome_seguro(computador or socket.gethostname(), 20)}.{os.getpid()}.tmp')
    with open(_longo(tmp), 'w', encoding='utf-8') as f:
        json.dump(indice, f, ensure_ascii=False); f.flush()
        try: os.fsync(f.fileno())
        except Exception: pass
    for tentativa in range(4):
        try:
            os.replace(_longo(tmp), _longo(destino)); return          # troca de uma vez: ninguém lê um índice pela metade
        except OSError:
            if tentativa == 3:
                try: os.remove(_longo(tmp))
                except OSError: pass
                raise
            time.sleep(0.4 * (tentativa + 1))          # outro computador está lendo o índice neste instante: espera um pouco


def atualizar_indice(db_path, base, computador=None, cache=None, cancelar=None):
    """Varre o servidor, junta com o que este computador conhece e grava o índice (para todos). Devolve o índice ou None se o servidor não respondeu."""
    varrido = varrer_servidor(base, cancelar)
    if varrido is None:
        return None
    anterior, _ = ler_indice(base)
    indice = montar_indice(anterior, varrido, _locais(db_path), computador)
    try: _gravar_indice(base, indice, computador)
    except OSError:
        pass                 # sem permissão para gravar o índice: ainda serve para esta tela
    if cache: guardar_cache(indice, cache)
    return indice


def publicar_conhecidos(db_path, base, computador=None, cache=None):
    """Avisa o índice (sem varrer o servidor) de documentos que ESTE computador tem e que talvez ainda não estejam lá, para os outros
    computadores já mostrarem "faltam N". Devolve True se mudou alguma coisa."""
    indice, origem = ler_indice(base)
    if not indice or origem != 'servidor':
        return False
    removidos = set(str(x) for x in (indice.get('removidos') or [])); mudou = False
    for (cnpj, mes), (nome, n) in _locais(db_path).items():
        if f'{cnpj}|{mes}' in removidos: continue
        emp = indice['empresas'].setdefault(cnpj, {'nome': nome, 'meses': {}})
        if not emp.get('nome') and nome: emp['nome'] = nome
        d = emp['meses'].setdefault(mes, {'conhecidos': 0, 'no_servidor': 0, 'diferentes': 0})
        if n > int(d.get('conhecidos') or 0): d['conhecidos'] = n; mudou = True
    if mudou:
        try: _gravar_indice(base, indice, computador)
        except OSError: return False
        if cache: guardar_cache(indice, cache)
    return mudou


def marcar_removidos(base, pastas, computador=None):
    """Depois de apagar meses vencidos do servidor: o índice deixa de contar esses meses como "faltando"."""
    try:
        indice, _ = ler_indice(base)
        if not indice: return
        rem = set(str(x) for x in (indice.get('removidos') or []))
        for emp, ano, mes in pastas:
            chave = (_cnpj_da_pasta(emp), _chave_mes(ano, mes)); rem.add(f'{chave[0]}|{chave[1]}')
            e = indice['empresas'].get(chave[0])
            if e: e['meses'].pop(chave[1], None)
        indice['empresas'] = {c: e for c, e in indice['empresas'].items() if e['meses']}
        indice['removidos'] = sorted(rem); indice['gerado_em'] = datetime.now().isoformat(timespec='seconds')
        _gravar_indice(base, indice, computador)
    except Exception:
        pass


def indice_linhas(indice):
    """[(cnpj, empresa, mês, documentos, no servidor)] — mais recentes primeiro (igual em todos os computadores)."""
    linhas = []
    for cnpj, emp in (indice or {}).get('empresas', {}).items():
        for mes, d in emp.get('meses', {}).items():
            linhas.append((cnpj, emp.get('nome') or '', mes, int(d.get('conhecidos') or 0), int(d.get('no_servidor') or 0)))
    return sorted(linhas, key=lambda x: (_ordem_mes(x[2]), x[1].casefold()))


def marcar_fechados(base, meses, computador=None, cache=None):
    """Depois de fechar meses: anota no índice do servidor (sem varrer nada) que esses meses estão fechados, para a tela e os outros computadores
    já mostrarem. `meses`: [(cnpj, 'AAAA-MM', revisões)]. Devolve True se gravou."""
    try:
        indice, origem = ler_indice(base)
        if not indice or origem != 'servidor': return False
        for cnpj, mes, rev in meses:
            emp = indice['empresas'].setdefault(cnpj, {'nome': '', 'meses': {}})
            d = emp['meses'].setdefault(mes, {'conhecidos': 0, 'no_servidor': 0, 'diferentes': 0})
            d['fechado'] = True; d['revisoes'] = int(rev or 0)
        _gravar_indice(base, indice, computador)
        if cache: guardar_cache(indice, cache)
        return True
    except Exception:
        return False


def indice_fechamentos(indice):
    """{(cnpj, mês): (fechado, revisões)} do índice do servidor."""
    saida = {}
    for cnpj, emp in (indice or {}).get('empresas', {}).items():
        for mes, d in emp.get('meses', {}).items():
            saida[(cnpj, mes)] = (bool(d.get('fechado')), int(d.get('revisoes') or 0))
    return saida


def _ordem_mes(mes):
    return (0, tuple(-int(p) for p in mes.split('-'))) if re.fullmatch(r'\d{4}-\d{2}', str(mes)) else (1, (0,))


def indice_totais(indice):
    """{'xmls','empresas','meses','conhecidos','faltam','diferentes'} somando o índice."""
    xmls = conhecidos = faltam = dif = meses = 0; empresas = set()
    for cnpj, emp in (indice or {}).get('empresas', {}).items():
        for d in emp.get('meses', {}).values():
            n = int(d.get('no_servidor') or 0); c = max(int(d.get('conhecidos') or 0), n)
            xmls += n; conhecidos += c; faltam += max(c - n, 0); dif += int(d.get('diferentes') or 0); meses += 1
            if n: empresas.add(cnpj)
    return {'xmls': xmls, 'empresas': len(empresas), 'meses': meses, 'conhecidos': conhecidos, 'faltam': faltam, 'diferentes': dif}


# ------------------------------------------------------------------ cópia diária do banco
def zip_gentil(z, origem, arcname, bloco=4 * 1024 * 1024, pausa=0.004):
    """V189: grava um arquivo grande no ZIP em blocos grandes e cedendo a vez a cada bloco. O `ZipFile.write` copia de 8 em 8 KB e disputa o processador com a
    tela do programa (a interface engasgava enquanto o backup do banco rodava)."""
    zi = zipfile.ZipInfo(arcname, time.localtime(os.path.getmtime(origem))[:6]); zi.compress_type = z.compression
    zi._compresslevel = getattr(z, 'compresslevel', None)
    with open(origem, 'rb') as fin, z.open(zi, 'w', force_zip64=True) as fout:
        while True:
            b = fin.read(bloco)
            if not b: break
            fout.write(b); time.sleep(pausa)


def backup_diario(db_path, base, computador=None, manter_dias=30):
    """Uma cópia por dia e por computador do banco de dados, em <pasta>\\Backups\\AAAA-MM-DD. Devolve 'feito', 'ja_feito' ou 'inacessivel'."""
    if not pasta_acessivel(base):
        return 'inacessivel'
    pc = nome_seguro(computador or socket.gethostname(), 30)
    hoje = datetime.now().strftime('%Y-%m-%d')
    try:          # V183: a cópia temporária do banco fica em %TEMP% (precisa de ~2,3x o banco livres); sem espaço, pula o backup de hoje
        livre = shutil.disk_usage(tempfile.gettempdir()).free
        if livre < os.path.getsize(db_path) * 2.3: return 'sem_espaco'
    except OSError:
        pass
    pasta = Path(str(base)) / SUBPASTA_BACKUP / hoje
    alvo = pasta / f'central_fiscal_{pc}.zip'
    if os.path.exists(_longo(alvo)):
        return 'ja_feito'
    os.makedirs(_longo(pasta), exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix='exato_bk_'))
    try:
        copia = tmp / 'central_fiscal.db'
        origem = sqlite3.connect(db_path, timeout=30); destino = sqlite3.connect(copia)
        try: origem.backup(destino)
        finally: destino.close(); origem.close()
        zip_tmp = tmp / 'bk.zip'
        with zipfile.ZipFile(zip_tmp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as z:          # V189: nível 1 (bem mais rápido) e em blocos grandes
            zip_gentil(z, copia, 'central_fiscal.db')
        parcial = Path(str(alvo) + '.tmp')
        shutil.copyfile(zip_tmp, _longo(parcial))
        os.replace(_longo(parcial), _longo(alvo))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # guarda só as últimas cópias DESTE computador
    try:
        limite = datetime.now() - timedelta(days=manter_dias)
        for nome in os.listdir(_longo(Path(str(base)) / SUBPASTA_BACKUP)):
            try: dia = datetime.strptime(nome, '%Y-%m-%d')
            except ValueError: continue
            if dia < limite:
                velho = Path(str(base)) / SUBPASTA_BACKUP / nome / f'central_fiscal_{pc}.zip'
                if os.path.exists(_longo(velho)): os.remove(_longo(velho))
                try: os.rmdir(_longo(velho.parent))
                except OSError: pass
    except Exception:
        pass
    return 'feito'


# ------------------------------------------------------------------ conferência de integridade
def verificar(db_path, base, amostra=200):
    """Confere uma amostra de arquivos já copiados: existem e o conteúdo é o mesmo? Devolve lista de problemas (texto claro)."""
    problemas = []
    if not pasta_acessivel(base):
        return problemas
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        preparar_banco(conn)
        linhas = conn.execute("SELECT doc_id,caminho,sha256 FROM repositorio_copias WHERE copiado_em IS NOT NULL AND COALESCE(removido,0)=0 AND caminho<>''").fetchall()
        if len(linhas) > amostra:
            linhas = random.sample(linhas, amostra)
        voltam = []          # só grava no banco DEPOIS de ler a rede (nada de transação aberta durante o acesso ao servidor)
        for doc_id, caminho, sha in linhas:
            destino = Path(str(base)).joinpath(*caminho.split('/'))
            try:
                if not os.path.exists(_longo(destino)):
                    problemas.append(f'Arquivo sumiu do servidor: {caminho}')
                    voltam.append((doc_id,))      # volta para a fila
                elif _sha(_ler(destino)) != sha:
                    problemas.append(f'Arquivo foi alterado no servidor: {caminho}')
            except Exception as exc:
                problemas.append(f'Não consegui conferir {caminho}: {str(exc)[:80]}')
        _gravar(conn, [("UPDATE repositorio_copias SET copiado_em=NULL, erro='arquivo sumiu', ultima_tentativa=NULL WHERE doc_id=?", v) for v in voltam])
    finally:
        conn.close()
    return problemas


# ------------------------------------------------------------------ prazo de guarda (só avisa; apagar exige confirmação)
def _meses_vencidos(base, meses):
    """Pastas <empresa>/<ano>/<mês> mais antigas que o prazo."""
    corte = datetime.now().year * 12 + datetime.now().month - int(meses)
    pasta_repo = _pasta_repo(base); achadas = []
    try:
        for emp in os.listdir(_longo(pasta_repo)):
            for ano in os.listdir(_longo(pasta_repo / emp)):
                if not re.fullmatch(r'\d{4}', ano): continue
                for mes in os.listdir(_longo(pasta_repo / emp / ano)):
                    if not re.fullmatch(r'\d{2}', mes): continue
                    if int(ano) * 12 + int(mes) < corte:
                        achadas.append((emp, ano, mes))
    except Exception:
        pass
    return achadas


def vencidos(base, meses=MESES_PADRAO):
    """{'arquivos': n, 'bytes': n, 'pastas': [(empresa, ano, mes)]} — o que já passou do prazo no servidor."""
    if not pasta_acessivel(base):
        return {'arquivos': 0, 'bytes': 0, 'pastas': []}
    arquivos = tamanho = 0; pastas = _meses_vencidos(base, meses)
    pasta_repo = _pasta_repo(base)
    for emp, ano, mes in pastas:
        for raiz, _d, nomes in os.walk(_longo(pasta_repo / emp / ano / mes)):
            for n in nomes:
                if n.endswith('.xml'):
                    arquivos += 1
                    try: tamanho += os.path.getsize(os.path.join(raiz, n))
                    except OSError: pass
    return {'arquivos': arquivos, 'bytes': tamanho, 'pastas': pastas}


def apagar_vencidos(db_path, base, meses=MESES_PADRAO):
    """Remove do SERVIDOR as pastas de meses fora do prazo (o banco local não é tocado). Só chamar depois da confirmação do usuário."""
    info = vencidos(base, meses); pasta_repo = _pasta_repo(base)
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        preparar_banco(conn)
        marcas = []
        for emp, ano, mes in info['pastas']:
            shutil.rmtree(_longo(pasta_repo / emp / ano / mes), ignore_errors=True)
            _pref = f'{SUBPASTA}/{emp}/{ano}/{mes}/'
            marcas.append(("UPDATE repositorio_copias SET removido=1 WHERE substr(caminho,1,?)=?", (len(_pref), _pref)))
            try: os.rmdir(_longo(pasta_repo / emp / ano))
            except OSError: pass
            try: os.rmdir(_longo(pasta_repo / emp))
            except OSError: pass
        _gravar(conn, marcas)
    finally:
        conn.close()
    marcar_removidos(base, info['pastas'])
    return info


# ------------------------------------------------------------------ restaurar
def listar_para_restaurar(base):
    """[(cnpj, familia, caminho)] de todos os XMLs do repositório (para reconstruir o banco)."""
    pasta_repo = _pasta_repo(base); achados = []
    try:
        for emp in sorted(os.listdir(_longo(pasta_repo))):
            c_emp = cnpj_no_nome(emp)
            if not c_emp or emp.startswith('.'): continue
            for raiz, _d, nomes in os.walk(_longo(pasta_repo / emp)):
                partes = Path(raiz.replace('\\\\?\\UNC\\', '\\\\').replace('\\\\?\\', '')).parts
                familia = ''
                for p in partes:
                    base_tipo = p[len('Eventos '):] if p.startswith('Eventos ') else p
                    if base_tipo in _TIPOS_REVERSO: familia = _TIPOS_REVERSO[base_tipo]; break
                for n in sorted(nomes):
                    if n.endswith('.xml') and not n.startswith('.'):
                        achados.append((c_emp, familia, os.path.join(raiz, n)))
    except Exception:
        pass
    return achados


def ler_xml(caminho):
    return _ler(caminho)


def pendentes_por_empresa(db_path):
    """V183: {cnpj: quantos documentos ainda faltam copiar} (só empresas com fila)."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        preparar_banco(conn)
        return {str(c): int(n) for c, n in conn.execute(
            "SELECT d.cnpj, COUNT(*) FROM documents d LEFT JOIN repositorio_copias r ON r.doc_id=d.doc_id WHERE r.copiado_em IS NULL GROUP BY d.cnpj").fetchall()}
    finally:
        conn.close()
