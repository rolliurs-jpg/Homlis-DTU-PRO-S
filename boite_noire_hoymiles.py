import csv
import json
import re
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

VERSION = "6.7.5"
DEFAULT_DTU_HOST = ""
INTERVAL_MS = 60000
MAX_VISIBLE_POINTS = 300

BASE = Path.home() / "AppData" / "Local" / "BoiteNoireHoymiles"
BASE.mkdir(parents=True, exist_ok=True)
CSV_FILE = BASE / "hoymiles_log.csv"
LINKY_INDEX_FILE = BASE / "linky_index_log.csv"
CONFIG_FILE = BASE / "config_v5.json"
IMPORT_DIR = BASE / "Historiques_importes"
IMPORT_DIR.mkdir(parents=True, exist_ok=True)
BACKGROUND_IMAGE = Path(__file__).with_name("fond_solaire.png")
APP_ICON = Path(__file__).with_name("icone_panneau_solaire.ico")

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
        "abonnement_journalier_eur": 0.0,
        "plages_hc": "",
        "ddsu_import_positif": True
    },
    # Relevés saisis depuis l'espace client EDF, indexés par mois AAAA-MM.
    "releves_edf": {}
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
        # Migration sans toucher aux réglages TCP réellement configurés.
        if saved_linky == LEGACY_EMPTY_LINKY_CONFIG:
            saved_linky = DEFAULT_CONFIG["linky"]
        cfg["linky"] = {**DEFAULT_CONFIG["linky"], **saved_linky}
        saved_tariffs = data.get("tarifs_edf", {})
        if not isinstance(saved_tariffs, dict):
            saved_tariffs = {}
        cfg["tarifs_edf"] = {**DEFAULT_CONFIG["tarifs_edf"], **saved_tariffs}
        saved_readings = data.get("releves_edf", {})
        cfg["releves_edf"] = saved_readings if isinstance(saved_readings, dict) else {}
        return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()

CONFIG = load_config()
HOST = str(CONFIG.get("dtu_host", DEFAULT_DTU_HOST)).strip() or DEFAULT_DTU_HOST

def save_config():
    CONFIG_FILE.write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")

times, ac_power, grid_power, power_limit = [], [], [], []
linky_power = []
linky_hc_index, linky_hp_index = [], []
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

def load_linky_indexes():
    """Charge les index cumulés enregistrés localement par le Dinky."""
    if not LINKY_INDEX_FILE.exists():
        return 0
    count = 0
    try:
        with LINKY_INDEX_FILE.open("r", newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    when = datetime.strptime(row["date_heure"], "%Y-%m-%d %H:%M:%S")
                    hc = float(row["hc_kwh"])
                    hp = float(row["hp_kwh"])
                    linky_hc_index.append((when, hc))
                    linky_hp_index.append((when, hp))
                    count += 1
                except (KeyError, TypeError, ValueError):
                    pass
    except OSError:
        pass
    return count

LOADED_LINKY_INDEXES = load_linky_indexes()

if not CSV_FILE.exists():
    with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            ["date_heure", "production_ac_w", "reseau_ddsu_w", "consigne_w", "linky_w"]
        )

if not LINKY_INDEX_FILE.exists():
    with LINKY_INDEX_FILE.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["date_heure", "hc_kwh", "hp_kwh"])

fig, ax = plt.subplots(figsize=(13.5, 7.5))
fig.patch.set_facecolor("#f8fafc")
try:
    # Même symbole dans la barre de titre, la barre des tâches et le raccourci Windows.
    manager = plt.get_current_fig_manager()
    if APP_ICON.exists():
        manager.window.iconbitmap(default=str(APP_ICON))
except Exception:
    pass
try:
    background_ax = fig.add_axes([0, 0, 1, 1], zorder=-10)
    background_ax.imshow(plt.imread(BACKGROUND_IMAGE), aspect="auto", alpha=0.32)
    background_ax.set_axis_off()
except Exception:
    pass
plt.subplots_adjust(left=0.08, bottom=0.34, right=0.91, top=0.84)

line_ac, = ax.plot([], [], linewidth=2.8, color="#2563eb", label="Production AC")
line_grid, = ax.plot([], [], linewidth=2.2, color="#f59e0b", label="Réseau DDSU")
line_linky, = ax.plot([], [], linewidth=2.0, color="#7c3aed", linestyle="--", label="Linky Dinky")
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

status_text = fig.text(0.08, 0.065, "Connexion au DTU...", ha="left", va="bottom", fontsize=9, color="#475569")
# Les cartes de tête ont été retirées visuellement ; les objets sont conservés pour l'animation Matplotlib.
live_cards = [fig.text(0, 0, "", visible=False) for _ in range(4)]

# En-tête du suivi direct : il disparaît sur le bilan, qui possède son propre titre.
dashboard_title = fig.text(0.08, 0.885, "Boîte noire Hoymiles", ha="left", va="center",
                           fontsize=16, fontweight="bold", color="#0f172a")
dashboard_subtitle = fig.text(0.08, 0.855, "Suivi de production · DTU Pro-S + Linky Dinky 4",
                              ha="left", va="center", fontsize=9, color="#475569")

footer_style = dict(boxstyle="round,pad=0.45", facecolor="#ffffff", edgecolor="#dbe3ef", alpha=0.88)
end_labels = [
    fig.text(0.08, 0.95, "Limite DTU —", ha="left", va="center", fontsize=10, color="#16a34a",
             bbox={**footer_style, "edgecolor": "#86efac"}),
    fig.text(0.29, 0.95, "Production —", ha="left", va="center", fontsize=10, color="#2563eb",
             bbox={**footer_style, "edgecolor": "#93c5fd"}),
    fig.text(0.50, 0.95, "Réseau DDSU —", ha="left", va="center", fontsize=10, color="#f59e0b",
             bbox={**footer_style, "edgecolor": "#fcd34d"}),
    fig.text(0.71, 0.95, "Linky Dinky —", ha="left", va="center", fontsize=10, color="#7c3aed",
             bbox={**footer_style, "edgecolor": "#c4b5fd"}),
]

STATUS_COLORS = {
    "online": "#16a34a",
    "delayed": "#f97316",
    "offline": "#dc2626",
    "unknown": "#64748b",
}
connection_badges = [
    fig.text(0.08, 0.105, "● DTU en attente", ha="left", va="center", fontsize=8, color="white"),
    fig.text(0.34, 0.105, "● Linky/Dinky en attente", ha="left", va="center", fontsize=8, color="white"),
]

def set_connection_badge(badge, state, text):
    """Met à jour un état de connexion sans masquer le fond photo."""
    badge.set_text(text)
    badge.set_bbox(dict(boxstyle="round,pad=0.25", facecolor=STATUS_COLORS[state], edgecolor="white", alpha=0.92))

set_connection_badge(connection_badges[0], "delayed", "● DTU en attente")
set_connection_badge(connection_badges[1], "delayed", "● Linky/Dinky en attente")

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

    hosts = []
    for host in (HOST, "10.10.100.162", "10.10.100.254"):
        if host and host not in hosts:
            hosts.append(host)

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

def read_dinky_energy_indexes():
    """Lit les index Linky HC/HP affichés par le firmware Téléinfo du Dinky."""
    cfg = CONFIG.get("linky", {})
    host = str(cfg.get("host", "")).strip()
    port = int(cfg.get("port", 80) or 80)
    if not host:
        return None, "configuration Dinky incomplète"
    url = f"http://{host}:{port}/?m=1"
    try:
        with urlopen(url, timeout=float(cfg.get("timeout_s", 2))) as response:
            page = response.read().decode("utf-8", errors="replace")
        def extract(label):
            match = re.search(rf"{label}</div>\s*<div class='tic36r'>([0-9.,]+)", page)
            if not match:
                raise RuntimeError(f"index {label} absent de la page Téléinfo")
            return float(match.group(1).replace(",", "."))
        return {"hc": extract("Creuses"), "hp": extract("Pleines")}, "index HC/HP lu"
    except (OSError, URLError, ValueError, RuntimeError) as e:
        return None, f"index Dinky indisponible ({e})"

def read_dinky_history(period, labels):
    """Lit les barres HC/HP déjà mémorisées par le Dinky, en kWh.

    Le DDSU reste affiché sur le suivi de production, mais il n'est pas une
    source suffisamment fiable pour le bilan d'achat EDF. Cette lecture utilise
    exclusivement l'historique Téléinfo du compteur Linky fourni par le Dinky.
    """
    period_code = {"semaine": 1, "mois": 2, "annee": 3}.get(period)
    if period_code is None:
        return None
    cfg = CONFIG.get("linky", {})
    host = str(cfg.get("host", "")).strip()
    port = int(cfg.get("port", 80) or 80)
    if not host:
        return None
    try:
        url = f"http://{host}:{port}/histo?period={period_code}"
        with urlopen(url, timeout=float(cfg.get("timeout_s", 2))) as response:
            page = response.read().decode("utf-8", errors="replace")
        ticks = [(float(x), text.strip()) for x, text in re.findall(
            r"<text class='time' x=([0-9.]+)[^>]*>([^<]+)</text>", page
        )]
        if not ticks:
            return None
        hc, hp = [0.0] * len(labels), [0.0] * len(labels)
        bars = re.findall(
            r"<rect class='c([01])' x=([0-9.]+)[^>]*width=([0-9.]+)[^>]*><title>([0-9.]+)</title>",
            page,
        )
        for kind, x, width, wh in bars:
            center = float(x) + float(width) / 2
            tick_index = min(range(len(ticks)), key=lambda pos: abs(ticks[pos][0] - center))
            text = ticks[tick_index][1]
            if period == "semaine":
                lookup = {"Lun": 0, "Mar": 1, "Mer": 2, "Jeu": 3, "Ven": 4, "Sam": 5, "Dim": 6}
                index = lookup.get(text[:3])
            elif period == "mois":
                index = int(text) - 1 if text.isdigit() else None
            else:
                lookup = {"Jan": 0, "Fev": 1, "Mar": 2, "Avr": 3, "Mai": 4, "Jun": 5,
                          "Jul": 6, "Aut": 7, "Sep": 8, "Oct": 9, "Nov": 10, "Dec": 11}
                index = lookup.get(text[:3])
            if index is None or not 0 <= index < len(labels):
                continue
            if kind == "0":
                hc[index] += float(wh) / 1000
            else:
                hp[index] += float(wh) / 1000
        return hc, hp
    except (OSError, URLError, ValueError, RuntimeError):
        return None

def append_linky_energy_indexes(when, indexes):
    """Conserve les index cumulés séparément sans modifier l'historique V6.2."""
    if not isinstance(indexes, dict):
        return
    hc = float(indexes["hc"])
    hp = float(indexes["hp"])
    if linky_hc_index and linky_hc_index[-1][0] == when:
        return
    linky_hc_index.append((when, hc))
    linky_hp_index.append((when, hp))
    with LINKY_INDEX_FILE.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([when.strftime("%Y-%m-%d %H:%M:%S"), f"{hc:.3f}", f"{hp:.3f}"])


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
bilan_period = "24h"
bilan_ax = fig.add_axes([0.08, 0.34, 0.83, 0.46])
bilan_ax.set_visible(False)
bilan_cost_ax = bilan_ax.twinx()
bilan_cost_ax.set_visible(False)

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

def calculate_dinky_energy(start, end):
    """Déduit les kWh importés de l'écart entre deux index Linky HC/HP."""
    samples = list(zip(linky_hc_index, linky_hp_index))
    samples = [(when_hc, hc, hp) for ((when_hc, hc), (when_hp, hp)) in samples
               if when_hc == when_hp and when_hc <= end]
    if len(samples) < 2:
        return None
    before = [sample for sample in samples if sample[0] <= start]
    first = before[-1] if before else samples[0]
    last = samples[-1]
    if last[0] <= first[0]:
        return None
    hc = last[1] - first[1]
    hp = last[2] - first[2]
    if hc < -0.01 or hp < -0.01:
        return None
    return {
        "hc": max(0.0, hc),
        "hp": max(0.0, hp),
        "total": max(0.0, hc) + max(0.0, hp),
        "complete": bool(before) and first[0] <= start + timedelta(minutes=2),
        "from": first[0],
    }

def dinky_energy_for_period(start, end):
    """Le bilan reste disponible même si le journal d'index est incomplet.

    Les index du Dinky sont un complément au calcul DDSU : une ligne CSV
    abîmée ou une lecture simultanée ne doit donc jamais empêcher
    l'ouverture de la page Bilan.
    """
    try:
        return calculate_dinky_energy(start, end)
    except Exception:
        return None

def calculate_bilan_day():
    tariffs = CONFIG["tarifs_edf"]
    ranges = parse_hc_ranges(tariffs.get("plages_hc", ""))
    direction = 1 if tariffs.get("ddsu_import_positif", True) else -1
    today = datetime.now().date()
    now = datetime.now()
    start = datetime.combine(today, datetime.min.time())
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
    daily = float(tariffs.get("abonnement_journalier_eur", tariffs.get("abonnement_mensuel_eur", 0.0)) or 0.0)
    result["cost"] = result["hp"] * hp_price + result["hc"] * hc_price + daily
    result["dinky"] = dinky_energy_for_period(start, now)
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
                  "instant": True, "title": titles["suivi"], "dinky": None}
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
    daily = float(tariffs.get("abonnement_journalier_eur", tariffs.get("abonnement_mensuel_eur", 0.0)) or 0.0)
    subscription = 0.0
    day = start.date()
    while day <= now.date():
        subscription += daily
        day += timedelta(days=1)
    result["cost"] = result["hp"] * hp_price + result["hc"] * hc_price + subscription
    result["dinky"] = dinky_energy_for_period(start, now)
    return result

def automatic_energy_series(period, now):
    """Produit les kWh PV et EDF par créneau à partir des mesures enregistrées."""
    if period == "24h":
        start = datetime.combine(now.date(), datetime.min.time())
        labels = [f"{hour:02d} h" for hour in range(24)]
        index_for = lambda when: when.hour
        title = "Bilan automatique — dernières 24 h"
    elif period == "semaine":
        start = datetime.combine(now.date() - timedelta(days=now.weekday()), datetime.min.time())
        labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        index_for = lambda when: (when.date() - start.date()).days
        title = "Bilan automatique — semaine en cours"
    elif period == "mois":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        labels = [str(day) for day in range(1, calendar.monthrange(now.year, now.month)[1] + 1)]
        index_for = lambda when: when.day - 1
        title = "Bilan automatique — mois en cours"
    else:
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
        index_for = lambda when: when.month - 1
        title = "Bilan automatique — année en cours"

    production = [0.0] * len(labels)
    for index, when in enumerate(times):
        if when < start or when > now:
            continue
        next_when = times[index + 1] if index + 1 < len(times) else now
        seconds = min((next_when - when).total_seconds(), 180)
        if seconds <= 0:
            continue
        try:
            bucket = index_for(when)
            if not 0 <= bucket < len(labels):
                continue
            factor = seconds / 3_600_000
            production[bucket] += max(0.0, float(ac_power[index])) * factor
        except (IndexError, TypeError, ValueError):
            continue

    # Achat EDF : seule la Téléinfo du Linky (Dinky 4) fait foi, jamais le DDSU.
    historic = read_dinky_history(period, labels)
    if historic is not None and sum(historic[0]) + sum(historic[1]) > 0:
        hc, hp = historic
        source = "Historique Dinky 4 / Linky"
    else:
        hc, hp = [0.0] * len(labels), [0.0] * len(labels)
        samples = list(zip(linky_hc_index, linky_hp_index))
        samples = [(when_hc, value_hc, value_hp) for ((when_hc, value_hc), (when_hp, value_hp)) in samples
                   if when_hc == when_hp]
        for previous, current in zip(samples, samples[1:]):
            when, previous_hc, previous_hp = previous
            current_when, current_hc, current_hp = current
            if current_when < start or current_when > now:
                continue
            try:
                bucket = index_for(current_when)
                if not 0 <= bucket < len(labels):
                    continue
                hc[bucket] += max(0.0, float(current_hc) - float(previous_hc))
                hp[bucket] += max(0.0, float(current_hp) - float(previous_hp))
            except (IndexError, TypeError, ValueError):
                continue
        source = "Index Dinky 4 depuis le démarrage"
    achat_edf = [hc_value + hp_value for hc_value, hp_value in zip(hc, hp)]
    return labels, production, achat_edf, hc, hp, title, source, start

def subscription_series(period, start, now, count, daily_subscription):
    """Répartit l'abonnement dans les colonnes de coût, sans le mélanger aux kWh."""
    values = [0.0] * count
    if daily_subscription <= 0:
        return values
    if period == "24h":
        return [daily_subscription / count] * count
    day = start.date()
    while day <= now.date():
        if period == "semaine":
            index = (day - start.date()).days
        elif period == "mois":
            index = day.day - 1
        else:
            index = day.month - 1
        if 0 <= index < count:
            values[index] += daily_subscription
        day += timedelta(days=1)
    return values

def draw_bilan():
    if not showing_bilan:
        return
    now = datetime.now()
    labels, production, achat_edf, hc, hp, title, dinky_source, start = automatic_energy_series(bilan_period, now)
    tariffs = CONFIG["tarifs_edf"]
    hp_price = float(tariffs.get("hp_eur_kwh", 0.0) or 0.0)
    hc_price = float(tariffs.get("hc_eur_kwh", 0.0) or 0.0)
    daily_subscription = float(tariffs.get("abonnement_journalier_eur", tariffs.get("abonnement_mensuel_eur", 0.0)) or 0.0)
    hp_cost = [value * hp_price for value in hp]
    hc_cost = [value * hc_price for value in hc]
    subscription = subscription_series(bilan_period, start, now, len(labels), daily_subscription)
    bilan_ax.clear()
    bilan_cost_ax.clear()
    bilan_cost_ax.set_visible(True)
    bilan_ax.set_facecolor((1, 1, 1, 0.40))
    bilan_cost_ax.set_facecolor((1, 1, 1, 0.0))
    positions = list(range(len(labels)))
    pv_positions = [position - 0.20 for position in positions]
    edf_positions = [position + 0.20 for position in positions]
    bilan_ax.bar(pv_positions, production, width=0.38, color="#2563eb", label="Production PV")
    bilan_cost_ax.bar(edf_positions, subscription, width=0.38, color="#111827", label="Abonnement EDF")
    bilan_cost_ax.bar(edf_positions, hp_cost, width=0.38, bottom=subscription, color="#f97316", label="Achat EDF HP")
    hp_and_subscription = [fixed + hp_value for fixed, hp_value in zip(subscription, hp_cost)]
    bilan_cost_ax.bar(edf_positions, hc_cost, width=0.38, bottom=hp_and_subscription, color="#7c3aed", label="Achat EDF HC")
    bilan_ax.set_xticks(positions)
    bilan_ax.set_xticklabels(labels, rotation=0 if len(labels) <= 12 else 60, ha="right" if len(labels) > 12 else "center")
    bilan_ax.set_ylabel("Énergie (kWh)")
    bilan_ax.grid(axis="y", color="#dbe3ef", linewidth=0.7)
    bilan_ax.set_axisbelow(True)
    bilan_ax.spines["top"].set_visible(False)
    bilan_ax.spines["right"].set_visible(False)
    bilan_cost_ax.set_ylabel("Coût EDF (€)", color="#334155")
    bilan_cost_ax.tick_params(axis="y", colors="#334155")
    bilan_cost_ax.spines["top"].set_visible(False)
    bilan_cost_ax.spines["left"].set_visible(False)
    left_handles, left_labels = bilan_ax.get_legend_handles_labels()
    right_handles, right_labels = bilan_cost_ax.get_legend_handles_labels()
    bilan_ax.legend(
        left_handles + right_handles, left_labels + right_labels,
        loc="lower left", bbox_to_anchor=(0.0, 1.02), frameon=False, ncol=2,
        borderaxespad=0.0,
    )
    bilan_ax.set_title(title, loc="left", fontsize=14, pad=42)
    total_pv = sum(production)
    total_edf = sum(achat_edf)
    subscription_cost = sum(subscription)
    estimated_cost = sum(hp_cost) + sum(hc_cost) + subscription_cost
    tariff_note = "Tarifs à renseigner" if not (tariffs.get("hp_eur_kwh") or tariffs.get("hc_eur_kwh")) else \
        f"HP {hp_price:.4f} €/kWh  |  HC {hc_price:.4f} €/kWh  |  Abo {daily_subscription:.2f} €/jour"
    bilan_ax.text(
        0.98, 1.16,
        f"Achat Linky : {total_edf:.2f} kWh (HC {sum(hc):.2f} / HP {sum(hp):.2f})\nCoût : {estimated_cost:.2f} € dont abonnement {subscription_cost:.2f} €\n{dinky_source} — {tariff_note}",
        transform=bilan_ax.transAxes, ha="right", va="top", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#dbe3ef", alpha=0.82),
        clip_on=False,
    )

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
        daily = simpledialog.askstring(
            "Tarifs EDF", "Abonnement journalier en euros :",
            initialvalue=str(tariffs.get("abonnement_journalier_eur", 0.63)), parent=parent
        )
        if daily is None:
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
            "abonnement_journalier_eur": float_from_user(daily, "abonnement journalier"),
            "plages_hc": ranges.strip(),
            "ddsu_import_positif": float_from_user(sense, "sens DDSU") >= 0,
        })
        save_config()
        draw_bilan()
        fig.canvas.draw_idle()
    except Exception as exc:
        messagebox.showerror("Tarifs EDF", str(exc), parent=plt.get_current_fig_manager().window)

def open_real_edf_reading(event=None):
    """Enregistre un total réel communiqué par EDF, sans accès au compte utilisateur."""
    try:
        parent = plt.get_current_fig_manager().window
        default_month = datetime.now().strftime("%Y-%m")
        month = simpledialog.askstring(
            "Relevé EDF réel", "Mois du relevé (AAAA-MM) :",
            initialvalue=default_month, parent=parent
        )
        if month is None:
            return
        month = month.strip()
        datetime.strptime(month + "-01", "%Y-%m-%d")
        previous = CONFIG.setdefault("releves_edf", {}).get(month, {})
        kwh = simpledialog.askstring(
            "Relevé EDF réel", "Achat EDF réel en kWh :",
            initialvalue=str(previous.get("kwh", "")), parent=parent
        )
        if kwh is None:
            return
        cost = simpledialog.askstring(
            "Relevé EDF réel", "Coût EDF réel en € :",
            initialvalue=str(previous.get("cout_eur", "")), parent=parent
        )
        if cost is None:
            return
        CONFIG["releves_edf"][month] = {
            "kwh": float_from_user(kwh, "kWh EDF réel"),
            "cout_eur": float_from_user(cost, "coût EDF réel"),
        }
        save_config()
        draw_bilan()
        fig.canvas.draw_idle()
    except Exception as exc:
        messagebox.showerror("Relevé EDF réel", str(exc), parent=plt.get_current_fig_manager().window)

period_buttons = {}
period_caption = fig.text(0.20, 0.225, "Période du bilan", ha="left", va="center", fontsize=9,
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
    bilan_cost_ax.set_visible(showing_bilan)
    dashboard_title.set_visible(not showing_bilan)
    dashboard_subtitle.set_visible(not showing_bilan)
    cursor_line.set_visible(False)
    cursor_dot.set_visible(False)
    cursor_box.set_visible(False)
    bilan_button.label.set_text("Suivi production" if showing_bilan else "Bilan consommation")
    layout_bottom_actions()
    refresh_period_buttons()
    if showing_bilan:
        draw_bilan()
    fig.canvas.draw_idle()

tariffs_ax = plt.axes([0.31, 0.145, 0.18, 0.048])
tariffs_button = Button(tariffs_ax, "Tarifs EDF", color="#64748b", hovercolor="#475569")
tariffs_button.label.set_color("white")
tariffs_button.on_clicked(open_tariffs)

bilan_button_ax = plt.axes([0.52, 0.145, 0.22, 0.048])
bilan_button = Button(bilan_button_ax, "Bilan consommation", color="#2563eb", hovercolor="#1d4ed8")
bilan_button.label.set_color("white")
bilan_button.on_clicked(toggle_bilan)

for position, (period, label) in enumerate((
    ("24h", "24 h"), ("semaine", "Semaine"), ("mois", "Mois"), ("annee", "Année"),
)):
    period_ax = plt.axes([0.30 + position * 0.105, 0.205, 0.095, 0.038])
    period_button = Button(period_ax, label, color="#2563eb" if period == bilan_period else "#64748b", hovercolor="#334155")
    period_button.label.set_color("white")
    period_button.on_clicked(lambda event, choice=period: set_bilan_period(choice))
    period_ax.set_visible(False)
    period_buttons[period] = period_button

export_ax = plt.axes([0.77, 0.145, 0.16, 0.048])
export_button = Button(export_ax, "Exporter CSV", color="#475569", hovercolor="#334155")
export_button.label.set_color("white")
export_button.on_clicked(export_history)

def layout_bottom_actions():
    """Aligne les actions selon la page, sans laisser de vide inutile."""
    if showing_bilan:
        tariffs_ax.set_position([0.18, 0.145, 0.18, 0.048])
        bilan_button_ax.set_position([0.40, 0.145, 0.22, 0.048])
        export_ax.set_position([0.66, 0.145, 0.16, 0.048])
    else:
        tariffs_ax.set_position([0.18, 0.145, 0.18, 0.048])
        bilan_button_ax.set_position([0.40, 0.145, 0.22, 0.048])
        export_ax.set_position([0.66, 0.145, 0.16, 0.048])

layout_bottom_actions()

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

    dinky_indexes = None
    dinky_index_status = "index non lu"
    linky_cfg = CONFIG.get("linky", {})
    if linky_cfg.get("enabled") and str(linky_cfg.get("mode", "")).lower() in ("dinky_http", "tasmota_http"):
        try:
            dinky_indexes, dinky_index_status = read_dinky_energy_indexes()
            if dinky_indexes is not None:
                append_linky_energy_indexes(datetime.now(), dinky_indexes)
        except Exception as exc:
            dinky_index_status = f"index Dinky indisponible ({exc})"

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
        # Le DTU répond : son rythme de mise à jour peut être lent sans être une panne.
        set_connection_badge(connection_badges[0], "online", "● DTU connecté")

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
            f"échecs lecture DTU : {dtu_failures} — {mode} — Linky : {linky_status} — {dinky_index_status}"
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
            f"échecs lecture DTU : {dtu_failures} — Linky : {linky_status} — {dinky_index_status} — {e}"
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
