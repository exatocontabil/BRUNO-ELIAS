"""Agendador do Exato Web: dispara a rodada de busca sozinho a cada 4 horas (e quando alguém pede) sem deixar duas rodadas ao mesmo tempo."""
import threading, time
from datetime import datetime, timedelta

from .busca import AUTO_HORAS


class Agendador:
    def __init__(self, motor, intervalo=30, espera_inicial=20):
        self.motor = motor; self.intervalo = intervalo; self.espera_inicial = espera_inicial; self._parar = threading.Event(); self._th = None

    def ligado(self): return self.motor.cfg.get('web_auto', True) is not False

    def definir(self, ligado):
        self.motor.cfg['web_auto'] = bool(ligado); self.motor.salvar_cfg()

    def proxima(self):
        """Quando a próxima rodada automática deve começar (iso) ou ''."""
        if not self.ligado(): return ''
        ultima = str(self.motor.cfg.get('auto_round_last') or '')
        try: return (datetime.fromisoformat(ultima) + timedelta(hours=AUTO_HORAS)).isoformat(timespec='seconds') if ultima else 'agora'
        except Exception: return 'agora'

    def tick(self):
        """Um passo do agendador (testável): começa a rodada se está ligado, já passou da hora e não há outra rodando. Devolve True se começou."""
        try:
            if not self.motor.estado['rodando'] and self.motor.resumo_cfg().get('ativo'): threading.Thread(target=self.motor.enviar_resumo, daemon=True, name='resumo-diario').start()          # 1 vez por dia, depois das 7h
        except Exception: pass
        if not self.ligado() or not self.motor.vencida() or not self.motor.reservar(): return False
        threading.Thread(target=self.motor.rodada, kwargs={'reservado': True}, daemon=True, name='rodada-automatica').start(); return True

    def disparar(self, only=None, manual=True):
        """Pedido de uma pessoa (botão): começa já, em segundo plano. False se já há rodada."""
        if not self.motor.reservar(): return False
        threading.Thread(target=self.motor.rodada, kwargs={'only': only, 'manual': manual, 'reservado': True}, daemon=True, name='rodada-manual').start(); return True

    def iniciar(self):
        def laco():
            if self._parar.wait(self.espera_inicial): return
            while not self._parar.is_set():
                try: self.tick()
                except Exception: pass
                if self._parar.wait(self.intervalo): return
        self._th = threading.Thread(target=laco, daemon=True, name='agendador'); self._th.start()

    def parar(self): self._parar.set()
