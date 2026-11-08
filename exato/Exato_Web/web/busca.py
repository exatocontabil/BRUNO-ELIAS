"""Motor de busca do Exato Web: percorre as empresas e busca NF-e, NFC-e, CT-e e NFS-e com os certificados A1 do cofre.

Espelha, sem as telas, o que o programa instalado faz em `_run_sync_all`, `_finish_sync_all` e `_nfse_run_all` (V190). As rotinas fiscais protegidas e a
comunicação com a SEFAZ são as mesmas (`web.nucleo.core()`); aqui só há a ordem das tarefas, o uso do cofre e o registro do resultado.

Regras herdadas do programa: cada fluxo tem o seu ponto de continuação (NSU); a busca de NF-e respeita a espera da SEFAZ (nunca insiste); resposta desconhecida
da SEFAZ não vale como "sem notas"; cobertura só é gravada se a busca terminou bem; o resultado de cada tipo é anotado com a causa explicada."""
import os, re, sys, threading, time
from datetime import datetime, timedelta
from pathlib import Path

from . import config, nucleo
from .cofre import CofreErro

FAMILIAS_XML = ('nfe', 'nfce', 'cte')
ROTULO = {'nfe': 'NF-e', 'nfce': 'NFC-e', 'cte': 'CT-e', 'nfse': 'NFS-e'}
AUTO_HORAS = 4
ESCRITORIO = 'escritorio'


def _d(x): return re.sub(r'\D', '', str(x or ''))


class Cancelado(Exception): pass


class Motor:
    def __init__(self, core, cofre, nfse_transport=None, homologacao=False):
        self.core, self.cofre = core, cofre
        self.nfse_mod = nucleo.modulo('exato_nfse'); self.motivos = nucleo.modulo('exato_busca_motivos'); self.cobertura = nucleo.modulo('exato_cobertura'); self.proc = nucleo.modulo('exato_nfse_procuracao')
        self.nfse_transport = nfse_transport; self.homologacao = bool(homologacao)
        self.cfg = core.load_config(); self._cancelar = threading.Event(); self._trava = threading.Lock(); self._trava_repo = threading.Lock(); self.estado_repo = {'copiando': False, 'ultimo': None, 'resultado': None}
        self._trava_fech = threading.Lock(); self.estado_fech = {'fechando': False, 'ultimo': None, 'resultado': None}; self._trava_boxe = threading.Lock(); self._trava_resumo = threading.Lock(); self.estado_boxe = {'enviando': False, 'ultimo': None, 'resultado': None}; self.boxe_conectar = None; self.manifestador = None
        self.estado = {'rodando': False, 'empresa': '', 'indice': 0, 'total': 0, 'inicio': None, 'ultimo': None, 'resumo': None}
        for cod, (t, e, a, g) in CAUSAS_WEB.items(): self.motivos.CAUSAS.setdefault(cod, (t, e, a, g))          # causas próprias do site (explicadas em linguagem simples)

    # ------------------------------------------------------------ anotações
    def salvar_cfg(self):
        try:
            with self.core.CONFIG_LOCK: self.core.save_config(self.cfg)
        except Exception: pass

    def ocorrencia(self, cnpj, tipos, codigo, texto=''):
        try: self.motivos.registrar(str(self.core.DB_PATH), cnpj, tipos, codigo, texto)
        except Exception: pass

    def cancelar(self): self._cancelar.set()
    def cancelado(self): return self._cancelar.is_set()

    # ------------------------------------------------------------ certificado de cada empresa
    def certificado_para(self, cnpj):
        """Qual A1 do cofre usar: o da própria empresa; se não há, o do escritório (procuração). None se nenhum."""
        d = _d(cnpj)
        for cid in (d, ESCRITORIO):
            info = self.cofre.info(cid)
            if info and not info.get('vencido') and info.get('validade', '9999') >= datetime.now().date().isoformat(): return cid
        return None

    # ------------------------------------------------------------ NF-e, NFC-e e CT-e (espelha _run_sync_all)
    def buscar_xml(self, cnpj, thumb):
        core, cfg = self.core, self.cfg; cnpj = _d(cnpj); homolog = self.homologacao
        boot = cfg.setdefault('v028_bootstrap', {}); starts = {}
        for f in ('nfe', 'nfce'):
            key = core._sync_state_key(cnpj, f)
            if f == 'nfe' and core._nfe_requires_full_resync(cfg, cnpj): starts[f] = 0; continue
            starts[f] = core.get_saved_nsu(cfg, cnpj, f) if boot.get(key, False) else 0
        starts['cte_emitente'] = core.get_saved_nsu(cfg, cnpj, 'cte_emitente'); starts['cte_tomador'] = core.get_saved_nsu(cfg, cnpj, 'cte_tomador')
        for f in ('nfe', 'nfce'):          # V173: ponto zerado mas o arquivo já tem notas: continua do que o arquivo diz (menos a folga), sem baixar tudo de novo
            if str(starts.get(f) or '0') in ('0', '') and f != 'nfe':
                nsu_banco = core.db_max_source_nsu(cnpj, f)
                if nsu_banco > 0: starts[f] = max(0, nsu_banco - core.NSU_FOLGA)
        run_id = core.db_start_run(cnpj); core.busca_progresso_iniciar(cnpj); results = {}; lock = threading.Lock()

        def execute_stream(fetch, state_key, label, stream_start, actor_code='', family=''):
            novos = dup = 0
            def cb(evt):
                nonlocal novos, dup
                info_evt = evt.get('info') or {}; docs = info_evt.get('documents') or []
                if actor_code:
                    for d in docs: d['actor_code'] = str(actor_code); d['actor_label'] = label
                    info_evt['actor_code'] = str(actor_code); info_evt['actor_label'] = label; evt['info'] = info_evt
                try:
                    a, b = core.db_upsert_documents(cnpj, docs); novos += a; dup += b
                except Exception: return
                returned = info_evt.get('ultNSURet') or info_evt.get('ultNSU') or ''
                if returned not in (None, ''):
                    try:
                        meta = {'nfe_actor_filter': label, 'actor_bootstrapped': True} if family == 'nfe' else {}
                        if info_evt.get('maxNSU') not in ('', None): meta['max_nsu'] = int(str(info_evt['maxNSU']))
                        core.save_nsu_state(cfg, cnpj, state_key, returned, len(docs), metadata=meta)
                    except Exception: pass
            r = core.sync_documents_automatically(fetch, thumb, cnpj, f'{family}_{actor_code}' if actor_code else family, start_nsu=stream_start, progress_cb=cb, stop_cb=self.cancelado)
            r['new_count'] = novos; r['duplicate_count'] = dup; r['stream_name'] = label; r['state_key'] = state_key
            i657 = r.get('last_info') or {}
            if str(i657.get('cstat') or '').strip() == '657':
                r['retry_after_hours'] = 0; r['end_reason'] = r['message'] = core.nfe_cstat_user_message('657', i657.get('motivo'))
            return r

        def juntar(streams, extra=None):
            docs = []; b = n = d = 0; hist = []; razoes = []; ok = True; last = {}
            for r in streams:
                docs.extend(r.get('documents') or []); b += int(r.get('batches') or 0); n += int(r.get('new_count') or 0); d += int(r.get('duplicate_count') or 0)
                hist.extend(r.get('batch_history') or []); razoes.append(f"{r.get('stream_name', '')}: {r.get('end_reason', '')}"); ok = ok and bool(r.get('ok', False)); last = r.get('last_info') or last
            out = {'ok': ok and not self.cancelado(), 'documents': docs, 'batches': b, 'last_nsu': None, 'next_nsu': None, 'last_info': last, 'batch_history': hist, 'new_count': n, 'duplicate_count': d,
                   'end_reason': ' • '.join(x for x in razoes if x)}
            out.update(extra or {}); return out

        def familia(family):
            try:
                if family == 'nfe':
                    espera, control = core.nfe_cooldown_remaining(cfg, cnpj)
                    if espera > 0:
                        prox = str(control.get('next_actor') or '1'); lab = 'Emitente / Saída' if prox == '1' else 'Destinatário / Entrada'
                        res = {'ok': False, 'documents': [], 'batches': 0, 'last_nsu': None, 'next_nsu': None, 'last_info': {'cstat': str(control.get('last_cstat') or ''), 'motivo': str(control.get('last_end_reason') or '')},
                               'new_count': 0, 'duplicate_count': 0, 'deferred_actor': prox, 'deferred_label': lab, 'cooldown_remaining': espera, 'end_reason': f'aguardando {core._format_nfe_wait(espera)} para consultar {lab}'}
                    else:
                        def ator(a):
                            lab, suf = core.nfe_actor_meta(a); chave = core._sync_state_key(cnpj, suf); item = core.get_sync_state_item(cfg, cnpj, suf)
                            salvo = core.get_saved_nsu(cfg, cnpj, suf); amax = core.db_max_actor_source_nsu(cnpj, 'nfe', a)
                            ini = (min(salvo, amax) if amax > 0 else 0) if str(item.get('bootstrap_actor_code') or '') == '9' else (min(salvo, amax) if amax > 0 else salvo)
                            fetch = lambda th, c, n, aa=int(a): core._fetch_log('NF-e', c, n, lambda: core.test_sef_nfe_webservice(th, c, homolog, 1, n, aa))
                            r = execute_stream(fetch, chave, lab, ini, actor_code=a, family='nfe'); r['actor_code'] = a
                            cst = str((r.get('last_info') or {}).get('cstat') or '')
                            if cst and cst != 'não identificado': core.record_nfe_actor_result(cfg, cnpj, a, cst, r.get('end_reason', ''))
                            ctl = core.get_nfe_sync_control(cfg, cnpj); prox = str(ctl.get('next_actor') or ('1' if a == '2' else '2'))
                            r['deferred_actor'] = prox; r['deferred_label'] = 'Emitente / Saída' if prox == '1' else 'Destinatário / Entrada'
                            until = core._parse_iso_datetime(ctl.get('cooldown_until')); r['cooldown_remaining'] = max(0, int(((until or datetime.now()) - datetime.now()).total_seconds()))
                            return r
                        a1 = core.choose_nfe_actor(cfg, cnpj); primeiro = ator(a1); streams = [primeiro]
                        if core.nfe_can_chain_actor(primeiro) and not self.cancelado(): streams.append(ator('1' if str(a1) == '2' else '2'))
                        ctl = core.get_nfe_sync_control(cfg, cnpj); prox = str(ctl.get('next_actor') or '1'); resta, _ = core.nfe_cooldown_remaining(cfg, cnpj)
                        res = juntar(streams, {'deferred_actor': prox, 'deferred_label': 'Emitente / Saída' if prox == '1' else 'Destinatário / Entrada', 'cooldown_remaining': resta})
                elif family == 'nfce':
                    fetch = lambda th, c, n: core._fetch_log('NFC-e', c, n, lambda: core.test_sef_nfce_webservice(th, c, 1, 3, n))
                    res = execute_stream(fetch, core._sync_state_key(cnpj, 'nfce'), 'Geral', starts['nfce'], family='nfce')
                else:
                    streams = []
                    for ator_, lab, suf in ((1, 'Emitente / Saída', 'cte_emitente'), (2, 'Tomador / Entrada', 'cte_tomador')):
                        if self.cancelado(): break
                        fetch = lambda th, c, n, a=ator_: core._fetch_log('CT-e', c, n, lambda: core.test_sef_cte_webservice(th, c, 1, a, n))
                        streams.append(execute_stream(fetch, core._sync_state_key(cnpj, suf), lab, starts[suf], family='cte'))
                    res = juntar(streams); res['ok'] = res['ok'] and len(streams) == 2
            except Exception as exc:
                res = {'ok': False, 'documents': [], 'batches': 0, 'last_nsu': None, 'message': str(exc), 'last_info': {}, 'new_count': 0, 'duplicate_count': 0}
            with lock: results[family] = res

        ths = [threading.Thread(target=familia, args=(f,), daemon=True) for f in FAMILIAS_XML]
        for t in ths: t.start()
        for t in ths: t.join()
        core.busca_progresso_fim()
        return self._concluir_xml(cnpj, results, run_id)

    def _concluir_xml(self, cnpj, results, run_id):
        """Espelha `_finish_sync_all`: grava os pontos de continuação e a cobertura (só se terminou bem), anota a causa de cada tipo e fecha o registro da busca."""
        core, cfg = self.core, self.cfg; novos = dup = 0; cancel = self.cancelado()
        for fam, res in results.items():
            if res.get('ok') and res.get('last_nsu') is not None:
                try:
                    meta = {}; info = res.get('last_info') or {}
                    if info.get('maxNSU') not in ('', None): meta['max_nsu'] = int(str(info['maxNSU']))
                    if res.get('end_reason'): meta['end_reason'] = res['end_reason']
                    core.save_nsu_state(cfg, cnpj, fam, res['last_nsu'], len(res.get('documents') or []), metadata=meta)
                    cfg.setdefault('v028_bootstrap', {})[core._sync_state_key(cnpj, fam)] = True
                except Exception: pass
            if res.get('ok'):
                try: self.cobertura.registrar(cfg, cnpj, fam, nsu=res.get('last_nsu'))
                except Exception: pass
            novos += int(res.get('new_count') or 0); dup += int(res.get('duplicate_count') or 0)
        adiado = any(bool((r or {}).get('deferred_actor')) for r in results.values()) and not any((not (r or {}).get('ok')) and not (r or {}).get('deferred_actor') for r in results.values())
        for fam in FAMILIAS_XML:
            rr = results.get(fam)
            if rr is None: continue
            info = rr.get('last_info') or {}; cst = str(info.get('cstat') or '').strip()
            texto = ' '.join(str(x or '') for x in (rr.get('message') if isinstance(rr.get('message'), str) else '', rr.get('end_reason'), info.get('motivo'))).strip()
            if rr.get('deferred_actor'): cod = 'janela'
            elif rr.get('ok'): cod = 'ok' if int(rr.get('new_count') or 0) else 'sem_novas'
            elif cancel: cod = 'cancelada_pelo_usuario'
            else: cod = self.motivos.classificar(texto, cst)
            self.ocorrencia(cnpj, fam, cod, (f'cStat {cst}: ' if cst else '') + ((re.sub(r'\s+', ' ', str(info.get('motivo') or '')).strip() or texto) if cod in ('ok', 'sem_novas', 'janela') else texto))
            if rr.get('ok'):
                try:
                    n = len(core.db_canceladas_sem_evento(cnpj, fam))
                    if n: self.ocorrencia(cnpj, fam, 'cancelada_sem_evento', f'{n} nota(s) cancelada(s) sem o XML completo do cancelamento')
                except Exception: pass
        todos_ok = (not cancel) and len(results) == 3 and all((results.get(f) or {}).get('ok') for f in FAMILIAS_XML) and not adiado
        estado = 'Concluído' if todos_ok else ('Cancelado' if cancel else ('Aguardando próxima janela' if adiado else 'Concluído com observações'))
        try: core.db_update_run(run_id, estado, finished=True, total_found=sum(len((r or {}).get('documents') or []) for r in results.values()), new_count=novos, duplicate_count=dup,
                                error_text='Cancelado' if cancel else ('' if todos_ok or adiado else 'Uma ou mais fontes não foram concluídas.'))
        except Exception: pass
        self.salvar_cfg()
        return {'ok': todos_ok, 'estado': estado, 'novos': novos, 'duplicados': dup, 'adiado': adiado, 'results': results}

    # ------------------------------------------------------------ NFS-e (espelha _nfse_run_all)
    def cursor_nfse(self, cnpj):
        salvo = self.core.get_saved_nsu(self.cfg, cnpj, 'nfse')
        if salvo > 0: return salvo
        try: no_banco = int(self.core.db_max_source_nsu(cnpj, 'nfse') or 0)
        except Exception: no_banco = 0
        return max(0, no_banco - self.core.NSU_FOLGA) if no_banco > 0 else 0

    def buscar_nfse(self, cnpj, thumb, modo):
        """`modo`: 'proprio' (A1 da empresa) ou 'procuracao' (A1 do escritório). Devolve dict com o resultado; levanta nfse_mod.NfseError se o Emissor Nacional recusar."""
        core, cfg = self.core, self.cfg; cnpj = _d(cnpj); run_id = core.db_start_run(cnpj); last = self.cursor_nfse(cnpj)
        kw = {'transport': self.nfse_transport} if self.nfse_transport else {}
        try:
            items, new_last, info = self.nfse_mod.fetch_all_new(thumb, last, self.homologacao, cnpj, cancelled=self.cancelado, **kw)
            res = core.db_upsert_nfse_items(cnpj, items)
            core.save_nsu_state(cfg, cnpj, 'nfse', new_last, len(items), metadata={'environment': 'homologacao' if self.homologacao else 'producao'})
            cancelada = bool(info.get('cancelled'))
            if not cancelada: self.cobertura.registrar(cfg, cnpj, 'nfse', nsu=new_last)
            if modo == 'procuracao' and not cancelada: self.proc.registrar(cfg, cnpj, 'procuracao', True, 'consulta aceita pelo Emissor Nacional')
            self.ocorrencia(cnpj, 'nfse', 'cancelada_pelo_usuario' if cancelada else ('ok' if res['new'] else 'sem_novas'))
            try:
                n = len(core.db_canceladas_sem_evento(cnpj, 'nfse'))
                if n: self.ocorrencia(cnpj, 'nfse', 'cancelada_sem_evento', f'{n} nota(s) cancelada(s) sem o XML do evento')
            except Exception: pass
            core.db_update_run(run_id, 'Cancelado' if cancelada else 'Concluído', finished=True, total_found=len(items), new_count=res['new'], duplicate_count=res['duplicate'], error_text='Cancelado' if cancelada else '')
            self.salvar_cfg(); return {'ok': not cancelada, 'novos': res['new'], 'duplicados': res['duplicate'], 'canceladas': res['cancelled']}
        except self.nfse_mod.NfseError as exc:
            msg = self.proc.mensagem(modo, exc)
            if modo == 'procuracao': self.proc.registrar(cfg, cnpj, 'procuracao', False, str(exc))
            if modo == 'procuracao' and self.proc.parece_recusa(exc): self.ocorrencia(cnpj, 'nfse', self.proc.CODIGO_RECUSA, str(exc))
            else: self.ocorrencia(cnpj, 'nfse', self.motivos.classificar(str(exc), '', 'nfse'), str(exc))
            core.db_update_run(run_id, 'Não concluído', finished=True, error_text=msg); self.salvar_cfg()
            return {'ok': False, 'erro': msg, 'novos': 0}

    # ------------------------------------------------------------ rodada (espelha _auto_round_*)
    def reservar(self):
        """Garante, já, que só uma rodada vai existir (quem pede a rodada em segundo plano reserva antes de abrir a linha de trabalho)."""
        if not self._trava.acquire(blocking=False): return False
        self.estado['rodando'] = True; return True

    def rodada(self, only=None, manual=False, reservado=False):
        """Percorre as empresas: NF-e/NFC-e/CT-e e NFS-e. Uma de cada vez, nunca duas rodadas ao mesmo tempo. Devolve o resumo."""
        if not reservado and not self.reservar(): return {'ja_rodando': True}
        self._cancelar.clear(); core = self.core
        try:
            empresas = [c for c in core.db_list_companies(5000) if core._is_valid_cnpj(_d(c.get('cnpj')))]
            if only:
                keep = {_d(x) for x in only}; empresas = [c for c in empresas if _d(c.get('cnpj')) in keep]
            self.estado.update(rodando=True, total=len(empresas), indice=0, inicio=datetime.now().isoformat(timespec='seconds'), resumo=None)
            resumo = {'empresas': len(empresas), 'xml_ok': 0, 'xml_obs': 0, 'xml_novos': 0, 'nfse_novos': 0, 'nfse_problemas': 0, 'sem_certificado': 0, 'manual': manual}
            for i, comp in enumerate(empresas, 1):
                if self.cancelado(): break
                cnpj = _d(comp.get('cnpj')); self.estado.update(empresa=comp.get('name') or cnpj, indice=i)
                cid = self.certificado_para(cnpj)
                if cid is None:
                    resumo['sem_certificado'] += 1; self.ocorrencia(cnpj, FAMILIAS_XML + ('nfse',), 'sem_a1', '')
                    continue
                try:
                    with self.cofre.usar(cid) as thumb:
                        r = self.buscar_xml(cnpj, thumb)
                        resumo['xml_ok' if r['ok'] or r['adiado'] else 'xml_obs'] += 1; resumo['xml_novos'] += r['novos']
                        if self.manif_cfg()['auto'].get(cnpj) and not self.cancelado():          # só as empresas ligadas de propósito: a próxima busca traz o XML completo
                            try: m = self.manifestar(cnpj, limite=100, por='automático'); resumo['manifestadas'] = resumo.get('manifestadas', 0) + m['registradas']
                            except Exception: pass
                        if not self.cancelado():
                            modo = self.proc.modo_para(self._doc_do_certificado(cid), cnpj) if cid == ESCRITORIO else 'proprio'
                            if modo != 'procuracao' or not self.proc.ligada(self.cfg) or self.proc.tentar_agora(self.cfg, cnpj, manual=manual):
                                n = self.buscar_nfse(cnpj, thumb, modo); resumo['nfse_novos'] += n.get('novos', 0)
                                if not n['ok'] and not (modo == 'procuracao' and not manual): resumo['nfse_problemas'] += 1
                except CofreErro as exc:
                    self.ocorrencia(cnpj, FAMILIAS_XML + ('nfse',), 'sem_a1', str(exc)); resumo['sem_certificado'] += 1
                except Exception:
                    if os.environ.get('EXATO_WEB_DEBUG'): import traceback; traceback.print_exc()
                    try: self.core.log_exception(f'Web: busca da empresa {cnpj}', sys.exc_info())
                    except Exception: pass
                    self.ocorrencia(cnpj, FAMILIAS_XML, 'erro_desconhecido', 'erro inesperado'); resumo['xml_obs'] += 1
            if not self.cancelado():
                self.cfg['auto_round_last'] = datetime.now().isoformat(timespec='seconds'); self.salvar_cfg()
            if not self.cancelado():
                for etapa in (self.copiar_repositorio, self.enviar_boxe, self.fechar_meses):          # depois da busca: copia os XMLs, manda as NFS-e ao Box-e e fecha os meses prontos
                    try: etapa()
                    except Exception: pass
            resumo['cancelada'] = self.cancelado(); self.estado.update(ultimo=datetime.now().isoformat(timespec='seconds'), resumo=resumo)
            return resumo
        finally:
            self.estado.update(rodando=False, empresa=''); self._trava.release()

    # ------------------------------------------------------------ Repositório (XMLs em arquivos organizados, guardados para sempre)
    def copiar_repositorio(self, ignorar_pausa=False):
        """Copia para a pasta de arquivos os XMLs que ainda não estão lá (Empresa - CNPJ / Ano / Mês / Tipo). Nunca sobrescreve e nunca apaga."""
        repo = nucleo.modulo('exato_repositorio')
        if not self._trava_repo.acquire(blocking=False): return {'ja_copiando': True}
        try:
            self.estado_repo.update(copiando=True)
            r = repo.copiar_pendentes(str(self.core.DB_PATH), str(config.ARQUIVOS), cancelar=self.cancelado_repo, ignorar_pausa=ignorar_pausa)
            self.estado_repo.update(ultimo=datetime.now().isoformat(timespec='seconds'), resultado=r); return r
        except Exception:
            try: self.core.log_exception('Web: cópia para o Repositório', sys.exc_info())
            except Exception: pass
            return {'ok': False, 'motivo': 'falha'}
        finally:
            self.estado_repo.update(copiando=False); self._trava_repo.release()

    def cancelado_repo(self): return False

    # ------------------------------------------------------------ Fechamento do mês (PDFs + ZIPs de importação da Domínio no Repositório)
    def _nome_empresa(self, cnpj, nome_banco):
        try: return self.core.db_company_verified_name(cnpj)
        except Exception: return nome_banco, False

    def _coberto(self, cnpj, mes):
        """A busca já passou do fim do mês? (vale a cobertura mais recente entre NF-e, NFC-e e CT-e; sem informação, vale como sim)"""
        try:
            ano, m = int(mes[:4]), int(mes[5:]); fim = datetime(ano + (m == 12), m % 12 + 1, 1).date()
            ate = nucleo.modulo('exato_situacao_busca').cobertura_empresa(str(self.core.DB_PATH), self.cfg, None, cnpj)
            return True if ate is None else ate >= fim
        except Exception: return True

    def fechamento_cfg(self):
        c = self.cfg.setdefault('fechamento', {}); c.setdefault('ativo', True); c.setdefault('dias', nucleo.modulo('exato_fechamento').DIAS_PADRAO); return c

    def fechar_meses(self, manual=False):
        """Fecha os meses prontos (encerrados, sem nota nova há alguns dias, tudo copiado, busca já passou do fim). `manual`: sem esperar os dias. Nunca sobrescreve."""
        fech = nucleo.modulo('exato_fechamento'); cfgf = self.fechamento_cfg()
        if not manual and not cfgf.get('ativo', True): return {'desligado': True}
        if not self._trava_fech.acquire(blocking=False): return {'ja_fechando': True}
        try:
            self.estado_fech.update(fechando=True); estado = self.cfg.setdefault('fechamento_estado', {})
            logo = self.core.LOGO_PATH if getattr(self.core, 'LOGO_PATH', None) and Path(self.core.LOGO_PATH).exists() else None
            res = fech.fechar_pendentes(str(self.core.DB_PATH), str(config.ARQUIVOS), estado, dias=int(cfgf.get('dias') or fech.DIAS_PADRAO), forcar=manual, nome_empresa=self._nome_empresa, logo=logo,
                                        cancelar=(lambda: False) if manual else self.cancelado, limite=None if manual else fech.LIMITE_RODADA, coberto=self._coberto)
            if len(estado) > 6000:
                for k in list(estado)[:len(estado) - 6000]: estado.pop(k, None)
            self.salvar_cfg(); res['empresas'] = sorted(res.get('empresas') or []); self.estado_fech.update(ultimo=datetime.now().isoformat(timespec='seconds'), resultado={k: v for k, v in res.items() if k != 'feitos_lista'}); return res
        except Exception:
            try: self.core.log_exception('Web: fechamento do mês', sys.exc_info())
            except Exception: pass
            return {'erros': ['erro']}
        finally:
            self.estado_fech.update(fechando=False); self._trava_fech.release()

    def pasta_fechamento(self, cnpj, mes, nome=''):
        repo = nucleo.modulo('exato_repositorio'); fech = nucleo.modulo('exato_fechamento'); pasta_repo = repo._pasta_repo(str(config.ARQUIVOS))
        return Path(fech._pasta_fechamento(pasta_repo, repo._Empresas(pasta_repo, self._nome_empresa).pasta(_d(cnpj), nome), mes))

    def fechamento_info(self, cnpj, mes, nome=''):
        """Marca do fechamento (dict: arquivos, revisao, fechado_em...) ou None."""
        try: return nucleo.modulo('exato_fechamento').ler_marca(str(self.pasta_fechamento(cnpj, mes, nome)))
        except Exception: return None

    def fechamento_linhas(self):
        fech = nucleo.modulo('exato_fechamento'); dias = int(self.fechamento_cfg().get('dias') or fech.DIAS_PADRAO); saida = []
        for m in fech.meses(str(self.core.DB_PATH)):
            motivo = fech.motivo(m, dias, coberto=self._coberto); marca = self.fechamento_info(m['cnpj'], m['mes'], m.get('nome') or '')
            fechado = bool(marca) and marca.get('assinatura') == m['assinatura']
            saida.append({'cnpj': m['cnpj'], 'nome': m.get('nome') or m['cnpj'], 'mes': m['mes'], 'notas': m['notas'], 'motivo': '' if fechado else motivo, 'fechado': bool(marca), 'em_dia': fechado,
                          'revisao': int((marca or {}).get('revisao') or 0), 'arquivos': list((marca or {}).get('arquivos') or [])})
        return sorted(saida, key=lambda x: (x['mes'], x['nome']), reverse=True)

    # ------------------------------------------------------------ Box-e (NFS-e por e-mail para a Domínio)
    def boxe_cfg(self):
        boxe = nucleo.modulo('exato_boxe'); c = self.cfg.setdefault('boxe', {})
        for k, v in (('ativo', False), ('destino', boxe.DESTINO_PADRAO), ('servidor', ''), ('porta', 587), ('seguranca', 'STARTTLS'), ('usuario', ''), ('senha_protegida', ''), ('remetente', ''), ('tomadas', False), ('desde', '')): c.setdefault(k, v)
        return c

    def boxe_cfg_envio(self):
        c = dict(self.boxe_cfg()); c['senha'] = self.cofre.abrir_texto(c.get('senha_protegida') or '') if c.get('senha_protegida') else ''; return c

    def boxe_pronto(self): return nucleo.modulo('exato_boxe').configurado(self.boxe_cfg_envio())

    def enviar_boxe(self):
        """Envia por e-mail ao Box-e as NFS-e novas, uma única vez cada (marca no Repositório). Só se o Box-e estiver ligado e configurado."""
        boxe = nucleo.modulo('exato_boxe'); c = self.boxe_cfg()
        if not c.get('ativo') or not self.boxe_pronto(): return {'ok': True, 'motivo': 'desligado'}
        if not self._trava_boxe.acquire(blocking=False): return {'ok': True, 'motivo': 'ja_enviando'}
        try:
            self.estado_boxe.update(enviando=True)
            r = boxe.enviar_pendentes(str(self.core.DB_PATH), self.boxe_cfg_envio(), str(config.ARQUIVOS), cancelar=self.cancelado, computador='site', incluir_tomadas=bool(c.get('tomadas')),
                                      conectar=self.boxe_conectar, desde=str(c.get('desde') or ''))
            self.estado_boxe.update(ultimo=datetime.now().isoformat(timespec='seconds'), resultado=r); return r
        except Exception:
            try: self.core.log_exception('Web: Box-e', sys.exc_info())
            except Exception: pass
            return {'ok': False, 'motivo': 'falha'}
        finally:
            self.estado_boxe.update(enviando=False); self._trava_boxe.release()

    # ------------------------------------------------------------ Manifestação do destinatário (Ciência da Operação)
    def manif_cfg(self):
        c = self.cfg.setdefault('manifestacao', {}); c.setdefault('auto', {}); c.setdefault('homologacao', False); return c

    def manifestar(self, cnpj, limite=50, por=''):
        """Manifesta a Ciência das NF-e pendentes da empresa (só quando pedido, ou se a empresa foi ligada para o modo automático)."""
        if self.manifestador is None: return {'registradas': 0, 'ja': 0, 'erros': ['A manifestação não está disponível.'], 'restantes': 0}
        self.manifestador.homologacao = bool(self.manif_cfg().get('homologacao')); return self.manifestador.manifestar(cnpj, limite=limite, por=por, cancelar=None)

    # ------------------------------------------------------------ Resumo diário por e-mail (usa o e-mail do Box-e)
    def resumo_cfg(self):
        c = self.cfg.setdefault('resumo_diario', {})
        for k, v in (('ativo', False), ('destino', ''), ('ultimo', '')): c.setdefault(k, v)
        return c

    def resumo_montar(self, hoje=None):
        return nucleo.modulo('exato_resumo_diario').montar(str(self.core.DB_PATH), self.cfg, None, hoje=hoje, canceladas_sem_evento=lambda c: len(self.core.db_canceladas_sem_evento(c, '')), acessos=dict(self.cfg.get('nfse_acesso') or {}))

    def enviar_resumo(self, forcar=False, agora=None):
        """Uma vez por dia, depois das 7h, manda o resumo por e-mail. `forcar`: manda agora (teste), sem marcar o dia. Devolve {'enviado','motivo'}."""
        rd = nucleo.modulo('exato_resumo_diario'); c = self.resumo_cfg(); agora = agora or datetime.now()
        if not forcar and (not rd.deve_enviar(c, agora) or self.estado['rodando']): return {'enviado': False, 'motivo': 'nao_e_hora'}
        if not c.get('destino'): return {'enviado': False, 'motivo': 'sem_destino'}
        if not self.boxe_pronto(): return {'enviado': False, 'motivo': 'sem_email'}
        if not self._trava_resumo.acquire(blocking=False): return {'enviado': False, 'motivo': 'enviando'}
        try:
            rd.enviar(self.boxe_cfg_envio(), c['destino'], self.resumo_montar(agora.date()), conectar=self.boxe_conectar)
            if not forcar: c['ultimo'] = agora.strftime('%Y-%m-%d'); self.salvar_cfg()
            return {'enviado': True, 'motivo': ''}
        except Exception as exc:
            try: self.core.log_exception('Web: resumo diário', sys.exc_info())
            except Exception: pass
            return {'enviado': False, 'motivo': 'falha', 'erro': nucleo.modulo('exato_boxe').erro_amigavel(exc)}
        finally:
            self._trava_resumo.release()

    # ------------------------------------------------------------ Auditoria: busca só do que falta (espelha _audit_buscar_faltantes, V185)
    def buscar_faltantes(self, cnpj, lista, thumb):
        """Busca SÓ a faixa de NSU em volta das notas "SAT sem XML na Central". Nunca move o ponto de continuação da busca normal. `lista`: itens de
        `exato_auditoria_busca.faltantes`. Devolve {'novos','erros','esperar','concluidos','restam','cancelado'}."""
        core, cnpj = self.core, _d(cnpj); ab = nucleo.modulo('exato_auditoria_busca'); grupos = ab.agrupar(lista); homolog = self.homologacao
        resumo = {'novos': 0, 'erros': [], 'esperar': [], 'concluidos': [], 'cancelado': False}
        core.busca_progresso_iniciar(cnpj)
        try:
            for (fam, ator), itens in grupos.items():
                if self.cancelado(): resumo['cancelado'] = True; break
                nome = ab.NOMES.get(fam, fam) + (' (saída)' if ator == '1' else ' (entrada)' if ator == '2' else '')
                plano = ab.janela(str(core.DB_PATH), cnpj, fam, ator, itens)
                if fam == 'nfe':
                    espera, _c = core.nfe_cooldown_remaining(self.cfg, cnpj)
                    if espera > 0: resumo['esperar'].append(f'{nome}: a SEFAZ pede para esperar {core._format_nfe_wait(espera)}'); continue
                    fetch = lambda th, c, n, a=int(ator or 2): core._fetch_log('NF-e', c, n, lambda: core.test_sef_nfe_webservice(th, c, homolog, 1, n, a))
                else:
                    fetch = lambda th, c, n: core._fetch_log('NFC-e', c, n, lambda: core.test_sef_nfce_webservice(th, c, 1, 3, n))
                parou = [False]
                def cb(evt, ator=ator, nome=nome, plano=plano, parou=parou):
                    info = evt.get('info') or {}; docs = info.get('documents') or []
                    if ator:
                        for d in docs: d['actor_code'] = str(ator); d['actor_label'] = core.nfe_actor_meta(ator)[0]
                    try: nn, _nd = core.db_upsert_documents(cnpj, docs); resumo['novos'] += nn
                    except Exception as exc: resumo['erros'].append(f'{nome}: não consegui gravar ({core.friendly_message(str(exc))})'); parou[0] = True
                    retorno = info.get('ultNSURet') or info.get('ultNSU') or ''
                    try:
                        if plano['fim'] and int(str(retorno)) >= plano['fim']: parou[0] = True          # já passou das notas que faltam
                    except Exception: pass
                r = core.sync_documents_automatically(fetch, thumb, cnpj, f'{fam}_{ator}_dirigida', start_nsu=plano['inicio'], progress_cb=cb, stop_cb=lambda: parou[0] or self.cancelado())
                info_fim = r.get('last_info') or {}
                if fam == 'nfe' and str(info_fim.get('cstat') or ''):
                    try: core.record_nfe_actor_result(self.cfg, cnpj, str(ator or 2), str(info_fim.get('cstat')), str(info_fim.get('motivo') or r.get('end_reason') or ''))
                    except Exception: pass
                if r.get('cancelled') and not parou[0]: resumo['cancelado'] = True; break
                if not r.get('ok') and not parou[0] and not r.get('cancelled'): resumo['erros'].append(f"{nome}: {core.friendly_message(str(r.get('message') or r.get('end_reason') or 'a SEFAZ não respondeu'))}")
                else: resumo['concluidos'].append((fam, ator))
        except Exception:
            try: core.log_exception('Web: auditoria, busca dirigida', sys.exc_info())
            except Exception: pass
            resumo['erros'].append('Erro inesperado na busca (guardado no registro de erros).')
        finally:
            core.busca_progresso_fim()
        feitos = set(resumo['concluidos'])
        def atores_do(i): return [i['ator']] if i['ator'] or i['familia'] != 'nfe' else ['1', '2']
        tentados = {i['chave'] for i in lista if all((i['familia'], a) in feitos for a in atores_do(i))}
        resumo['restam'] = ab.ainda_sem_xml(str(core.DB_PATH), cnpj, lista); carimbo = datetime.now().strftime('%d/%m %H:%M')
        for i in resumo['restam']:
            if i['chave'] in tentados: core.AUDIT_TENTADAS[i['chave']] = f'Procurei na SEFAZ em {carimbo} e ela não entregou este XML (conferi a faixa de notas em volta). Se a nota é válida, tente de novo mais tarde.'
        self.salvar_cfg(); return resumo

    def _doc_do_certificado(self, cid):
        info = self.cofre.info(cid) or {}; return info.get('titular_cnpj') or ''

    def vencida(self):
        """A rodada automática já deveria ter rodado? (a última foi há mais de AUTO_HORAS)"""
        ultima = str(self.cfg.get('auto_round_last') or '')
        if not ultima: return True
        try: return datetime.now() - datetime.fromisoformat(ultima) >= timedelta(hours=AUTO_HORAS)
        except Exception: return True


CAUSAS_WEB = {
    'sem_a1': ('Esta empresa não tem certificado A1 guardado no site',
               'O site só busca com certificados A1 guardados no cofre. Nem esta empresa nem o escritório (procuração) têm um certificado válido guardado.',
               'Na tela Certificados A1, envie o certificado A1 da empresa (ou do escritório, se houver procuração).', 'aviso'),
}
