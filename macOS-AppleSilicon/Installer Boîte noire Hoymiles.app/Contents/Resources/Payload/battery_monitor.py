"""Mesures locales Zendure et seconde production. Aucune commande aux appareils."""
import csv
import json
import math
import threading
import time
from bisect import bisect_right
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import build_opener, ProxyHandler


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def get_json(cfg, path):
    host = str(cfg.get('host', '')).strip()
    if not host or any(c in host for c in '/?#@'):
        raise ValueError('Adresse IP ou nom réseau manquant/invalide')
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"http://{host}:{int(cfg.get('port', 80))}{path}",
                     timeout=float(cfg.get('timeout_s', 2))) as response:
        return json.loads(response.read(262144))


def parse_zendure(data, now=None):
    if str(data.get('product', '')).lower() != 'solarflow2400ac':
        raise ValueError('Cet appareil ne se présente pas comme SolarFlow 2400 AC')
    p = data.get('properties', {})
    if p.get('dataReady') != 1:
        raise ValueError('Batterie : mesures pas encore prêtes')
    stamp = number(p.get('ts', data.get('timestamp')))
    now = time.time() if now is None else now
    if stamp is None or abs(now - stamp) > 180:
        raise ValueError('Batterie : horodatage absent ou ancien')
    def required(key, upper):
        value = number(p.get(key))
        if value is None or not 0 <= value <= upper:
            raise ValueError('Mesure batterie absente/invalide : ' + key)
        return value
    return dict(soc_pct=required('electricLevel', 100),
                charge_w=required('outputPackPower', 10000),
                discharge_w=required('packInputPower', 10000),
                ac_charge_w=required('gridInputPower', 10000),
                ac_discharge_w=required('outputHomePower', 10000),
                pack_count=number(p.get('packNum')),
                charge_limit_w=number(p.get('chargeMaxLimit')))


def household(pv1, pv2, grid, battery, total_pv_known):
    """Bilan côté AC ; pas de zéro inventé en cas de production partielle."""
    if not total_pv_known or any(x is None for x in (pv1, pv2, grid)):
        return None
    if battery is None:
        return None
    value = pv1 + pv2 + grid + battery['ac_discharge_w'] - battery['ac_charge_w']
    return max(0.0, value) if value >= -30 else None


FIELDS = ['timestamp', 'soc_pct', 'charge_w', 'discharge_w', 'ac_charge_w',
          'ac_discharge_w', 'pack_count', 'charge_limit_w', 'pv2_w']


def energy_totals(rows, start, end):
    totals = dict(charge_kwh=0.0, discharge_kwh=0.0, ac_charge_kwh=0.0,
                  ac_discharge_kwh=0.0, pv2_kwh=0.0, battery_seconds=0.0, pv2_seconds=0.0)
    for a, b in zip(rows, rows[1:]):
        left, right = a['timestamp'], b['timestamp']
        if not 0 < right - left <= 45:
            continue
        dt = max(0, min(right, end) - max(left, start))
        if not dt:
            continue
        if all(a.get(k) is not None and b.get(k) is not None for k in FIELDS[1:6]):
            totals['battery_seconds'] += dt
            for key in ('charge', 'discharge', 'ac_charge', 'ac_discharge'):
                totals[key + '_kwh'] += (a[key + '_w'] + b[key + '_w']) / 2 * dt / 3600000
        if a.get('pv2_w') is not None and b.get('pv2_w') is not None:
            totals['pv2_seconds'] += dt
            totals['pv2_kwh'] += (a['pv2_w'] + b['pv2_w']) / 2 * dt / 3600000
    return totals





def battery_visual(row):
    soc = number(row.get('soc_pct'))
    charge, discharge = number(row.get('charge_w')), number(row.get('discharge_w'))
    percent = '—' if soc is None else f'{soc:.0f} %'
    if soc is None or charge is None or discharge is None:
        return percent, '#64748b', 'Mesure indisponible', 0 if soc is None else soc
    net = charge-discharge
    if net > 20:
        return percent, '#16a34a', f'En charge · {net:.0f} W', soc
    if net < -20:
        return percent, '#dc2626', f'En décharge · {-net:.0f} W', soc
    return percent, '#64748b', 'Pleine · au repos' if soc >= 100 else 'Au repos', soc

def battery_cycle(rows, full_at, until):
    """First sustained discharge, then sustained recharge, including midnight.

    Discharge requires power above 20 W both from the battery pack and on the
    AC output to the home. It is confirmed after 120 seconds when SOC falls,
    or after 10 continuous minutes when the rounded SOC remains unchanged.
    This rejects short scheduled activity while still detecting a gentle real
    discharge that can remain displayed at 99% for several minutes.
    Effective duration counts only measured discharging intervals (<=45 s).
    """
    result = dict(discharge_at=None, recharge_at=None, discharge_seconds=None,
                  cycle_incomplete=False, cycle_pending=True)
    if full_at is None:
        return result
    samples = [r for r in rows if full_at <= r['timestamp'] <= until]
    candidate = None
    candidate_soc = None
    previous = None
    for row in samples:
        t = row['timestamp']
        charge, discharge = number(row.get('charge_w')), number(row.get('discharge_w'))
        ac_discharge = number(row.get('ac_discharge_w'))
        seeking_discharge = result['discharge_at'] is None
        valid = charge is not None and discharge is not None
        if seeking_discharge:
            valid = valid and ac_discharge is not None
        if previous is not None and t-previous > 45:
            candidate = None
            candidate_soc = None
            result['cycle_incomplete'] = True
        if not valid:
            result['cycle_incomplete'] = True
            candidate = None
            candidate_soc = None
        else:
            net = discharge-charge
            matches = (net > 20 and ac_discharge > 20) if seeking_discharge else net < -20
            if matches:
                if candidate is None:
                    candidate = t
                    candidate_soc = number(row.get('soc_pct'))
                soc = number(row.get('soc_pct'))
                soc_fell = (candidate_soc is not None and soc is not None and
                            soc <= candidate_soc - 1)
                confirmed = (((t-candidate >= 120 and soc_fell) or
                              (t-candidate >= 600)) if seeking_discharge
                             else t-candidate >= 120)
                if confirmed:
                    if seeking_discharge:
                        result['discharge_at'] = candidate
                        candidate = None
                        candidate_soc = None
                    else:
                        result['recharge_at'] = candidate
                        result['cycle_pending'] = False
                        break
            else:
                candidate = None
                candidate_soc = None
        previous = t
    if previous is None or (result['recharge_at'] is None and until-previous > 45):
        result['cycle_incomplete'] = True
    if result['discharge_at'] is not None:
        start, stop = result['discharge_at'], result['recharge_at'] or until
        duration = 0.0
        for a,b in zip(samples, samples[1:]):
            left,right = a['timestamp'],b['timestamp']
            if not 0 < right-left <= 45:
                continue
            powers = [number(r.get(k)) for r in (a,b)
                      for k in ('charge_w','discharge_w','ac_discharge_w')]
            if any(v is None for v in powers):
                continue
            if (powers[1]-powers[0] > 20 and powers[2] > 20 and
                    powers[4]-powers[3] > 20 and powers[5] > 20):
                duration += max(0, min(right,stop)-max(left,start))
        result['discharge_seconds'] = duration
    return result


def cycle_values(r):
    """Shared desktop/mobile/CSV wording, times in the computer's local zone."""
    def clock(value):
        if value is None:
            return 'Non observée'
        dt = datetime.fromtimestamp(value)
        return dt.strftime('%H:%M') if dt.date().isoformat() == r['date'] else dt.strftime('%d/%m à %H:%M')
    seconds = r.get('discharge_seconds')
    duration = '—' if seconds is None else f"{int(seconds)//3600} h {int(seconds)%3600//60:02d} min"
    if seconds is not None and r.get('cycle_pending'):
        duration += ' (provisoire)'
    alerts = []
    if r.get('already_full'):
        alerts.append('Déjà pleine au relevé / après une interruption')
    if r.get('period_s',0)-r.get('coverage_s',0) > 1:
        alerts.append('Relevés réseau incomplets')
    if r.get('cycle_incomplete'):
        alerts.append('Relevés batterie incomplets')
    energy = 'Indisponible' if r['export_kwh'] is None else f"{r['export_kwh']:.3f} kWh"
    if r['end_at'] is None and r['export_kwh'] is not None:
        energy += ' (provisoire)'
    return (r['date'], clock(r['full_at']), energy,
            clock(r['end_at']) if r['end_at'] is not None else 'Non confirmée',
            clock(r.get('discharge_at')), duration, clock(r.get('recharge_at')),
            ' · '.join(alerts) or '—')


CYCLE_HEADINGS = ('Jour du plein', 'Pleine à', 'Surplus après plein', 'Fin solaire estimée',
                  'Décharge dès', 'Temps en décharge', 'Recharge dès', 'Remarques')

def full_charge_days(battery_rows, grid_rows, pv_rows, now):
    """Daily first observed 100%, then measured export. No gap extrapolation.

    pv_rows contains total PV only when all production lines are known.
    A production end is estimated after 30 continuous minutes <= 10 W,
    after noon and after observed production. Any later activity cancels it.
    """
    battery_rows = sorted({r['timestamp']: r for r in battery_rows}.values(), key=lambda r: r['timestamp'])
    days = {}
    for row in sorted(battery_rows, key=lambda r: r['timestamp']):
        t = row['timestamp']
        if t > now:
            continue
        day = datetime.fromtimestamp(t).date()
        entry = days.setdefault(day, dict(full_at=None, already_full=False,
                                         previous=None))
        soc = number(row.get('soc_pct'))
        if soc is not None and soc >= 100 and entry['full_at'] is None:
            entry['full_at'] = t
            prev = entry['previous']
            entry['already_full'] = not (prev and 0 < t-prev[0] <= 45 and prev[1] < 100)
        entry['previous'] = (t, soc) if soc is not None else None
    grid_rows = sorted({r['timestamp']: r for r in grid_rows}.values(), key=lambda r: r['timestamp'])
    pv_rows = sorted({r['timestamp']: r for r in pv_rows}.values(), key=lambda r: r['timestamp'])
    results = []
    for day, entry in sorted(days.items(), reverse=True):
        start = datetime.combine(day, datetime.min.time()).timestamp()
        stop = min(now, datetime.combine(day + timedelta(days=1), datetime.min.time()).timestamp())
        full = entry['full_at']
        result = dict(date=day.isoformat(), full_at=full, already_full=entry['already_full'],
                      end_at=None, export_kwh=None, coverage_s=0.0, period_s=0.0,
                      ongoing=day == datetime.fromtimestamp(now).date())
        if full is not None:
            active = False
            low_start = None
            prev_t = None
            for row in pv_rows:
                t, power = row['timestamp'], number(row.get('pv_w'))
                if not full <= t <= stop:
                    continue
                if power is None or prev_t is None or t-prev_t > 180:
                    low_start = None
                    result['end_at'] = None
                if power is not None and power > 10:
                    active = True
                    low_start = None
                    result['end_at'] = None
                elif power is not None and active and datetime.fromtimestamp(t).hour >= 12:
                    if low_start is None:
                        low_start = t
                    if t-low_start >= 1800:
                        result['end_at'] = low_start
                prev_t = t
            # Do not confirm an end across missing trailing measurements.
            if prev_t is None or stop-prev_t > 180:
                result['end_at'] = None
            end = result['end_at'] if result['end_at'] is not None else stop
            result['period_s'] = max(0, end-full)
            energy = 0.0
            for a, b in zip(grid_rows, grid_rows[1:]):
                left, right = a['timestamp'], b['timestamp']
                dt = right-left
                pa, pb = number(a.get('injection_w')), number(b.get('injection_w'))
                # A new logger session has intervalle_s=0: never bridge it.
                if not 0 < dt <= 180 or pa is None or pb is None or b.get('intervalle_s', dt) == 0:
                    continue
                lo, hi = max(left, full), min(right, end)
                if hi <= lo:
                    continue
                pa, pb = max(0, pa), max(0, pb)
                p0 = pa + (pb-pa)*(lo-left)/dt
                p1 = pa + (pb-pa)*(hi-left)/dt
                energy += (p0+p1)/2*(hi-lo)/3600000
                result['coverage_s'] += hi-lo
            if result['coverage_s']:
                result['export_kwh'] = energy
        # Attach the following night to the day of the full charge, not midnight.
        cycle_end = min(now, datetime.combine(day + timedelta(days=2), datetime.min.time()).timestamp())
        # Même si le Mac a démarré après le passage à 100 %, une décharge
        # réellement observée aujourd'hui reste une information valable.
        cycle_start = full if full is not None else start
        result.update(battery_cycle(battery_rows, cycle_start, cycle_end))
        results.append(result)

    # A discharge beginning on the day of a full charge belongs to that same
    # cycle until its first sustained recharge, even when midnight passes.
    # Without this arbitration the new calendar day also detected the still
    # running discharge from 00:00 and the dashboard displayed a duplicate
    # cycle whose duration had apparently been reset.
    today = datetime.fromtimestamp(now).date()
    owners = [r for r in results
              if r.get('full_at') is not None
              and r.get('discharge_at') is not None
              and r.get('recharge_at') is None
              and datetime.fromisoformat(r['date']).date() < today
              and today <= datetime.fromisoformat(r['date']).date() + timedelta(days=1)]
    if owners:
        owner = max(owners, key=lambda r: r['date'])
        for result in results:
            result['ongoing'] = result is owner
            if (result is not owner and result.get('full_at') is None
                    and result['date'] == today.isoformat()):
                result.update(discharge_at=None, recharge_at=None,
                              discharge_seconds=None, cycle_pending=True)

    for result in results:
        result['display'] = list(cycle_values(result))
    return results


class BatteryMonitor:
    def __init__(self, base, config):
        self.path = Path(base) / 'batterie_production2.csv'
        self.config = config
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.rows, self.stamps = [], []
        self.current = {}
        self.error = 'En attente de la première mesure'
        self.thread = None
        if self.path.exists():
            with self.path.open(encoding='utf-8', newline='') as handle:
                for row in csv.DictReader(handle):
                    parsed = {k: number(row.get(k)) for k in FIELDS}
                    if parsed['timestamp'] is not None:
                        self.rows.append(parsed)
            self.rows.sort(key=lambda row: row['timestamp'])
            self.stamps = [row['timestamp'] for row in self.rows]

    def start(self):
        if any(self.config.get(k, {}).get('enabled') for k in ('battery', 'shelly2')):
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()

    def run(self):
        while not self.stop_event.is_set():
            row = {k: None for k in FIELDS}
            errors = []
            if self.config.get('battery', {}).get('enabled'):
                try:
                    row.update(parse_zendure(get_json(self.config['battery'], '/properties/report')))
                except Exception as exc:
                    errors.append('Zendure : ' + str(exc))
            if self.config.get('shelly2', {}).get('enabled'):
                try:
                    cfg = self.config['shelly2']
                    channel = int(cfg.get('channel', 0))
                    value = number(get_json(cfg, f'/rpc/EM1.GetStatus?id={channel}').get('act_power'))
                    if value is None:
                        raise ValueError('Puissance absente')
                    value *= -1 if cfg.get('reverse', False) else 1
                    if value < -30:
                        raise ValueError('Production négative : vérifier le sens de la pince')
                    row['pv2_w'] = max(0, value)
                except Exception as exc:
                    errors.append('Shelly 2 : ' + str(exc))
            row['timestamp'] = time.time()
            try:
                new = not self.path.exists() or self.path.stat().st_size == 0
                with self.path.open('a', newline='', encoding='utf-8') as handle:
                    writer = csv.DictWriter(handle, fieldnames=FIELDS)
                    if new:
                        writer.writeheader()
                    writer.writerow(row)
            except OSError as exc:
                errors.append('Historique non enregistré : ' + str(exc))
            with self.lock:
                self.current = row
                self.error = ' / '.join(errors)
                self.rows.append(row)
                self.stamps.append(row['timestamp'])
            self.stop_event.wait(15)

    def snapshot(self):
        with self.lock:
            row, error = dict(self.current), self.error
        if row and time.time() - row['timestamp'] > 45:
            return {}, 'Mesures anciennes — connexion à vérifier'
        return row, error

    def at(self, timestamp):
        with self.lock:
            index = bisect_right(self.stamps, timestamp) - 1
            if index >= 0 and 0 <= timestamp - self.stamps[index] <= 45:
                return dict(self.rows[index])
        return {}

    def totals(self, start, end):
        with self.lock:
            rows = list(self.rows)
        return energy_totals(rows, start, end)

    def full_charge_report(self):
        with self.lock:
            rows = list(self.rows)
        def read_log(name):
            path = self.path.parent / name
            if not path.exists():
                return []
            with path.open(encoding='utf-8-sig', newline='') as handle:
                return list(csv.DictReader(handle))
        def stamp(row):
            try:
                return datetime.fromisoformat(row.get('date_heure', '')).timestamp()
            except (ValueError, TypeError):
                return None
        grid = []
        for row in read_log('shelly_injection_log.csv'):
            t = stamp(row)
            if t is not None:
                grid.append(dict(timestamp=t, injection_w=number(row.get('injection_w')),
                                 intervalle_s=number(row.get('intervalle_s'))))
        pv = []
        if self.config.get('production_complete', False):
            stamps = [r['timestamp'] for r in rows]
            for row in read_log('hoymiles_log.csv'):
                t = stamp(row)
                if t is None:
                    continue
                power = number(row.get('shelly_a_w'))
                if self.config.get('shelly2', {}).get('enabled'):
                    index = bisect_right(stamps, t)-1
                    second = rows[index].get('pv2_w') if index >= 0 and t-stamps[index] <= 45 else None
                    power = power+second if power is not None and second is not None else None
                pv.append(dict(timestamp=t, pv_w=power))
        return full_charge_days(rows, grid, pv, time.time())

    def open_full_charge_window(self, parent):
        import tkinter as tk
        from tkinter import ttk, filedialog
        window = tk.Toplevel(parent)
        window.title('Cycle batterie — plein, surplus, décharge et recharge')
        window.geometry('1120x480')
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Chaque ligne relie le plein à la décharge puis à la reprise de charge, même le lendemain.\n'
                  'Temps en décharge : uniquement les périodes mesurées de décharge, sans les pauses.\n'
                  'Début de décharge / recharge : puissance nette supérieure à 20 W pendant 2 minutes.\n'
                  'Surplus provisoire si la fin solaire est inconnue : relevés disponibles jusqu’à minuit ; peut inclure un apport batterie.',
                  wraplength=1060).pack(anchor='w', pady=(0, 10))
        columns = ('date', 'full', 'energy', 'end', 'discharge', 'duration', 'recharge', 'notes')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
        for key, title, width in zip(columns, CYCLE_HEADINGS,
                (95, 80, 160, 145, 130, 170, 130, 240)):
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=75, anchor='w', stretch=False)
        tree.pack(fill='both', expand=True)
        scroll = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        scroll.pack(fill='x')
        tree.configure(xscrollcommand=scroll.set)
        status = ttk.Label(frame, text='', wraplength=1060)
        status.pack(anchor='w', pady=8)
        report = []
        def values(r):
            return cycle_values(r)
        def refresh():
            nonlocal report
            try:
                report = self.full_charge_report()
                tree.delete(*tree.get_children())
                for r in report:
                    tree.insert('', 'end', values=values(r))
                status.config(text='Aucun relevé batterie disponible.' if not report else
                    'Les trous de mesure sont exclus, jamais remplacés par zéro. Actualisation toutes les 30 secondes.')
            except (OSError, csv.Error) as exc:
                status.config(text='Historique momentanément indisponible : ' + str(exc))
            timer[0] = window.after(30000, refresh)
        def export():
            target = filedialog.asksaveasfilename(parent=window, defaultextension='.csv', initialfile='surplus_apres_batterie_pleine.csv')
            if target:
                with open(target, 'w', encoding='utf-8-sig', newline='') as handle:
                    writer = csv.writer(handle, delimiter=';')
                    writer.writerow([tree.heading(c)['text'] for c in columns])
                    writer.writerows(values(r) for r in report)
        controls = ttk.Frame(frame)
        controls.pack(fill='x')
        ttk.Button(controls, text='Exporter ce bilan CSV', command=export).pack(side='left')
        timer = [None]
        def close():
            if timer[0]:
                window.after_cancel(timer[0])
            window.destroy()
        ttk.Button(controls, text='Fermer', command=close).pack(side='right')
        window.protocol('WM_DELETE_WINDOW', close)
        refresh()
        return window

    def open_window(self, parent):
        import tkinter as tk
        from tkinter import ttk, filedialog
        import shutil
        window = tk.Toplevel(parent)
        window.title('Batterie et seconde production — mesures réelles')
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='ZENDURE SOLARFLOW 2400 AC', font=('Arial', 12, 'bold')).pack(anchor='center')
        drawing = tk.Canvas(frame, width=340, height=160, bg='#f8fafc', highlightthickness=0)
        drawing.pack(fill='x', pady=12)
        def draw_battery(row):
            percent, color, state, soc = battery_visual(row)
            drawing.delete('all')
            drawing.create_rectangle(46, 24, 294, 114, outline=color, width=4)
            drawing.create_rectangle(296, 48, 308, 90, fill=color, outline=color)
            drawing.create_rectangle(52, 30, 288, 108, fill='#e2e8f0', outline='')
            if soc > 0:
                drawing.create_rectangle(52, 30, 52+236*min(100,max(0,soc))/100, 108, fill=color, outline='')
            drawing.create_rectangle(115, 46, 225, 94, fill='#f8fafc', outline='')
            drawing.create_text(170, 70, text=percent, fill='#0f172a', font=('Arial', 26, 'bold'))
            drawing.create_text(170, 139, text=state, fill=color, font=('Arial', 13, 'bold'))
        label = ttk.Label(frame, text='', justify='left', wraplength=650, font=('Arial', 11))
        label.pack(anchor='w')
        def fmt(v, unit='W'):
            return 'indisponible' if v is None else f'{v:.0f} {unit}'
        def refresh():
            if not window.winfo_exists():
                return
            row, error = self.snapshot()
            now = datetime.now()
            totals = self.totals(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp(), now.timestamp())
            draw_battery(row)
            label.config(text=(
                f"Aujourd’hui : {totals['charge_kwh']:.2f} kWh chargés · {totals['discharge_kwh']:.2f} kWh déchargés\n"
                f"Nouveaux panneaux : {fmt(row.get('pv2_w'))}\n"
                + (error or ('Lecture locale active' if row else 'Activez la batterie dans Équipements.'))))
            window.after(2000, refresh)
        def export():
            path = filedialog.asksaveasfilename(parent=window, defaultextension='.csv', initialfile='batterie_production2.csv')
            if path and self.path.exists() and Path(path).resolve() != self.path.resolve():
                shutil.copyfile(self.path, path)
        ttk.Button(frame, text='Cycle batterie : plein, surplus et décharge',
                   command=lambda: self.open_full_charge_window(window)).pack(anchor='w', pady=(12, 0))
        ttk.Button(frame, text='Exporter les mesures CSV', command=export).pack(anchor='w', pady=12)
        refresh()
        return window
