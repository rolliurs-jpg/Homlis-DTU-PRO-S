"""Régulation locale du HMS ; aucun réglage de batterie modifié."""
import math
import threading
import time

class SurplusController:
    def __init__(self, proxy, sample, enabled=False, rated_w=1000, dtu=None):
        self.proxy, self.sample = proxy, sample
        self.enabled, self.rated_w = enabled, rated_w
        # After a service restart, an already enabled controller must also
        # re-authorize its proxy commands.  Otherwise only the DTU is limited
        # and the two Bluetooth panels keep injecting at 100 %.
        if self.proxy is not None and hasattr(self.proxy, "config"):
            self.proxy.config["commands_enabled"] = bool(enabled)
        self.dtu = dtu
        self.full_since = self.last_sample = None
        self.full = False
        # Après un redémarrage alors que le pilotage est déjà actif, ne pas
        # envoyer une consigne 100 % avant d'avoir reconstruit deux minutes
        # de mesures cohérentes.
        self.hold_until = time.time() + 120 if enabled else 0.0
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._state = {}

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def evaluate(self, s, now):
        p, b = s.get('proxy', {}), s.get('battery', {})
        result = dict(mode='automatic' if self.enabled else 'paused', commands_enabled=self.enabled,
                      controlled_panels=6 if self.dtu else 2, battery_full_confirmed=False, hms1000_limit_pct=None, dtu_limit_pct=100 if self.dtu else None)
        try:
            values = [s['grid_w'], s['timestamp'], b['timestamp'], b['soc_pct'],
                      b['ac_charge_w'], b['ac_discharge_w'], p['power_w'], p['timestamp'], p['limit_pct']]
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
                raise ValueError()
            if not all(0 <= now-t <= 45 for t in (s['timestamp'], b['timestamp'], p['timestamp'])):
                raise ValueError()
            if p['state'] != 'online' or not 0 <= b['soc_pct'] <= 100 or not 0 <= p['limit_pct'] <= 100:
                raise ValueError()
            if min(b['ac_charge_w'], b['ac_discharge_w'], p['power_w']) < 0 or self.rated_w <= 0:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            self.full_since = self.last_sample = None
            self.full = False
            # En contrôle à distance, une mesure momentanément absente ne doit
            # jamais relancer toute la production : on garde les dernières
            # consignes connues jusqu'au prochain échantillon complet.
            result.update(hms1000_limit_pct=None, dtu_limit_pct=None,
                          write_hold=True,
                          reason='Mesures absentes ou anciennes : consignes précédentes conservées, aucune commande envoyée.')
            return result
        # Le BMS Zendure peut afficher 98 à 100 % pendant la phase terminale,
        # alors que la batterie est déjà au repos. Pour l'autoconsommation,
        # 98 % est donc un plein ; l'état reste mémorisé jusqu'à 97 % afin
        # d'éviter les oscillations de l'affichage de niveau.
        if self.last_sample is not None and not 0 <= b['timestamp']-self.last_sample <= 45:
            self.full_since, self.full = None, False
        self.last_sample = b['timestamp']
        if b['soc_pct'] <= 97 or b['ac_charge_w'] > 50 or b['ac_discharge_w'] > 20:
            self.full_since, self.full = None, False
        elif not self.full:
            if b['soc_pct'] >= 98 and b['ac_charge_w'] <= 30 and b['ac_discharge_w'] <= 20:
                if self.full_since is None:
                    self.full_since = b['timestamp']
                if b['timestamp']-self.full_since >= 120:
                    self.full = True
            else:
                self.full_since = None
        result['battery_full_confirmed'] = self.full
        if self.dtu:
            d = s.get('dtu', {})
            try:
                if d['state'] != 'online' or not 0 <= now-d['timestamp'] <= 45:
                    raise ValueError()
                if not all(isinstance(d[k], (int,float)) and not isinstance(d[k],bool) and math.isfinite(d[k]) for k in ('power_w','limit_pct')):
                    raise ValueError()
                if d['power_w'] < 0 or not 2 <= d['limit_pct'] <= 100 or len(set(d['port_limits_pct'])) != 1:
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                # Une lecture Modbus manquée ne dit rien de l'état de charge
                # de la batterie. On bloque toute écriture tant que le DTU
                # est douteux, mais la confirmation batterie continue pour
                # reprendre la régulation dès que le DTU répond à nouveau.
                result.update(hms1000_limit_pct=None, dtu_limit_pct=None,
                              write_hold=True,
                              reason='Mesures DTU absentes ou incohérentes : consignes précédentes conservées, aucune commande envoyée.')
                return result
        if not self.full:
            result.update(hms1000_limit_pct=100, reason='Priorité à la maison et à la charge batterie.')
        elif abs(s['grid_w']-30) <= 15:
            result.update(hms1000_limit_pct=round(p['limit_pct']), reason='Batterie pleine : équilibre réseau atteint.')
        else:
            if s['grid_w'] < 15:
                desired = max(0, p['power_w']+s['grid_w']-30)
                target = min(p['limit_pct'], desired/self.rated_w*100)
            else:
                target = p['limit_pct']+(s['grid_w']-30)/self.rated_w*100
            result.update(hms1000_limit_pct=max(1, min(100, round(target))),
                          reason='Batterie pleine : régulation des deux panneaux du HMS.')
        if self.dtu and self.full:
            if abs(s['grid_w']-30) <= 15:
                a, z = p['limit_pct'], d['limit_pct']
            elif s['grid_w'] < 15:
                total = p['power_w'] + d['power_w']
                desired = max(0, total+s['grid_w']-30)
                ratio = desired/total if total > 0 else 0
                a = min(p['limit_pct'], p['power_w']*ratio/self.rated_w*100)
                z = min(d['limit_pct'], d['power_w']*ratio/self.dtu.rated_w*100)
            else:
                step = (s['grid_w']-30)/(self.rated_w+self.dtu.rated_w)*100
                a, z = p['limit_pct']+step, d['limit_pct']+step
            result.update(hms1000_limit_pct=max(1,min(100,round(a))), dtu_limit_pct=max(2,min(100,round(z))),
                          reason='Batterie pleine : régulation des six panneaux.')
        result['uncontrolled_surplus_w'] = round(max(0, -s['grid_w']-p['power_w']-(d['power_w'] if self.dtu else 0)), 1)
        if result['uncontrolled_surplus_w'] > 30:
            result['reason'] += ' Surplus des autres panneaux non pilotés.'
        return result

    def set_enabled(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("Activation attendue : oui ou non")
        with self._lock:
            self.enabled = enabled
            self.full_since = self.last_sample = None
            self.full = False
            # Une prise en main après l'arrêt du zéro-injection Hoymiles ne
            # doit jamais commencer par une hausse de production. On conserve
            # les limites observées pendant deux minutes de mesures stables.
            self.hold_until = time.time() + 120 if enabled else 0.0
            # La désactivation demande explicitement 100 % au HMS ; le proxy
            # doit donc rester autorisé à transmettre cette unique consigne.
            self.proxy.config["commands_enabled"] = True
            if not enabled:
                self.proxy.request_limit(100)
            self._state = dict(mode="automatic" if enabled else "paused", commands_enabled=enabled,
                               controlled_panels=6 if self.dtu else 2, hms1000_limit_pct=100, dtu_limit_pct=100 if self.dtu else None,
                               reason="Validation des mesures pendant 2 min : limites actuelles conservées." if enabled else "Gestion arrêtée : retour à 100 % demandé.")

    def start(self):
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _worker(self):
        while not self._stop.is_set():
            try:
                sample = self.sample()
                if self.dtu:
                    sample['dtu'] = self.dtu.snapshot()
            except Exception:
                sample = {}
            with self._lock:
                result = self.evaluate(sample, time.time())
                target = result.get('hms1000_limit_pct')
                hold = self.enabled and time.time() < self.hold_until
                if hold:
                    result['reason'] = 'Validation des mesures pendant 2 min : aucune commande envoyée.'
                    result['write_hold'] = True
                suppress_writes = hold or bool(result.get('write_hold'))
                if self.enabled and not suppress_writes and target is not None:
                    self.proxy.request_limit(target)
                if not self.enabled:
                    if self.proxy.config.get('commands_enabled'):
                        self.proxy.request_limit(100)
                    result.update(hms1000_limit_pct=100, reason='Gestion arrêtée : retour à 100 % demandé si la liaison répond.')
                if self.dtu:
                    result['dtu'] = sample.get('dtu', {})
                    # En mode arrêté, le DTU reste sous le contrôle natif du
                    # DDSU : observer sa limite ne doit jamais lui écrire 100
                    # % en boucle. Les commandes Modbus ne sont autorisées
                    # qu'après une activation explicite de la régulation.
                    if self.enabled and not suppress_writes and result.get('dtu_limit_pct') is not None:
                        try:
                            self.dtu.request_limit(result['dtu_limit_pct'], result['dtu'])
                        except Exception as exc:
                            result['dtu_command_error'] = type(exc).__name__
                            result['reason'] += ' Commande DTU non confirmée ; retour du HMS à 100 % demandé.'
                            self.proxy.request_limit(100)
                            self.full_since = self.last_sample = None
                            self.full = False
                self._state = result
            self._stop.wait(15)
