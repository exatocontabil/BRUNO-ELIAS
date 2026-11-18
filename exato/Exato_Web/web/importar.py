"""Importa para o Exato Web os dados do programa instalado (empresas, notas e pontos de busca), para o site não começar vazio.

  python -m web.importar --origem "C:\\Users\\voce\\AppData\\Local\\Exato\\Central Fiscal\\Dados"      (a pasta Dados do programa instalado)
  python -m web.importar --origem "central_fiscal_PC01.zip"                                            (um backup .zip feito pelo programa)

Pare o site antes de importar. Pode rodar mais de uma vez (de computadores diferentes): nada é duplicado e nenhum ponto de busca volta atrás.
Usuários e senhas NÃO são importados (os do site são criados com `python -m web.usuarios`)."""
import argparse, json, os, shutil, sqlite3, sys, tempfile, zipfile
from pathlib import Path

LOTE = 500
TABELAS = ('companies', 'documents', 'document_sources')
# Histórico do programa instalado que também vem: marcas de exportação, caixa do Box-e (para NUNCA reenviar), empresas removidas, histórico de buscas e de auditorias.
EXTRAS_CHAVE = ('document_exports', 'boxe_envios', 'empresas_removidas')          # têm chave própria: INSERT OR IGNORE basta e pode repetir
EXTRAS_HISTORICO = ('sync_runs', 'busca_ocorrencias', 'audit_runs')          # numeração própria: só entram se o histórico do site ainda está vazio (não repete nem colide)
# Nunca importados: usuários e senhas, registro de atividade, filas da Central e cópias do Repositório (caminhos do outro computador; o site refaz a sua).


def _achar(pasta):
    pasta = Path(pasta)
    if (pasta / 'central_fiscal.db').exists(): return pasta
    for p in pasta.rglob('central_fiscal.db'): return p.parent
    return None


def preparar_origem(origem):
    """(pasta com central_fiscal.db, pasta temporária a apagar depois ou None). Aceita pasta ou backup .zip."""
    origem = Path(origem)
    if origem.is_file() and origem.suffix.lower() == '.zip':
        tmp = Path(tempfile.mkdtemp(prefix='exato_importar_'))
        with zipfile.ZipFile(origem) as z: z.extractall(tmp)
        pasta = _achar(tmp)
        if not pasta: shutil.rmtree(tmp, ignore_errors=True); raise ValueError('O backup não tem o banco de dados do Exato (central_fiscal.db).')
        return pasta, tmp
    pasta = _achar(origem) if origem.is_dir() else None
    if not pasta: raise ValueError('Não encontrei o banco de dados do Exato (central_fiscal.db) nessa pasta.')
    return pasta, None


def _colunas(con, banco, tabela):
    return [r[1] for r in con.execute(f'PRAGMA {banco}.table_info({tabela})')]


def _importar_tabela(con, tabela, progresso):
    dest = _colunas(con, 'main', tabela); orig = _colunas(con, 'o', tabela)
    if not orig: return 0, 0
    cols = ', '.join(c for c in dest if c in orig)
    total = con.execute(f'SELECT COUNT(*) FROM o.{tabela}').fetchone()[0]; inseridos = 0; ultimo = 0
    while True:
        lim = con.execute(f'SELECT MAX(rowid) FROM (SELECT rowid FROM o.{tabela} WHERE rowid > ? ORDER BY rowid LIMIT ?)', (ultimo, LOTE)).fetchone()[0]
        if lim is None: break
        antes = con.total_changes
        con.execute(f'INSERT OR IGNORE INTO main.{tabela}({cols}) SELECT {cols} FROM o.{tabela} WHERE rowid > ? AND rowid <= ?', (ultimo, lim)); con.commit()          # lotes curtos: nunca uma gravação longa aberta
        inseridos += con.total_changes - antes; ultimo = lim
        progresso(f'{tabela}: {min(ultimo, total)} de {total}...') if tabela == 'documents' else None
    return inseridos, total


def _garantir_tabela(con, tabela):
    """Cria no site a tabela do programa instalado, com o mesmo desenho, se o site ainda não a tem. False se a origem não a tem."""
    if con.execute("SELECT 1 FROM o.sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone() is None: return False
    if con.execute("SELECT 1 FROM main.sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone() is None:
        con.execute(con.execute("SELECT sql FROM o.sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone()[0]); con.commit()
    return True


def _importar_extra(con, tabela, so_vazia):
    if not _garantir_tabela(con, tabela): return {'novos': 0, 'total': 0}
    if so_vazia and con.execute(f'SELECT 1 FROM main.{tabela} LIMIT 1').fetchone(): return {'novos': 0, 'total': con.execute(f'SELECT COUNT(*) FROM o.{tabela}').fetchone()[0]}
    novos, total = _importar_tabela(con, tabela, lambda *_: None); return {'novos': novos, 'total': total}


def _mesclar_config(dest, orig):
    """Junta a configuração do programa instalado à do site sem nunca voltar um ponto de busca. Devolve quantos itens mudaram."""
    n = 0
    for k, item in (orig.get('sync_state') or {}).items():
        atual = (dest.setdefault('sync_state', {})).get(k)
        if atual is None or int(item.get('last_saved_nsu') or 0) > int(atual.get('last_saved_nsu') or 0): dest['sync_state'][k] = item; n += 1
    for k, v in (orig.get('v028_bootstrap') or {}).items():
        if v and not dest.setdefault('v028_bootstrap', {}).get(k): dest['v028_bootstrap'][k] = True; n += 1
    for cnpj, fams in (orig.get('busca_cobertura') or {}).items():
        for fam, item in (fams or {}).items():
            atual = ((dest.setdefault('busca_cobertura', {})).setdefault(cnpj, {})).get(fam)
            if atual is None or str(item.get('ate') or '') > str(atual.get('ate') or ''): dest['busca_cobertura'][cnpj][fam] = item; n += 1
    for chave in ('nfse_prefs', 'company_names', 'fechamento', 'zip_importacao'):          # preferências: só entram se o site ainda não tem
        v = orig.get(chave)
        if v and chave not in dest: dest[chave] = v; n += 1
    for chave in ('nfe_sync_control', 'nfse_acesso'):
        for k, item in (orig.get(chave) or {}).items():
            if k not in dest.setdefault(chave, {}): dest[chave][k] = item; n += 1
    return n


def importar(origem, core, progresso=print):
    """Importa de `origem` (pasta Dados ou .zip) para o banco do site (`core`, o módulo do Exato). Devolve um resumo."""
    pasta, tmp = preparar_origem(origem)
    try:
        core.init_database(); resumo = {}
        con = sqlite3.connect(Path(core.DB_PATH).resolve().as_uri() + '?mode=rw', uri=True, timeout=60)
        try:
            con.execute('PRAGMA busy_timeout=60000')
            con.execute("ATTACH DATABASE ? AS o", ((pasta / 'central_fiscal.db').resolve().as_uri() + '?mode=ro',))          # só leitura: o banco do programa instalado nunca é alterado
            for t in TABELAS:
                novos, total = _importar_tabela(con, t, progresso); resumo[t] = {'novos': novos, 'total': total}
            for t in EXTRAS_CHAVE + EXTRAS_HISTORICO:
                try: resumo[t] = _importar_extra(con, t, so_vazia=t in EXTRAS_HISTORICO)
                except Exception as exc: resumo[t] = {'novos': 0, 'total': 0, 'erro': str(exc)[:120]}          # um histórico que não vem nunca derruba a importação
            con.execute('DETACH DATABASE o')
        finally:
            con.close()
        cfg_arq = pasta / 'config.json'; mudou = 0
        if cfg_arq.exists():
            try: orig = json.loads(cfg_arq.read_text(encoding='utf-8'))
            except Exception: orig = {}
            with core.CONFIG_LOCK:
                dest = core.load_config(); mudou = _mesclar_config(dest, orig); core.save_config(dest)
        resumo['configuracao'] = mudou
        return resumo
    finally:
        if tmp: shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='web.importar'); ap.add_argument('--origem', required=True, help='pasta Dados do programa instalado ou backup .zip')
    a = ap.parse_args(argv)
    from . import nucleo
    core = nucleo.core()
    try: r = importar(a.origem, core)
    except ValueError as exc: sys.exit(str(exc))
    print(f"Empresas: {r['companies']['novos']} nova(s) de {r['companies']['total']}.")
    print(f"Notas: {r['documents']['novos']} nova(s) de {r['documents']['total']} (as demais já existiam).")
    extras = {'document_exports': 'marcas de exportação', 'boxe_envios': 'envios do Box-e', 'sync_runs': 'histórico de buscas', 'busca_ocorrencias': 'ocorrências da busca', 'audit_runs': 'auditorias', 'empresas_removidas': 'empresas removidas'}
    for t, nome in extras.items():
        if t in r and r[t]['total']: print(f"{nome.capitalize()}: {r[t]['novos']} novo(s) de {r[t]['total']}." + (f" (não importado: {r[t]['erro']})" if r[t].get('erro') else ''))
    print(f"Pontos de busca e configuração: {r['configuracao']} item(ns) atualizado(s).")


if __name__ == '__main__': main()
