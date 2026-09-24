"""Read-only, shared web reports. No device connections and no invented samples."""
import csv
import math
import threading
import time
from bisect import bisect_right
from datetime import datetime, timedelta
from pathlib import Path

from battery_monitor import number, household
from autostart import status as autostart_status, set_enabled as set_autostart_enabled


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
                               battery_discharge_w=number(b.get('discharge_w'))))
        production, pv_seconds = integrate(points,'production_w',start,end)
        exported, grid_seconds = integrate(points,'export_w',start,end)
        billing = index_energy(dated_rows(self.base/'linky_index_log.csv'),start,end) if enabled('linky') else index_energy([],start,end)
        tariffs = cfg.get('tarifs_edf',{})
        hp_rate, hc_rate = number(tariffs.get('hp_eur_kwh')),number(tariffs.get('hc_eur_kwh'))
        energy_cost = None
        if billing['import_kwh'] is not None and hp_rate is not None and hc_rate is not None and hp_rate>0 and hc_rate>0:
            energy_cost = billing['hp_kwh']*hp_rate+billing['hc_kwh']*hc_rate
        # Calendar days, not DST-dependent 24-hour intervals.
        days = (end_dt.date()-start_dt.date()).days + (0 if end_dt.time()==datetime.min.time() else 1)
        daily_fee = number(tariffs.get('abonnement_journalier_eur'))
        subscription = None if daily_fee is None else max(0,days)*daily_fee
        totals = self.battery.totals(start,end)
        return dict(period=period, from_time=start_dt.isoformat(), to_time=end_dt.isoformat(),
                    updated_at=now.isoformat(timespec='seconds'), production_kwh=production,
                    production_complete=complete, export_kwh=exported, pv_seconds=pv_seconds,
                    grid_seconds=grid_seconds, billing=billing, energy_cost=energy_cost,
                    subscription=subscription, total_cost=None if energy_cost is None or subscription is None else energy_cost+subscription,
                    battery_charge_kwh=totals['charge_kwh'] if totals['battery_seconds'] else None,
                    battery_discharge_kwh=totals['discharge_kwh'] if totals['battery_seconds'] else None,
                    history=compress_history([p for p in points if start<=p['stamp']<=end]),
                    source='Index Linky enregistrés ; intervalles à cheval sur la période exclus. Les relevés EDF manuels restent accessibles dans les outils classiques.')

    def settings(self):
        result = {'dtu_host':str(self.config.get('dtu_host','')),
                  'production_complete':bool(self.config.get('production_complete')),
                  'tarifs_edf':{k:self.config.get('tarifs_edf',{}).get(k) for k in
                                ('hp_eur_kwh','hc_eur_kwh','abonnement_journalier_eur','plages_hc')}}
        for name in ('linky','shelly','battery','shelly2'):
            item=self.config.get(name,{})
            result[name]={k:item.get(k) for k in ('enabled','host','reverse')}
        result['autostart'] = autostart_status(self.base)
        return result

    def set_autostart(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError('Le choix Oui ou Non est nécessaire.')
        return set_autostart_enabled(enabled, self.base)
