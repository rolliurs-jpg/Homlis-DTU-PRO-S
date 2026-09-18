"""Mesures locales Zendure et seconde production. Aucune commande aux appareils."""
import csv
import json
import math
import threading
import time
from bisect import bisect_right
from datetime import datetime
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

    def open_window(self, parent):
        import tkinter as tk
        from tkinter import ttk, filedialog
        import shutil
        window = tk.Toplevel(parent)
        window.title('Batterie et seconde production — mesures réelles')
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill='both', expand=True)
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
            month = self.totals(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp(), now.timestamp())
            label.config(text=(
                'ZENDURE SOLARFLOW 2400 AC\n'
                f"Niveau : {fmt(row.get('soc_pct'), '%')}   ·   Modules : {fmt(row.get('pack_count'), '')}\n"
                f"Charge batterie : {fmt(row.get('charge_w'))}\nDécharge batterie : {fmt(row.get('discharge_w'))}\n"
                f"Entrée 230 V du SolarFlow : {fmt(row.get('ac_charge_w'))}\n"
                f"Restitution vers la maison : {fmt(row.get('ac_discharge_w'))}\n"
                'L’entrée 230 V peut venir du solaire : ce n’est pas une mesure d’achat EDF.\n\n'
                f"PRODUCTION SECONDE LIGNE : {fmt(row.get('pv2_w'))}\n\n"
                f"AUJOURD’HUI — charge {totals['charge_kwh']:.3f} kWh · décharge {totals['discharge_kwh']:.3f} kWh\n"
                f"CE MOIS — charge {month['charge_kwh']:.3f} kWh · décharge {month['discharge_kwh']:.3f} kWh\n"
                f"Seconde production mesurée ce mois : {month['pv2_kwh']:.3f} kWh\n"
                f"Durée batterie mesurée ce mois : {month['battery_seconds']/3600:.2f} h\n"
                'Cumuls depuis le début des relevés ; les coupures ne sont pas extrapolées.\n\n'
                + (error or ('Lecture locale active' if row else 'Activez les appareils dans Équipements puis relancez.'))))
            window.after(2000, refresh)
        def export():
            path = filedialog.asksaveasfilename(parent=window, defaultextension='.csv', initialfile='batterie_production2.csv')
            if path and self.path.exists() and Path(path).resolve() != self.path.resolve():
                shutil.copyfile(self.path, path)
        ttk.Button(frame, text='Exporter les mesures CSV', command=export).pack(anchor='w', pady=12)
        refresh()
        return window
