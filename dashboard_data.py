"""Read-only, shared web reports. No device connections and no invented samples."""
import csv
import os
import socket
import subprocess
import sys
import math
import threading
import time
from bisect import bisect_right
from datetime import datetime, timedelta
from pathlib import Path

from battery_monitor import number, household
from autostart import status as autostart_status, set_enabled as set_autostart_enabled


def icmp_reachable(host):
    """Probe an access point which intentionally exposes no TCP service."""
    if not host:
        return False
    if os.name == "nt":
        command = ["ping", "-n", "1", "-w", "1000", host]
    elif sys.platform == "darwin":
        command = ["ping", "-c", "1", "-W", "1000", host]
    else:
        command = ["ping", "-c", "1", "-W", "1", host]
    try:
        return subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=2, check=False,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def period_bounds(period, now):
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'today':
        return midnight, now
    if period == 'yesterday':
        return midnight-timedelta(days=1), midnight
    if period == 'week':
        return midnight-timedelta(days=6), now
    if period == 'month':
        return midnight.replace(day=1), now
    if period == 'year':
        return midnight.replace(month=1, day=1), now
    raise ValueError('Période inconnue')


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def dated_rows(path):
    result = {}
    for row in read_csv(path):
        try:
            stamp = datetime.fromisoformat(row['date_heure']).timestamp()
            result[stamp] = dict(row, stamp=stamp)
        except (KeyError, TypeError, ValueError):
            continue
    return [result[t] for t in sorted(result)]


def integrate(points, key, start, end):
    energy, seconds = 0.0, 0.0
    for a, b in zip(points, points[1:]):
        left, right = a['stamp'], b['stamp']
        dt = right-left
        pa, pb = number(a.get(key)), number(b.get(key))
        if not 0 < dt <= 180 or pa is None or pb is None:
            continue
        lo, hi = max(start, left), min(end, right)
        if hi <= lo:
            continue
        p0 = pa+(pb-pa)*(lo-left)/dt
        p1 = pa+(pb-pa)*(hi-left)/dt
        energy += (max(0, p0)+max(0, p1))/2*(hi-lo)/3600000
        seconds += hi-lo
    return (energy if seconds else None), seconds


def hc_windows(value):
    """Lit les plages HC saisies sous la forme 22:00-06:00,13:00-15:00."""
    windows = []
    for item in str(value or '').split(','):
        try:
            left, right = (part.strip() for part in item.split('-', 1))
            start_h, start_m = (int(part) for part in left.split(':', 1))
            end_h, end_m = (int(part) for part in right.split(':', 1))
            start_minute, end_minute = start_h * 60 + start_m, end_h * 60 + end_m
            if 0 <= start_minute < 1440 and 0 <= end_minute < 1440:
                windows.append((start_minute, end_minute))
        except (TypeError, ValueError):
            continue
    return windows


def is_hc(when, windows):
    minute = when.hour * 60 + when.minute
    return any(
        start <= minute < end if start < end else minute >= start or minute < end
        for start, end in windows
    )


def detailed_energy(points, start, end, hp_rate, hc_rate, hc_ranges):
    """Estime les kWh qui couvrent directement la maison, sans double compte."""
    result = dict(solar_direct_hp_kwh=0.0, solar_direct_hc_kwh=0.0,
                  battery_hp_kwh=0.0, battery_hc_kwh=0.0,
                  solar_seconds=0.0, battery_seconds=0.0,
                  solar_first_stamp=None, solar_last_stamp=None)
    windows = hc_windows(hc_ranges)
    for a, b in zip(points, points[1:]):
        left, right = a['stamp'], b['stamp']
        if not 0 < right - left <= 180:
            continue
        lo, hi = max(start, left), min(end, right)
        if hi <= lo:
            continue
        values = {}
        for key in ('production_w', 'consumption_w', 'battery_ac_discharge_w'):
            first, second = number(a.get(key)), number(b.get(key))
            values[key] = None if first is None or second is None else max(0.0, (first + second) / 2)
        if values['production_w'] is None or values['consumption_w'] is None:
            continue
        direct_solar = min(values['production_w'], values['consumption_w'])
        duration = hi - lo
        energy = direct_solar * duration / 3_600_000
        target = 'hc' if is_hc(datetime.fromtimestamp((lo + hi) / 2), windows) else 'hp'
        result[f'solar_direct_{target}_kwh'] += energy
        result['solar_seconds'] += duration
        result['solar_first_stamp'] = lo if result['solar_first_stamp'] is None else min(result['solar_first_stamp'], lo)
        result['solar_last_stamp'] = hi if result['solar_last_stamp'] is None else max(result['solar_last_stamp'], hi)
        if values['battery_ac_discharge_w'] is not None:
            battery = min(values['battery_ac_discharge_w'], max(0.0, values['consumption_w'] - direct_solar))
            result[f'battery_{target}_kwh'] += battery * duration / 3_600_000
            result['battery_seconds'] += duration
    solar_kwh = result['solar_direct_hp_kwh'] + result['solar_direct_hc_kwh']
    battery_kwh = result['battery_hp_kwh'] + result['battery_hc_kwh']
    result['solar_direct_kwh'] = solar_kwh if result['solar_seconds'] else None
    result['battery_covered_kwh'] = battery_kwh if result['battery_seconds'] else None
    if hp_rate is not None and hc_rate is not None and hp_rate > 0 and hc_rate > 0:
        result['solar_gain_hp_eur'] = result['solar_direct_hp_kwh'] * hp_rate
        result['solar_gain_hc_eur'] = result['solar_direct_hc_kwh'] * hc_rate
        result['solar_gain_eur'] = result['solar_gain_hp_eur'] + result['solar_gain_hc_eur']
        result['battery_gain_hp_eur'] = result['battery_hp_kwh'] * hp_rate
        result['battery_gain_hc_eur'] = result['battery_hc_kwh'] * hc_rate
        result['battery_gain_eur'] = result['battery_gain_hp_eur'] + result['battery_gain_hc_eur']
    else:
        result.update(solar_gain_hp_eur=None, solar_gain_hc_eur=None, solar_gain_eur=None,
                      battery_gain_hp_eur=None, battery_gain_hc_eur=None, battery_gain_eur=None)
    return result


def index_energy(rows, start, end):
    """Only intervals entirely within the requested period. Resets are excluded.

    A long interval between cumulative indexes is valid; it is not an
    interpolation of power. A boundary-straddling interval cannot be assigned
    to the day accurately and is excluded.
    """
    hc = hp = seconds = 0.0
    first = last = None
    for a,b in zip(rows, rows[1:]):
        if not start <= a['stamp'] < b['stamp'] <= end:
            continue
        vals = [number(r.get(k)) for r in (a,b) for k in ('hc_kwh','hp_kwh')]
        if any(v is None for v in vals):
            continue
        dc, dp = vals[2]-vals[0], vals[3]-vals[1]
        if dc < 0 or dp < 0:
            continue
        hc += dc
        hp += dp
        seconds += b['stamp']-a['stamp']
        first = a['stamp'] if first is None else first
        last = b['stamp']
    return dict(hc_kwh=hc if seconds else None, hp_kwh=hp if seconds else None,
                import_kwh=hc+hp if seconds else None, seconds=seconds,
                first=first, last=last, complete=bool(seconds and end-start-seconds <= 180))



def manual_edf_history(config, hp_rate, hc_rate, linky_rows, now):
    """Base EDF déclarée, prolongée uniquement par les index locaux postérieurs."""
    declared = config.get('historique_edf', {})
    base_hp, base_hc = number(declared.get('hp_kwh')), number(declared.get('hc_kwh'))
    start_date, as_of_date = str(declared.get('start_date') or ''), str(declared.get('as_of_date') or '')
    if base_hp is None or base_hc is None or base_hp < 0 or base_hc < 0:
        return None
    local_hp = local_hc = 0.0
    automatic_from = ''
    try:
        # Le relevé déclaré inclut toute sa journée ; la collecte locale reprend le lendemain.
        automatic_start = datetime.strptime(as_of_date, '%Y-%m-%d') + timedelta(days=1)
        automatic_from = automatic_start.date().isoformat()
        if now > automatic_start:
            local = index_energy(linky_rows, automatic_start.timestamp(), now.timestamp())
            local_hp = local['hp_kwh'] or 0.0
            local_hc = local['hc_kwh'] or 0.0
    except ValueError:
        automatic_from = ''
    hp_kwh, hc_kwh = base_hp + local_hp, base_hc + local_hc
    energy_cost = None
    if hp_rate is not None and hc_rate is not None and hp_rate > 0 and hc_rate > 0:
        energy_cost = hp_kwh * hp_rate + hc_kwh * hc_rate
    subscription = None
    try:
        first_day = datetime.strptime(start_date, '%Y-%m-%d').date()
        daily_fee = number(config.get('tarifs_edf', {}).get('abonnement_journalier_eur'))
        if daily_fee is not None and daily_fee >= 0 and now.date() >= first_day:
            subscription = ((now.date() - first_day).days + 1) * daily_fee
    except ValueError:
        pass
    total_cost = None if energy_cost is None or subscription is None else energy_cost + subscription
    return dict(
        start_date=start_date, as_of_date=as_of_date, automatic_from=automatic_from,
        base_hp_kwh=base_hp, base_hc_kwh=base_hc,
        local_hp_kwh=local_hp, local_hc_kwh=local_hc,
        hp_kwh=hp_kwh, hc_kwh=hc_kwh, import_kwh=hp_kwh + hc_kwh,
        energy_cost=energy_cost, subscription=subscription, total_cost=total_cost,
        source='Base EDF déclarée, prolongée par les index Denky/Linky du Raspberry.',
    )

def hoymiles_cloud_history(config):
    """Totaux mensuels exportés par S-Miles, affichés sans les mêler au Raspberry."""
    history = config.get('historique_hoymiles', {})
    months = history.get('months', []) if isinstance(history, dict) else []
    totals = dict(production_kwh=0.0, export_kwh=0.0, import_kwh=0.0,
                  consumption_kwh=0.0, months=[])
    for item in months:
        if not isinstance(item, dict):
            continue
        month = str(item.get('month') or '')
        values = {key: number(item.get(key)) for key in
                  ('production_kwh', 'export_kwh', 'import_kwh', 'consumption_kwh')}
        if not month or any(value is None or value < 0 for value in values.values()):
            continue
        totals['months'].append(dict(month=month, **values))
        for key, value in values.items():
            totals[key] += value
    if not totals['months']:
        return None
    totals['months'].sort(key=lambda item: item['month'])
    totals['from_month'] = totals['months'][0]['month']
    totals['to_month'] = totals['months'][-1]['month']
    totals['source'] = str(history.get('source') or 'Export S-Miles Cloud')
    return totals

def cumulative_grid_export(rows, config):
    """Integrate only the measured export since the first saved sample."""
    if not bool(config.get('shelly', {}).get('enabled')):
        return None
    points = []
    export_positive = bool(config.get('shelly', {}).get('grid_export_positive'))
    for row in rows:
        grid = number(row.get('shelly_b_w'))
        if grid is None:
            continue
        if export_positive:
            grid = -grid
        points.append({'stamp': row['stamp'], 'export_w': max(0.0, -grid)})
    if len(points) < 2:
        return None
    return integrate(points, 'export_w', points[0]['stamp'], points[-1]['stamp'])[0]


def compress_history(points, count=240):
    if len(points) <= count:
        return points
    indexes = {0, len(points)-1}
    step = math.ceil(len(points)/count)
    keys = ('production_w', 'export_w', 'import_w',
            'battery_charge_w', 'battery_discharge_w')
    for left in range(0, len(points), step):
        right = min(left+step, len(points))
        indexes.update((left,right-1))
        for key in keys:
            good = [i for i in range(left,right) if points[i].get(key) is not None]
            if good:
                indexes.add(min(good,key=lambda i:points[i][key]))
                indexes.add(max(good,key=lambda i:points[i][key]))
            missing = next((i for i in range(left,right) if points[i].get(key) is None),None)
            if missing is not None:
                indexes.add(missing)
    return [points[i] for i in sorted(indexes)]


class DashboardData:
    def __init__(self, base, config, battery):
        self.base, self.config, self.battery = Path(base), config, battery
        self.lock = threading.Lock()
        self.cache = {}
        self.esp_lock = threading.Lock()
        self.esp_cache = None
        self.esp_checked = 0

    def report(self, period='today'):
        with self.lock:
            cached = self.cache.get(period)
            if cached and time.monotonic()-cached[0] < 30:
                return cached[1]
            result = self._report(period, datetime.now())
            self.cache[period] = (time.monotonic(), result)
            return result

    def _report(self, period, now):
        start_dt, end_dt = period_bounds(period, now)
        start,end = start_dt.timestamp(),end_dt.timestamp()
        rows = dated_rows(self.base/'hoymiles_log.csv')
        with self.battery.lock:
            battery_rows = list(self.battery.rows)
        stamps = [r['timestamp'] for r in battery_rows]
        def battery_at(stamp):
            i = bisect_right(stamps,stamp)-1
            return battery_rows[i] if i>=0 and stamp-stamps[i]<=45 else {}
        cfg = self.config
        enabled = lambda k: bool(cfg.get(k,{}).get('enabled'))
        complete = bool(cfg.get('production_complete'))
        extended = enabled('battery') or enabled('shelly2')
        points = []
        for r in rows:
            if not start-180 <= r['stamp'] <= end+180:
                continue
            b = battery_at(r['stamp'])
            dtu_pv = number(r.get('production_ac_w'))
            shelly_pv = number(r.get('shelly_a_w')) if enabled('shelly') else None
            grid = number(r.get('shelly_b_w')) if enabled('shelly') else None
            if grid is not None and cfg.get('shelly',{}).get('grid_export_positive'):
                grid = -grid
            if extended:
                pv1 = shelly_pv
                pv2 = number(b.get('pv2_w')) if enabled('shelly2') else (0.0 if complete else None)
                # Une seconde installation non mesurée rend le total incomplet,
                # mais ne doit pas masquer l'énergie réellement vue par Shelly 1.
                pv = (pv1+pv2 if pv1 is not None and pv2 is not None else
                      pv1 if pv1 is not None else pv2)
                bflow = b if b.get('ac_charge_w') is not None and b.get('ac_discharge_w') is not None else None
                if not enabled('battery'):
                    bflow = dict(ac_charge_w=0,ac_discharge_w=0)
                consumption = household(pv1,pv2,grid,bflow,complete)
            else:
                pv1, pv2 = shelly_pv, None
                pv = dtu_pv if dtu_pv is not None else shelly_pv
                consumption = None if shelly_pv is None or grid is None else max(0.0, shelly_pv+grid)
            points.append(dict(stamp=r['stamp'], timestamp=datetime.fromtimestamp(r['stamp']).isoformat(),
                               production_w=pv, pv1_w=pv1, pv2_w=pv2,
                               consumption_w=consumption,
                               import_w=None if grid is None else max(0,grid),
                               export_w=None if grid is None else max(0,-grid),
                               battery_charge_w=number(b.get('charge_w')),
                               battery_discharge_w=number(b.get('discharge_w')),
                               battery_ac_discharge_w=number(b.get('ac_discharge_w'))))
        production, pv_seconds = integrate(points,'production_w',start,end)
        consumption, consumption_seconds = integrate(points,'consumption_w',start,end)
        exported, grid_seconds = integrate(points,'export_w',start,end)
        exported_total = cumulative_grid_export(rows, cfg)
        linky_rows = dated_rows(self.base/'linky_index_log.csv') if enabled('linky') else []
        billing = index_energy(linky_rows,start,end)
        tariffs = cfg.get('tarifs_edf',{})
        hp_rate, hc_rate = number(tariffs.get('hp_eur_kwh')),number(tariffs.get('hc_eur_kwh'))
        energy_cost = None
        if billing['import_kwh'] is not None and hp_rate is not None and hc_rate is not None and hp_rate>0 and hc_rate>0:
            energy_cost = billing['hp_kwh']*hp_rate+billing['hc_kwh']*hc_rate
        # Calendar days, not DST-dependent 24-hour intervals.
        days = (end_dt.date()-start_dt.date()).days + (0 if end_dt.time()==datetime.min.time() else 1)
        daily_fee = number(tariffs.get('abonnement_journalier_eur'))
        subscription = None if daily_fee is None else max(0,days)*daily_fee
        declared_edf = manual_edf_history(cfg, hp_rate, hc_rate, linky_rows, now)
        cloud_history = hoymiles_cloud_history(cfg)
        totals = self.battery.totals(start,end)
        detail = detailed_energy(points, start, end, hp_rate, hc_rate, tariffs.get('plages_hc'))
        return dict(period=period, from_time=start_dt.isoformat(), to_time=end_dt.isoformat(),
                    updated_at=now.isoformat(timespec='seconds'), production_kwh=production,
                    consumption_kwh=consumption, consumption_seconds=consumption_seconds,
                    production_complete=complete, export_kwh=exported, export_total_kwh=exported_total, pv_seconds=pv_seconds,
                    grid_seconds=grid_seconds, billing=billing, energy_cost=energy_cost,
                    subscription=subscription, total_cost=None if energy_cost is None or subscription is None else energy_cost+subscription,
                    tariffs=dict(hp_eur_kwh=hp_rate, hc_eur_kwh=hc_rate),
                    battery_charge_kwh=totals['charge_kwh'] if totals['battery_seconds'] else None,
                    battery_discharge_kwh=totals['discharge_kwh'] if totals['battery_seconds'] else None,
                    detailed_energy=detail,
                    declared_edf=declared_edf,
                    cloud_history=cloud_history,
                    history=compress_history([p for p in points if start<=p['stamp']<=end]),
                    source='Index Linky enregistrés ; intervalles à cheval sur la période exclus. Les relevés EDF manuels restent accessibles dans les outils classiques.')

    def esp_devices(self):
        with self.esp_lock:
            if self.esp_cache is not None and time.monotonic()-self.esp_checked < 15:
                return self.esp_cache
            proxy = self.config.get('hoymiles_proxy', {})
            router = self.config.get('esp_router', {})
            tp_link = self.config.get('tp_link', {})
            devices = [dict(id='proxy', name='ESP32 — proxy Bluetooth cabanon',
                            hosts=[str(proxy.get('host') or '')], port=int(proxy.get('port',6053)),
                            role='Près des panneaux cabanon · liaison Bluetooth', enabled=bool(proxy.get('enabled', False))),
                       dict(id='router', name='ESP32 — routeur Wi-Fi Solaire cabanon',
                            hosts=[str(router.get('ap_host') or ''), str(router.get('host') or '')], port=80,
                            role='Point d’accès Wi-Fi local', enabled=bool(router.get('enabled', False)),
                            probe='icmp')]
            for device in devices:
                reachable = []
                for host in device['hosts'] if device['enabled'] else []:
                    if device.get('probe') == 'icmp':
                        if icmp_reachable(host):
                            reachable.append(host)
                    else:
                        try:
                            with socket.create_connection((host, device['port']), timeout=1):
                                reachable.append(host)
                        except OSError:
                            pass
                device.update(reachable_hosts=reachable, connected=bool(reachable), checked_at=time.time())
            self.esp_cache, self.esp_checked = devices, time.monotonic()
            return devices

    @staticmethod
    def wireless_interfaces():
        """Return the two USB Wi-Fi links and their useful network references.

        An Alfa USB adapter is an interface of the Raspberry Pi, not a device
        with its own Livebox lease.  Showing that explicitly avoids sending
        the user looking for a non-existent Alfa IP in the Livebox.
        """
        states = {}
        try:
            completed = subprocess.run(
                ['nmcli', '-t', '-f', 'DEVICE,STATE', 'device', 'status'],
                capture_output=True, text=True, timeout=2, check=False,
                env={**os.environ, 'LC_ALL': 'C'},
            )
            if completed.returncode == 0:
                for line in (completed.stdout or '').splitlines():
                    interface, separator, state = line.partition(':')
                    if separator:
                        # NetworkManager may preserve the interface spelling
                        # supplied by a USB driver (for example ``WLAN2``).
                        # Linux interface matching is otherwise
                        # case-sensitive, while our two expected links are
                        # deliberately named in lower case below.
                        states[interface.lower()] = state
        except (OSError, subprocess.SubprocessError):
            pass

        links = (
            ('wlan1', 'Alfa AWUS036NHA — Wi-Fi DTU',
             'Liaison Wi-Fi directe vers le DTU',
             ('TP-Link / Livebox : 192.168.1.205', 'DTU local : 10.10.100.254')),
            ('wlan2', 'Alfa · antenne Wi-Fi solaire cabanon',
             'USB 3.0 obligatoire · liaison Wi-Fi vers le cabanon',
             ('Clé USB : aucune adresse Livebox propre',
              'Routeur ESP : 192.168.4.1', 'Proxy Hoymiles : 192.168.4.2')),
        )
        result = []
        for interface, name, role, references in links:
            connected = states.get(interface) == 'connected'
            if interface not in states:
                try:
                    connected = Path('/sys/class/net', interface, 'operstate').read_text().strip() == 'up'
                except OSError:
                    connected = False
            result.append(dict(interface=interface, name=name, role=role,
                               references=list(references), connected=connected))
        return result

    def settings(self):
        result = {'dtu_host':str(self.config.get('dtu_host','')),
                  'settings_password_enabled':bool(isinstance(self.config.get('settings_password'),dict) and self.config.get('settings_password',{}).get('salt') and self.config.get('settings_password',{}).get('digest')),
                  'production_complete':bool(self.config.get('production_complete')),
                  'tarifs_edf':{k:self.config.get('tarifs_edf',{}).get(k) for k in
                                ('hp_eur_kwh','hc_eur_kwh','abonnement_journalier_eur','plages_hc')}}
        for name in ('linky','shelly','battery','shelly2','tp_link','hoymiles_proxy','esp_router'):
            item=self.config.get(name,{})
            result[name]={k:item.get(k) for k in ('enabled','host','reverse')}
        result['esp_devices'] = self.esp_devices()
        result['wireless_interfaces'] = self.wireless_interfaces()
        try:
            result['autostart'] = autostart_status(self.base)
        except OSError:
            # systemd owns automatic startup on Raspberry Pi / Linux.  The
            # web dashboard must stay usable even though the desktop helper
            # only exists on Windows and macOS.
            result['autostart'] = {'enabled': False, 'computer': 'Raspberry Pi'}
        return result

    def set_autostart(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError('Le choix Oui ou Non est nécessaire.')
        return set_autostart_enabled(enabled, self.base)
