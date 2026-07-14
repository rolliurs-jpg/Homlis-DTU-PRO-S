import csv
import json
import shutil
import socket
import subprocess
import calendar
from tkinter import simpledialog, messagebox
from bisect import bisect_left
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.widgets import Button

VERSION = "6.6.3-public"
# Version publique : chaque installation renseigne ses propres équipements.
DEFAULT_DTU_HOST = ""
INTERVAL_MS = 60000
MAX_VISIBLE_POINTS = 300

BASE = Path.home() / "AppData" / "Local" / "BoiteNoireHoymiles"
BASE.mkdir(parents=True, exist_ok=True)
CSV_FILE = BASE / "hoymiles_log.csv"
CONFIG_FILE = BASE / "config_v5.json"
IMPORT_DIR = BASE / "Historiques_importes"
IMPORT_DIR.mkdir(parents=True, exist_ok=True)
BACKGROUND_IMAGE = Path(__file__).with_name("fond_solaire.png")

LEGACY_EMPTY_LINKY_CONFIG = {
    "enabled": False,
    "mode": "tcp",
    "host": "",
    "port": 0,
    "timeout_s": 2,
}

DEFAULT_CONFIG = {
    "dtu_host": DEFAULT_DTU_HOST,
    "linky": {
        "enabled": False,
        "mode": "dinky_http",
        "host": "",
        "port": 80,
        "timeout_s": 2,
        "path": "Status 8"
    },
    "tarifs_edf": {
        "hp_eur_kwh": 0.0,
        "hc_eur_kwh": 0.0,
        "abonnement_mensuel_eur": 0.0,
        "plages_hc": "",
        "ddsu_import_positif": True
    }
}

def load_config():
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG.copy()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("configuration racine invalide")
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(data)
        saved_linky = data.get("linky", {})
        if not isinstance(saved_linky, dict):
            saved_linky = {}
        # Migration sans toucher aux réglages TCP réellement configurés :
        # l'ancien bloc vide est remplacé par le Dinky installé sur ce site.
        if saved_linky == LEGACY_EMPTY_LINKY_CONFIG:
            saved_linky = DEFAULT_CONFIG["linky"]
        cfg["linky"] = {**DEFAULT_CONFIG["linky"], **saved_linky}
        saved_tariffs = data.get("tarifs_edf", {})
        if not isinstance(saved_tariffs, dict):
            saved_tariffs = {}
        cfg["tarifs_edf"] = {**DEFAULT_CONFIG["tarifs_edf"], **saved_tariffs}
        return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()

CONFIG = load_config()
HOST = str(CONFIG.get("dtu_host", DEFAULT_DTU_HOST)).strip()

def save_config():
    CONFIG_FILE.write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")

times, ac_power, grid_power, power_limit = [], [], [], []
linky_power = []
follow_now = True
last_success = None
dtu_failures = 0

def history_files():
    """V6.2 : un seul historique interne. Aucun fichier du Bureau n'est lu."""
    return [CSV_FILE] if CSV_FILE.exists() else []

def parse_history_row(row):
    t = datetime.strptime(row["date_heure"], "%Y-%m-%d %H:%M:%S")
    ac = float(row["production_ac_w"])
    grid = float(row["reseau_ddsu_w"])
    # Compatibilité avec tous les formats d'historique rencontrés.
    if row.get("consigne_w") not in ("", None):
        limit_w = float(row["consigne_w"])
    elif row.get("consigne_dtu_w") not in ("", None):
        limit_w = float(row["consigne_dtu_w"])
    elif row.get("consigne_brute") not in ("", None):
        limit_w = float(row["consigne_brute"]) / 10
    else:
        limit_w = 0.0
    lky = row.get("linky_w", "")
    lky_value = float(lky) if lky not in ("", None) else float("nan")
    return t, ac, grid, limit_w, lky_value

def load_history():
    """Fusionne tous les CSV, supprime les doublons et trie par date."""
    merged = {}
    loaded_files = []
    for path in history_files():
        try:
            count = 0
            with path.open("r", newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    try:
                        t, ac, grid, limit_w, lky = parse_history_row(row)
                        # Une seule mesure par seconde. Le fichier principal V5 est prioritaire.
                        if t not in merged or path == CSV_FILE:
                            merged[t] = (ac, grid, limit_w, lky)
                        count += 1
                    except Exception:
                        pass
            if count:
                loaded_files.append((path, count))
        except Exception:
            pass

    for t in sorted(merged):
        ac, grid, limit_w, lky = merged[t]
        times.append(t)
        ac_power.append(ac)
        grid_power.append(grid)
        power_limit.append(limit_w)
        linky_power.append(lky)

    return loaded_files

LOADED_HISTORY_FILES = load_history()

if not CSV_FILE.exists():
    with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            ["date_heure", "production_ac_w", "reseau_ddsu_w", "consigne_w", "linky_w"]
        )

fig, ax = plt.subplots(figsize=(13.5, 7.5))
fig.patch.set_facecolor("#f8fafc")
try:
    background_ax = fig.add_axes([0, 0, 1, 1], zorder=-10)
    background_ax.imshow(plt.imread(BACKGROUND_IMAGE), aspect="auto", alpha=0.32)
    background_ax.set_axis_off()
except Exception:
    pass
plt.subplots_adjust(left=0.08, bottom=0.26, right=0.91, top=0.84)

line_ac, = ax.plot([], [], linewidth=2.8, color="#2563eb", label="Production AC")
line_grid, = ax.plot([], [], linewidth=2.2, color="#f97316", label="Réseau DDSU")
line_linky, = ax.plot([], [], linewidth=2.0, color="#dc2626", linestyle="--", label="Linky Dinky")
limit_ax = ax.twinx()
line_limit, = limit_ax.plot([], [], linewidth=2.0, color="#16a34a", label="Limite DTU")

ax.set_xlabel("Date / heure")
ax.set_ylabel("Puissance (W)")
ax.set_ylim(-500, 2200)
ax.set_facecolor((1, 1, 1, 0.32))
ax.axhline(0, linewidth=1, color="#94a3b8")
ax.grid(True, color="#dbe3ef", linewidth=0.7)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
limit_ax.set_ylim(0, 120)
limit_ax.set_ylabel("Limite DTU (%)", color="#16a34a")
limit_ax.tick_params(axis="y", colors="#16a34a")
limit_ax.spines["top"].set_visible(False)
limit_ax.spines["left"].set_visible(False)

status_text = fig.text(0.08, 0.105, "Connexion au DTU...", ha="left", va="bottom", fontsize=9, color="#475569")
# Les cartes de tête ont été retirées visuellement ; les objets sont conservés pour l'animation Matplotlib.
live_cards = [fig.text(0, 0, "", visible=False) for _ in range(4)]

footer_style = dict(boxstyle="round,pad=0.45", facecolor="#ffffff", edgecolor="#dbe3ef")
end_labels = [
    fig.text(0.08, 0.94, "Limite DTU —", ha="left", va="center", fontsize=10, color="#16a34a", bbox=footer_style),
    fig.text(0.29, 0.94, "Production —", ha="left", va="center", fontsize=10, color="#2563eb", bbox=footer_style),
    fig.text(0.50, 0.94, "Réseau DDSU —", ha="left", va="center", fontsize=10, color="#f97316", bbox=footer_style),
    fig.text(0.71, 0.94, "Linky Dinky —", ha="left", va="center", fontsize=10, color="#dc2626", bbox=footer_style),
]

STATUS_COLORS = {
    "online": "#16a34a",
    "delayed": "#f97316",
    "offline": "#dc2626",
    "unknown": "#64748b",
}
connection_badges = [
    fig.text(0.08, 0.145, "● DTU en attente", ha="left", va="center", fontsize=8, color="white"),
    fig.text(0.29, 0.145, "● Linky/Dinky en attente", ha="left", va="center", fontsize=8, color="white"),
    fig.text(0.58, 0.145, "☁ Cloud S-Miles non vérifié", ha="left", va="center", fontsize=8, color="white"),
]

def set_connection_badge(badge, state, text):
    """Met à jour un état de connexion sans masquer le fond photo."""
    badge.set_text(text)
    badge.set_bbox(dict(boxstyle="round,pad=0.25", facecolor=STATUS_COLORS[state], edgecolor="white", alpha=0.92))

set_connection_badge(connection_badges[0], "delayed", "● DTU en attente")
set_connection_badge(connection_badges[1], "delayed", "● Linky/Dinky en attente")
set_connection_badge(connection_badges[2], "unknown", "☁ Cloud S-Miles non vérifié")

# Calque indÃ©pendant : le curseur reste au-dessus du fond et de l'axe secondaire.
# Curseur de lecture ajoutÃ© directement Ã  la figure : il reste toujours au premier plan.
cursor_line = Line2D([0, 0], [0, 1], transform=ax.get_xaxis_transform(), color="#0f172a",
                     linewidth=2.0, linestyle="--", visible=False, zorder=100)
cursor_dot = Line2D([], [], transform=ax.transData, linestyle="", marker="o", markersize=8,
                    color="#2563eb", markeredgecolor="white", markeredgewidth=1.2,
                    visible=False, zorder=101)
fig.add_artist(cursor_line)
fig.add_artist(cursor_dot)
cursor_box = fig.text(
    0, 0, "", transform=fig.transFigure, fontsize=9, ha="left", va="top", visible=False,
    bbox=dict(boxstyle="round,pad=0.45", facecolor="#ffffff", edgecolor="#0f172a", alpha=0.62), zorder=102,
)


def show_cursor(index):
    """Place la barre pointillÃ©e et la boÃ®te de valeurs sur une mesure."""
    if not times:
        return
    index = max(0, min(index, len(times) - 1))
    x_values = mdates.date2num(times)
    point_time = times[index]
    production = ac_power[index]
    grid = grid_power[index]
    limit = power_limit[index]
    linky = linky_power[index]
    linky_text = "—" if linky != linky else f"{linky:.0f} W"

    point_x = mdates.date2num(point_time)
    cursor_line.set_xdata([point_x, point_x])
    cursor_line.set_visible(True)
    cursor_dot.set_data([point_x], [production])
    cursor_dot.set_visible(True)
    top_x, _ = fig.transFigure.inverted().transform(
        ax.transData.transform((point_x, ax.get_ylim()[1]))
    )
    if index > len(times) * 0.78:
        cursor_box.set_ha("right")
        cursor_box.set_position((top_x - 0.008, 0.895))
    else:
        cursor_box.set_ha("left")
        cursor_box.set_position((top_x + 0.008, 0.895))
    cursor_box.set_text(
        f"{point_time:%d/%m/%Y %H:%M:%S}\n"
        f"Production  {production:.0f} W\n"
        f"Réseau DTU  {grid:+.0f} W\n"
        f"Limite DTU  {limit:.0f} %\n"
        f"Linky       {linky_text}"
    )
    cursor_box.set_visible(True)
    fig.canvas.draw_idle()


def move_cursor(event):
    """Affiche les mesures de la date la plus proche du curseur de la souris."""
    if showing_bilan or not times or event.x is None or event.y is None:
        return
    if not ax.bbox.contains(event.x, event.y):
        cursor_line.set_visible(False)
        cursor_dot.set_visible(False)
        cursor_box.set_visible(False)
        fig.canvas.draw_idle()
        return
    xdata = ax.transData.inverted().transform((event.x, event.y))[0]
    x_values = mdates.date2num(times)
    index = bisect_left(x_values, xdata)
    if index >= len(x_values):
        index = len(x_values) - 1
    elif index > 0 and abs(x_values[index - 1] - xdata) < abs(x_values[index] - xdata):
        index -= 1
    show_cursor(index)


fig.canvas.mpl_connect("motion_notify_event", move_cursor)

def read_dtu():
    """Lecture DTU robuste : essaie l'adresse configurée puis les adresses connues."""
    global HOST
    startupinfo = None
    creationflags = 0
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    hosts = [HOST] if HOST else []
    if not hosts:
        raise RuntimeError("adresse IP du DTU à renseigner dans config_v5.json")

    errors = []
    for host in hosts:
        cmd = ["hoymiles-wifi", "--host", host, "--as-json", "get-real-data-new"]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=12,
                startupinfo=startupinfo, creationflags=creationflags
            )
            text = result.stdout.strip()
            if not text:
                raise RuntimeError(result.stderr.strip() or "Aucune réponse")
            data = json.loads(text)
            if "error" in data:
                raise RuntimeError(str(data["error"]))
            if "sgsData" not in data or "meterData" not in data:
                raise RuntimeError("Réponse DTU incomplète")
            HOST = host
            return data
        except Exception as e:
            errors.append(f"{host}: {e}")
    raise RuntimeError(" | ".join(errors))

def read_linky_tcp():
    cfg = CONFIG.get("linky", {})
    if not cfg.get("enabled"):
        return None, "en attente du module TIC"
    host = str(cfg.get("host", "")).strip()
    port = int(cfg.get("port", 0) or 0)
    if not host or not port:
        return None, "configuration TCP incomplète"
    try:
        with socket.create_connection((host, port), timeout=float(cfg.get("timeout_s", 2))) as s:
            raw = s.recv(4096).decode("utf-8", errors="ignore").strip()
        # V5 prépare la connexion. Le décodage exact sera adapté au protocole du module reçu.
        try:
            obj = json.loads(raw)
            for key in ("power", "power_w", "linky_w", "sinsts"):
                if key in obj:
                    return float(obj[key]), "connecté"
        except Exception:
            pass
        return None, "TCP connecté — format TIC à régler"
    except Exception as e:
        return None, f"hors ligne ({e})"


def read_linky_dinky_http():
    """Lit la puissance active du Denky D4 / Tasmota par son API JSON locale."""
    cfg = CONFIG.get("linky", {})
    host = str(cfg.get("host", "")).strip()
    port = int(cfg.get("port", 80) or 80)
    if not host:
        return None, "configuration Dinky incomplète"

    # Commande Tasmota en lecture seule : elle retourne StatusSNS.ENERGY.
    command = str(cfg.get("path", "") or "Status 8")
    url = f"http://{host}:{port}/cm?cmnd={quote(command)}"
    try:
        with urlopen(url, timeout=float(cfg.get("timeout_s", 2))) as response:
            obj = json.loads(response.read().decode("utf-8"))
        energy = obj.get("StatusSNS", {}).get("ENERGY", {})
        if "Power" not in energy:
            raise RuntimeError("champ StatusSNS.ENERGY.Power absent")
        return float(energy["Power"]), "Dinky connecté"
    except (OSError, URLError, ValueError, json.JSONDecodeError, RuntimeError) as e:
        return None, f"Dinky hors ligne ({e})"


def read_linky():
    """Conserve le protocole TCP existant et ajoute l'API HTTP du Dinky."""
    cfg = CONFIG.get("linky", {})
    if not cfg.get("enabled"):
        return None, "en attente du module TIC"
    mode = str(cfg.get("mode", "tcp")).lower()
    if mode in ("dinky_http", "tasmota_http"):
        return read_linky_dinky_http()
    if mode == "tcp":
        return read_linky_tcp()
    return None, f"mode Linky inconnu ({mode})"

def redraw():
    line_ac.set_data(times, ac_power)
    line_grid.set_data(times, grid_power)
    line_limit.set_data(times, power_limit)
    line_linky.set_data(times, linky_power)
    if times and not showing_bilan:
        show_cursor(len(times) - 1)
    if showing_bilan:
        draw_bilan()

def update_end_labels():
    """Affiche les valeurs à droite en évitant le chevauchement."""
    if not times:
        return
    linky = linky_power[-1]
    linky_txt = "—" if linky != linky else f"{linky:.0f} W"
    end_labels[0].set_text(f"Limite DTU  {power_limit[-1]:.0f} %")
    end_labels[1].set_text(f"Production  {ac_power[-1]:.0f} W")
    end_labels[2].set_text(f"Réseau DDSU  {grid_power[-1]:+.0f} W")
    end_labels[3].set_text(f"Linky Dinky  {linky_txt}")
    return

    series = [
        (ac_power, "Production"),
        (grid_power, "DDSU"),
        (power_limit, "Consigne"),
        (linky_power, "Linky"),
    ]
    visible = []
    for ann, (values, name) in zip(end_labels, series):
        val = values[-1]
        if val != val:
            ann.set_text("")
            continue
        visible.append([ann, float(val), name])

    visible.sort(key=lambda x: x[1])
    # Les petites puissances (0 / DDSU / consigne) restent lisibles à droite.
    min_gap = 120.0
    for i in range(1, len(visible)):
        if visible[i][1] - visible[i-1][1] < min_gap:
            visible[i][1] = visible[i-1][1] + min_gap

    for ann, display_y, name in visible:
        original = next(values[-1] for values, n in series if n == name)
        ann.xy = (times[-1], display_y)
        ann.set_text(f"{name} {original:.0f} W")

def export_history(event=None):
    """Copie l'historique complet sur le Bureau, sans boîte de dialogue."""
    try:
        if not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0:
            raise RuntimeError("aucun historique à exporter")

        default_name = f"hoymiles_historique_{datetime.now():%Y%m%d_%H%M}.csv"
        desktop = Path.home() / "Desktop"
        export_dir = desktop if desktop.exists() else BASE / "Exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        destination = export_dir / default_name
        shutil.copy2(CSV_FILE, destination)
        status_text.set_text(f"Historique exporté : {destination}")
    except Exception as e:
        status_text.set_text(f"Export impossible — {e}")
    fig.canvas.draw_idle()

showing_bilan = False
bilan_period = "jour"
bilan_ax = fig.add_axes([0.08, 0.28, 0.83, 0.52])
bilan_ax.set_visible(False)

def float_from_user(value, label):
    try:
        return float(value.replace(",", ".").strip())
    except Exception:
        raise ValueError(f"Valeur invalide pour {label}")

def parse_hc_ranges(value):
    ranges = []
    for part in str(value or "").split(","):
        if "-" not in part:
            continue
        start, end = (text.strip() for text in part.split("-", 1))
        try:
            sh, sm = (int(x) for x in start.split(":"))
            eh, em = (int(x) for x in end.split(":"))
            ranges.append((sh * 60 + sm, eh * 60 + em))
        except Exception:
            pass
    return ranges

def is_hc(when, ranges):
    minute = when.hour * 60 + when.minute
    for start, end in ranges:
        if start <= end and start <= minute < end:
            return True
        if start > end and (minute >= start or minute < end):
            return True
    return False

def calculate_bilan_day():
    tariffs = CONFIG["tarifs_edf"]
    ranges = parse_hc_ranges(tariffs.get("plages_hc", ""))
    direction = 1 if tariffs.get("ddsu_import_positif", True) else -1
    today = datetime.now().date()
    now = datetime.now()
    result = {"pv": 0.0, "auto": 0.0, "edf": 0.0, "hp": 0.0, "hc": 0.0, "cost": 0.0}

    for index, when in enumerate(times):
        if when.date() != today:
            continue
        next_when = times[index + 1] if index + 1 < len(times) else now
        seconds = min((next_when - when).total_seconds(), 180)
        if seconds <= 0:
            continue
        pv = max(0.0, float(ac_power[index]))
        grid = direction * float(grid_power[index])
        edf = max(0.0, grid)
        home = max(0.0, pv + grid)
        auto = min(pv, home)
        factor = seconds / 3_600_000
        result["pv"] += pv * factor
        result["auto"] += auto * factor
        result["edf"] += edf * factor
        if is_hc(when, ranges):
            result["hc"] += edf * factor
        else:
            result["hp"] += edf * factor

    hp_price = float(tariffs.get("hp_eur_kwh", 0.0) or 0.0)
    hc_price = float(tariffs.get("hc_eur_kwh", 0.0) or 0.0)
    monthly = float(tariffs.get("abonnement_mensuel_eur", 0.0) or 0.0)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    result["cost"] = result["hp"] * hp_price + result["hc"] * hc_price + monthly / days_in_month
    return result

def calculate_bilan_period():
    """Calcule le bilan pour la période sélectionnée, sans calculer d'injection."""
    tariffs = CONFIG["tarifs_edf"]
    direction = 1 if tariffs.get("ddsu_import_positif", True) else -1
    now = datetime.now()
    titles = {
        "suivi": "Bilan consommation — suivi instantané",
        "jour": "Bilan consommation — aujourd'hui",
        "semaine": "Bilan consommation — cette semaine",
        "mois": "Bilan consommation — ce mois",
        "annee": "Bilan consommation — cette année",
    }
    if bilan_period == "jour":
        result = calculate_bilan_day()
        result.update({"instant": False, "title": titles["jour"]})
        return result
    if bilan_period == "suivi":
        result = {"pv": 0.0, "auto": 0.0, "edf": 0.0, "hp": 0.0, "hc": 0.0, "cost": 0.0,
                  "instant": True, "title": titles["suivi"]}
        if times:
            pv = max(0.0, float(ac_power[-1]))
            grid = direction * float(grid_power[-1])
            result.update({"pv": pv, "auto": min(pv, max(0.0, pv + grid)), "edf": max(0.0, grid)})
        return result

    if bilan_period == "semaine":
        start = datetime.combine(now.date() - timedelta(days=now.weekday()), datetime.min.time())
    elif bilan_period == "mois":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    ranges = parse_hc_ranges(tariffs.get("plages_hc", ""))
    result = {"pv": 0.0, "auto": 0.0, "edf": 0.0, "hp": 0.0, "hc": 0.0, "cost": 0.0,
              "instant": False, "title": titles[bilan_period]}
    for index, when in enumerate(times):
        if when < start or when > now:
            continue
        next_when = times[index + 1] if index + 1 < len(times) else now
        seconds = min((next_when - when).total_seconds(), 180)
        if seconds <= 0:
            continue
        pv = max(0.0, float(ac_power[index]))
        grid = direction * float(grid_power[index])
        edf = max(0.0, grid)
        factor = seconds / 3_600_000
        result["pv"] += pv * factor
        result["auto"] += min(pv, max(0.0, pv + grid)) * factor
        result["edf"] += edf * factor
        result["hc" if is_hc(when, ranges) else "hp"] += edf * factor

    hp_price = float(tariffs.get("hp_eur_kwh", 0.0) or 0.0)
    hc_price = float(tariffs.get("hc_eur_kwh", 0.0) or 0.0)
    monthly = float(tariffs.get("abonnement_mensuel_eur", 0.0) or 0.0)
    subscription = 0.0
    day = start.date()
    while day <= now.date():
        subscription += monthly / calendar.monthrange(day.year, day.month)[1]
        day += timedelta(days=1)
    result["cost"] = result["hp"] * hp_price + result["hc"] * hc_price + subscription
    return result

def draw_bilan():
    if not showing_bilan:
        return
    bilan = calculate_bilan_period()
    tariffs = CONFIG["tarifs_edf"]
    bilan_ax.clear()
    bilan_ax.set_facecolor((1, 1, 1, 0.40))
    values = [bilan["pv"], bilan["auto"], bilan["edf"]]
    labels = ["Production PV", "Autoconsommée", "Achat EDF"]
    unit = "W" if bilan["instant"] else "kWh"
    bars = bilan_ax.bar(labels, values, color=["#2563eb", "#16a34a", "#f97316"], width=0.58)
    bilan_ax.set_ylabel("Énergie aujourd'hui (kWh)")
    bilan_ax.grid(axis="y", color="#dbe3ef", linewidth=0.7)
    bilan_ax.set_axisbelow(True)
    bilan_ax.set_ylabel("Puissance instantanée (W)" if bilan["instant"] else "Énergie (kWh)")
    bilan_ax.spines["top"].set_visible(False)
    bilan_ax.spines["right"].set_visible(False)
    for bar, value in zip(bars, values):
        bilan_ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.0f} W" if bilan["instant"] else f"{value:.2f} kWh",
                      ha="center", va="bottom", fontsize=10)
    tariff_note = "Tarifs à renseigner" if not (tariffs.get("hp_eur_kwh") or tariffs.get("hc_eur_kwh")) else \
        f"HP {tariffs['hp_eur_kwh']:.4f} €/kWh  |  HC {tariffs['hc_eur_kwh']:.4f} €/kWh"
    bilan_ax.set_title("Bilan consommation — zéro injection", loc="left", fontsize=14, pad=16)
    bilan_ax.set_title(bilan["title"], loc="left", fontsize=14, pad=16)
    if bilan["instant"]:
        summary = f"Production : {bilan['pv']:.0f} W  |  Autoconsommation : {bilan['auto']:.0f} W\nAchat EDF instantané : {bilan['edf']:.0f} W  |  {tariff_note}"
    else:
        summary = f"Achat EDF : {bilan['edf']:.2f} kWh (HP {bilan['hp']:.2f} / HC {bilan['hc']:.2f})\nCoût estimé de la période : {bilan['cost']:.2f} €  |  {tariff_note}"
    bilan_ax.text(0.43, 1.10, summary, transform=bilan_ax.transAxes, va="top", fontsize=10,
                  bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#dbe3ef", alpha=0.82),
                  clip_on=False)

def open_tariffs(event=None):
    tariffs = CONFIG["tarifs_edf"]
    try:
        parent = plt.get_current_fig_manager().window
        hp = simpledialog.askstring("Tarifs EDF", "Prix HP en €/kWh :", initialvalue=str(tariffs["hp_eur_kwh"]), parent=parent)
        if hp is None:
            return
        hc = simpledialog.askstring("Tarifs EDF", "Prix HC en €/kWh :", initialvalue=str(tariffs["hc_eur_kwh"]), parent=parent)
        if hc is None:
            return
        monthly = simpledialog.askstring("Tarifs EDF", "Abonnement mensuel en € :", initialvalue=str(tariffs["abonnement_mensuel_eur"]), parent=parent)
        if monthly is None:
            return
        ranges = simpledialog.askstring("Tarifs EDF", "Plages HC (ex. 22:00-06:00,13:00-15:00) :", initialvalue=str(tariffs["plages_hc"]), parent=parent)
        if ranges is None:
            return
        sense = simpledialog.askstring("Tarifs EDF", "DDSU : 1 = achat EDF positif, -1 = achat EDF négatif :", initialvalue="1" if tariffs.get("ddsu_import_positif", True) else "-1", parent=parent)
        if sense is None:
            return
        tariffs.update({
            "hp_eur_kwh": float_from_user(hp, "HP"),
            "hc_eur_kwh": float_from_user(hc, "HC"),
            "abonnement_mensuel_eur": float_from_user(monthly, "abonnement"),
            "plages_hc": ranges.strip(),
            "ddsu_import_positif": float_from_user(sense, "sens DDSU") >= 0,
        })
        save_config()
        draw_bilan()
        fig.canvas.draw_idle()
    except Exception as exc:
        messagebox.showerror("Tarifs EDF", str(exc), parent=plt.get_current_fig_manager().window)

period_buttons = {}
period_caption = fig.text(0.08, 0.252, "Période du bilan", ha="left", va="center", fontsize=9,
                          color="#334155", visible=False,
                          bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dbe3ef", alpha=0.72))

def refresh_period_buttons():
    period_caption.set_visible(showing_bilan)
    for period, button in period_buttons.items():
        button.ax.set_visible(showing_bilan)
        button.ax.set_facecolor("#2563eb" if period == bilan_period else "#64748b")

def set_bilan_period(period):
    global bilan_period
    bilan_period = period
    refresh_period_buttons()
    draw_bilan()
    fig.canvas.draw_idle()

def toggle_bilan(event=None):
    global showing_bilan
    showing_bilan = not showing_bilan
    ax.set_visible(not showing_bilan)
    limit_ax.set_visible(not showing_bilan)
    bilan_ax.set_visible(showing_bilan)
    cursor_line.set_visible(False)
    cursor_dot.set_visible(False)
    cursor_box.set_visible(False)
    bilan_button.label.set_text("Suivi production" if showing_bilan else "Bilan consommation")
    refresh_period_buttons()
    if showing_bilan:
        draw_bilan()
    fig.canvas.draw_idle()

tariffs_ax = plt.axes([0.47, 0.165, 0.13, 0.048])
tariffs_button = Button(tariffs_ax, "Tarifs EDF", color="#475569", hovercolor="#334155")
tariffs_button.label.set_color("white")
tariffs_button.on_clicked(open_tariffs)

bilan_button_ax = plt.axes([0.61, 0.165, 0.18, 0.048])
bilan_button = Button(bilan_button_ax, "Bilan consommation", color="#16a34a", hovercolor="#15803d")
bilan_button.label.set_color("white")
bilan_button.on_clicked(toggle_bilan)

for position, (period, label) in enumerate((
    ("suivi", "Suivi"), ("jour", "Jour"), ("semaine", "Semaine"), ("mois", "Mois"), ("annee", "Année"),
)):
    period_ax = plt.axes([0.17 + position * 0.105, 0.215, 0.095, 0.038])
    period_button = Button(period_ax, label, color="#2563eb" if period == bilan_period else "#64748b", hovercolor="#334155")
    period_button.label.set_color("white")
    period_button.on_clicked(lambda event, choice=period: set_bilan_period(choice))
    period_ax.set_visible(False)
    period_buttons[period] = period_button

export_ax = plt.axes([0.80, 0.165, 0.13, 0.048])
export_button = Button(export_ax, "Exporter CSV", color="#2563eb", hovercolor="#1d4ed8")
export_button.label.set_color("white")
export_button.on_clicked(export_history)

def update(_):
    global last_success, dtu_failures
    linky_started = monotonic()
    try:
        # Le Linky reste utilisable même lorsque le DTU est temporairement indisponible.
        lky, linky_status = read_linky()
    except Exception as e:
        lky, linky_status = None, f"erreur Linky ({e})"
    linky_delay = monotonic() - linky_started
    if lky is not None:
        set_connection_badge(
            connection_badges[1], "delayed" if linky_delay > 3 else "online",
            "● Linky/Dinky délai important" if linky_delay > 3 else "● Linky/Dinky connecté",
        )
    elif "attente" in linky_status.lower():
        set_connection_badge(connection_badges[1], "delayed", "● Linky/Dinky en attente")
    else:
        set_connection_badge(connection_badges[1], "offline", "● Linky/Dinky hors ligne")

    dtu_started = monotonic()
    try:
        data = read_dtu()
        now = datetime.now()
        last_success = now
        dtu_delay = monotonic() - dtu_started
        set_connection_badge(
            connection_badges[0], "delayed" if dtu_delay > 3 else "online",
            "● DTU délai important" if dtu_delay > 3 else "● DTU connecté",
        )

        sgs = data["sgsData"][0]
        meter = data["meterData"][0]
        ac = sgs["activePower"] / 10
        # Certains firmwares ne renvoient temporairement que la valeur de phase.
        # Les deux champs représentent la même mesure sur cette installation monophasée.
        grid_raw = meter.get("phaseTotalPower", meter.get("phaseAPower"))
        if grid_raw is None:
            raise RuntimeError("puissance réseau absente de la réponse DTU")
        grid = float(grid_raw)
        limit_w = sgs["powerLimit"] / 10
        times.append(now)
        ac_power.append(ac)
        grid_power.append(grid)
        power_limit.append(limit_w)
        linky_power.append(float(lky) if lky is not None else float("nan"))

        with CSV_FILE.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                now.strftime("%Y-%m-%d %H:%M:%S"),
                round(ac, 1), grid, round(limit_w, 1),
                "" if lky is None else round(lky, 1)
            ])

        redraw()
        update_end_labels()

        if follow_now and len(times) >= 2:
            start_index = max(0, len(times) - MAX_VISIBLE_POINTS)
            ax.set_xlim(times[start_index], times[-1])

        if lky is None:
            linky_card_txt = "LINKY DINKY\nEN ATTENTE"
        else:
            linky_card_txt = f"LINKY DINKY\n{lky:.0f} W (TIC)"
        live_cards[0].set_text(f"PRODUCTION\n{ac:.0f} W")
        live_cards[1].set_text(f"RÉSEAU DDSU\n{grid:+.0f} W")
        live_cards[2].set_text(f"LIMITE DTU\n{limit_w:.0f} %")
        live_cards[3].set_text(linky_card_txt)

        mode = "suivi direct" if follow_now else "historique"
        status_text.set_text(
            f"Dernière mise à jour : {now:%d/%m/%Y %H:%M:%S} — DTU {HOST} connecté — dernière réponse 0 s — "
            f"{len(times)} mesures — {len(LOADED_HISTORY_FILES)} fichier(s) historique — "
            f"échecs lecture DTU : {dtu_failures} — {mode} — Linky : {linky_status}"
        )
    except Exception as e:
        dtu_failures += 1
        set_connection_badge(connection_badges[0], "offline", "● DTU hors ligne")
        age = "jamais"
        if last_success is not None:
            age = f"{int((datetime.now() - last_success).total_seconds())} s"
        last_update = last_success.strftime("%d/%m/%Y %H:%M:%S") if last_success else "jamais"
        status_text.set_text(
            f"Dernière mise à jour : {last_update} — DTU sans réponse — dernière réponse il y a {age} — "
            f"échecs lecture DTU : {dtu_failures} — Linky : {linky_status} — {e}"
        )

    return (
        line_ac, line_grid, line_limit, line_linky, cursor_line, cursor_dot, cursor_box,
        *live_cards, status_text, *end_labels, *connection_badges,
    )

redraw()
update_end_labels()
if times:
    start_index = max(0, len(times) - MAX_VISIBLE_POINTS)
    ax.set_xlim(times[start_index], times[-1])
else:
    # Évite l'axe Matplotlib 31/12 -> 01/01 quand l'historique est neuf.
    now0 = datetime.now()
    ax.set_xlim(now0, now0.replace(second=0, microsecond=0) + __import__("datetime").timedelta(hours=2))
    fig.autofmt_xdate()

# Première lecture immédiate au démarrage, puis une lecture chaque minute.
update(None)
ani = FuncAnimation(fig, update, interval=INTERVAL_MS, cache_frame_data=False)

def enable_full_window_resize():
    """Agrandit le canevas avec la fenÃªtre Tk, y compris aprÃ¨s un plein Ã©cran."""
    try:
        manager = plt.get_current_fig_manager()
        window = manager.window
        canvas_widget = manager.canvas.get_tk_widget()
        canvas_widget.pack_configure(fill="both", expand=True)
        last_size = [0, 0]

        def resize_to_window():
            width = window.winfo_width()
            toolbar = getattr(manager, "toolbar", None)
            toolbar_height = toolbar.winfo_height() if toolbar is not None else 0
            height = window.winfo_height() - toolbar_height
            if width < 640 or height < 480:
                return
            if abs(width - last_size[0]) < 3 and abs(height - last_size[1]) < 3:
                return
            last_size[:] = [width, height]
            manager.resize(width, height)

        def on_configure(event):
            if event.widget is window:
                window.after_idle(resize_to_window)

        def toggle_fullscreen(event=None):
            window.attributes("-fullscreen", not bool(window.attributes("-fullscreen")))
            return "break"

        def leave_fullscreen(event=None):
            window.attributes("-fullscreen", False)

        window.bind("<Configure>", on_configure, add="+")
        window.bind("<F11>", toggle_fullscreen)
        window.bind("<Escape>", leave_fullscreen)

        def on_tk_motion(event):
            x = event.x
            y = canvas_widget.winfo_height() - event.y
            if showing_bilan or not times or not ax.bbox.contains(x, y):
                return
            xdata = ax.transData.inverted().transform((x, y))[0]
            x_values = mdates.date2num(times)
            index = bisect_left(x_values, xdata)
            if index >= len(x_values):
                index = len(x_values) - 1
            elif index > 0 and abs(x_values[index - 1] - xdata) < abs(x_values[index] - xdata):
                index -= 1
            show_cursor(index)

        canvas_widget.bind("<Motion>", on_tk_motion, add="+")
        window.after(200, resize_to_window)
    except Exception:
        pass

enable_full_window_resize()
plt.show()
