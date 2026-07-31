import csv
import json
import re
import shutil
import socket
import subprocess
import calendar
import sys
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, ttk
from bisect import bisect_left
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic, sleep
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

import matplotlib
# Le backend natif macOS de Matplotlib peut planter avec Python 3.14 lors d'un
# clic sur un bouton. TkAgg est stable sur Apple Silicon et permet les boîtes
# de dialogue Tarifs EDF.
if sys.platform == "darwin":
    matplotlib.use("TkAgg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.widgets import Button

try:
    # Le DTU-Pro-S expose les mesures détaillées par Modbus-TCP lorsqu'il est
    # raccordé à la box en Ethernet. Cette dépendance est optionnelle afin de
    # conserver le fonctionnement Wi-Fi direct des anciennes installations.
    from hoymiles_modbus.client import HoymilesModbusTCP
except ImportError:
    HoymilesModbusTCP = None

# Version stable destinée à la publication communautaire.
VERSION = "7.0.8"
DEFAULT_DTU_HOST = "10.10.100.254"
INTERVAL_MS = 60000
MAX_VISIBLE_POINTS = 300
DIRECT_WINDOW_HOURS = 4
MAX_DTU_LIMIT_PCT = 120.0
DEFAULT_DTU_LIMIT_PCT = 110.0
SAV_CONFIRMATION_REQUEST = (
    "DEMANDE AU SAV HOYMILES — Merci de confirmer la réception de ce fichier, "
    "d'indiquer le résultat de votre analyse des mesures DTU / DDSU / Linky, "
    "et de préciser toute correction, action ou réglage appliqué. "
    "Réponse demandée à : rolli.urs@free.fr"
)

# Les mesures restent locales à chaque ordinateur. Windows et macOS utilisent
# leurs emplacements standards, sans changer les noms de fichiers historiques.
if sys.platform == "darwin":
    BASE = Path.home() / "Library" / "Application Support" / "BoiteNoireHoymiles"
else:
    BASE = Path.home() / "AppData" / "Local" / "BoiteNoireHoymiles"
BASE.mkdir(parents=True, exist_ok=True)
CSV_FILE = BASE / "hoymiles_log.csv"
LINKY_INDEX_FILE = BASE / "linky_index_log.csv"
DTU_WIFI_RECOVERY_LOG = BASE / "dtu_wifi_recovery.log"
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
    # Le firmware DTU ne fournit pas une valeur powerLimit stable en lecture.
    # Ces limites sont des réglages d'affichage déclaratifs : elles ne sont
    # jamais envoyées au DTU par l'application.
    "dtu_wifi_limit_pct": DEFAULT_DTU_LIMIT_PCT,
    "dtu_lan_limit_pct": DEFAULT_DTU_LIMIT_PCT,
    "linky": {
        "enabled": True,
        "mode": "dinky_http",
        "host": "192.168.1.126",
        "port": 80,
        "timeout_s": 2,
        "path": "Status 8"
    },
    "tarifs_edf": {
        "hp_eur_kwh": 0.0,
        "hc_eur_kwh": 0.0,
        "abonnement_mensuel_eur": 0.0,
        "abonnement_journalier_eur": 0.63,
        "plages_hc": "",
        "ddsu_import_positif": True
    },
    # Désactivé par défaut : l'utilisateur peut l'activer après avoir renseigné
    # son interface et son profil Wi-Fi dédiés au DTU.
    "dtu_wifi_recovery": {
        "enabled": False,
        "interface": "",
        "profile": "",
        "after_minutes": 30,
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
        # Migration sans toucher aux réglages TCP réellement configurés :
        # l'ancien bloc vide est remplacé par le Dinky installé sur ce site.
        if saved_linky == LEGACY_EMPTY_LINKY_CONFIG:
            saved_linky = DEFAULT_CONFIG["linky"]
        cfg["linky"] = {**DEFAULT_CONFIG["linky"], **saved_linky}
        saved_tariffs = data.get("tarifs_edf", {})
        if not isinstance(saved_tariffs, dict):
            saved_tariffs = {}
        cfg["tarifs_edf"] = {**DEFAULT_CONFIG["tarifs_edf"], **saved_tariffs}
        saved_recovery = data.get("dtu_wifi_recovery", {})
        if not isinstance(saved_recovery, dict):
            saved_recovery = {}
        cfg["dtu_wifi_recovery"] = {**DEFAULT_CONFIG["dtu_wifi_recovery"], **saved_recovery}
        saved_readings = data.get("releves_edf", {})
        cfg["releves_edf"] = saved_readings if isinstance(saved_readings, dict) else {}
        # Première édition macOS : elle utilisait par erreur l'ancienne IP .162.
        # La migration ne touche qu'à ce réglage obsolète et garde les tarifs,
        # historiques et autres paramètres saisis sur le Mac.
        if sys.platform == "darwin" and str(cfg.get("dtu_host", "")).strip() == "10.10.100.162":
            cfg["dtu_host"] = DEFAULT_DTU_HOST
        return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()

CONFIG = load_config()
HOST = str(CONFIG.get("dtu_host", DEFAULT_DTU_HOST)).strip() or DEFAULT_DTU_HOST

# Bleu ciel pour la production PV : distinct du bleu foncé utilisé pour les HP EDF.
PV_COLOR = "#0ea5e9"

def save_config():
    CONFIG_FILE.write_text(json.dumps(CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")

times, ac_power, grid_power, power_limit = [], [], [], []
linky_power = []
linky_hc_index, linky_hp_index = [], []
follow_now = True
last_success = None
dtu_failures = 0
dtu_failure_since = None
last_dtu_wifi_recovery = None

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

    # Les anciennes versions pouvaient enregistrer une limite firmware
    # aberrante (par exemple 500 %). On conserve le CSV brut comme preuve,
    # mais l'affichage retrouve la dernière limite réaliste.
    previous_limit = DEFAULT_DTU_LIMIT_PCT
    for t in sorted(merged):
        ac, grid, limit_w, lky = merged[t]
        if 0 <= limit_w <= MAX_DTU_LIMIT_PCT:
            previous_limit = limit_w
        else:
            limit_w = previous_limit
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
fig.patch.set_facecolor("#f4f7fb")

def dialog_parent():
    """Retourne la fenêtre Tk sous Windows, ou None pour les boîtes macOS."""
    try:
        window = getattr(plt.get_current_fig_manager(), "window", None)
        return window if hasattr(window, "tk") else None
    except Exception:
        return None

try:
    # Même symbole dans la barre de titre, la barre des tâches et le raccourci Windows.
    manager = plt.get_current_fig_manager()
    if APP_ICON.exists():
        try:
            manager.window.iconbitmap(default=str(APP_ICON))
        except Exception:
            # macOS utilise l'icône de l'application / du lanceur, pas un .ico.
            pass
    # Barre Matplotlib destinée au développement (zoom, pan, sauvegarde) :
    # le logiciel possède ses propres commandes, elle ne doit pas encombrer l'interface.
    toolbar = getattr(manager, "toolbar", None)
    if toolbar is not None:
        toolbar.pack_forget()
        manager._hoymiles_toolbar_hidden = True
except Exception:
    pass
try:
    background_ax = fig.add_axes([0, 0, 1, 1], zorder=-10)
    background_ax.imshow(plt.imread(BACKGROUND_IMAGE), aspect="auto", alpha=0.25)
    background_ax.set_axis_off()
except Exception:
    pass
plt.subplots_adjust(left=0.08, bottom=0.34, right=0.91, top=0.75)

line_ac, = ax.plot([], [], linewidth=2.15, color=PV_COLOR, label="Production PV")
line_grid, = ax.plot([], [], linewidth=1.45, color="#dc2626", label="Réseau DDSU")
line_linky, = ax.plot([], [], linewidth=1.40, color="#93c5fd", linestyle="--", label="Linky Dinky")
limit_ax = ax.twinx()
line_limit, = limit_ax.plot([], [], linewidth=1.40, color="#2563eb", label="Limite DTU")
# Légende permanente, hors du graphique, comme sur la page Bilan.
main_chart_legend = ax.legend(
    [line_limit, line_ac, line_grid, line_linky],
    ["Limite DTU (%)", "Production PV", "Réseau DDSU", "Linky Dinky"],
    loc="upper left", bbox_to_anchor=(0.08, 0.866), bbox_transform=fig.transFigure,
    ncol=2, frameon=False, borderaxespad=0.0, fontsize=9, handlelength=2.6,
)

ax.set_xlabel("Date / heure")
ax.set_ylabel("Puissance (W)")
ax.set_ylim(-500, 2200)
ax.set_facecolor((1, 1, 1, 0.47))
ax.axhline(0, linewidth=0.65, color="#94a3b8")
ax.grid(True, color="#cbd5e1", linewidth=0.45, alpha=0.85)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M"))
limit_ax.set_ylim(0, 120)
limit_ax.set_ylabel("Limite DTU (%)", color="#2563eb")
limit_ax.tick_params(axis="y", colors="#2563eb")
limit_ax.spines["top"].set_visible(False)
limit_ax.spines["left"].set_visible(False)

status_text = fig.text(0.08, 0.028, "Connexion au DTU...", ha="left", va="bottom", fontsize=8.3, color="#475569")
# Les cartes de tête ont été retirées visuellement ; les objets sont conservés pour l'animation Matplotlib.
live_cards = [fig.text(0, 0, "", visible=False) for _ in range(4)]

# En-tête du suivi direct : il disparaît sur le bilan, qui possède son propre titre.
dashboard_title = fig.text(0.08, 0.890, f"Boîte noire Hoymiles — v{VERSION}", ha="left", va="center",
                           fontsize=16, fontweight="bold", color="#0f172a")
dashboard_subtitle = fig.text(0.08, 0.790, "Suivi de production · DTU Pro-S + Linky Dinky 4",
                               ha="left", va="center", fontsize=9, color="#475569")

footer_style = dict(boxstyle="round,pad=0.50", facecolor="#ffffff", edgecolor="#dbe3ef", alpha=0.92)
end_labels = [
    fig.text(0.08, 0.95, "Limite DTU —", ha="left", va="center", fontsize=10, color="#173f8a",
             bbox={**footer_style, "edgecolor": "#93c5fd"}),
    fig.text(0.29, 0.95, "Production PV —", ha="left", va="center", fontsize=10, color="#173f8a",
             bbox={**footer_style, "edgecolor": "#93c5fd"}),
    fig.text(0.50, 0.95, "Réseau DDSU —", ha="left", va="center", fontsize=10, color="#173f8a",
             bbox={**footer_style, "edgecolor": "#93c5fd"}),
    fig.text(0.71, 0.95, "Linky Dinky —", ha="left", va="center", fontsize=10, color="#173f8a",
             bbox={**footer_style, "edgecolor": "#93c5fd"}),
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
                    color=PV_COLOR, markeredgecolor="white", markeredgewidth=1.2,
                    visible=False, zorder=101)
fig.add_artist(cursor_line)
fig.add_artist(cursor_dot)
cursor_box = fig.text(
    0, 0, "", transform=fig.transFigure, fontsize=9, ha="left", va="top", visible=False,
    bbox=dict(boxstyle="round,pad=0.45", facecolor="#ffffff", edgecolor="#0f172a", alpha=0.62), zorder=102,
)
bilan_cursor_data = {"labels": [], "production": [], "hc": [], "hp": [], "subscription": []}
comparison_cursor_data = {"labels": [], "production": [], "ddsu": [], "linky": []}
bilan_cursor_box = fig.text(
    0, 0, "", transform=fig.transFigure, fontsize=9, ha="left", va="top", visible=False,
    bbox=dict(boxstyle="round,pad=0.45", facecolor="#ffffff", edgecolor="#0f172a", alpha=0.76), zorder=103,
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
        f"Production PV  {production:.0f} W\n"
        f"Réseau DTU  {grid:+.0f} W\n"
        f"Limite DTU  {limit:.0f} %\n"
        f"Linky       {linky_text}"
    )
    cursor_box.set_visible(True)
    fig.canvas.draw_idle()


def move_cursor(event):
    """Affiche les mesures de la date la plus proche du curseur de la souris."""
    if showing_bilan:
        if showing_comparison:
            move_comparison_cursor(event.x, event.y)
        else:
            move_bilan_cursor(event.x, event.y)
        return
    if not times or event.x is None or event.y is None:
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

    # Un DTU sur le LAN ne présente pas le service Wi-Fi direct (port 10081) :
    # il expose à la place Modbus-TCP sur le port 502. L'interroger d'abord
    # évite trois délais de 12 secondes inutiles à chaque cycle de lecture.
    if not str(HOST).startswith("10.10.100.") and HoymilesModbusTCP is not None:
        try:
            plant = HoymilesModbusTCP(HOST, port=502, unit_id=1).plant_data
            return {
                "_source": "modbus_tcp",
                "_modbus_pv_w": float(plant.pv_power),
                "sgsData": [{"activePower": int(round(float(plant.pv_power) * 10)), "powerLimit": 0}],
                "meterData": [{"phaseTotalPower": 0}],
            }
        except Exception as exc:
            modbus_error = f"Modbus TCP {HOST}: {exc}"
    else:
        modbus_error = ""

    hosts = []
    for host in (HOST, "10.10.100.162", "10.10.100.254"):
        if host and host not in hosts:
            hosts.append(host)

    # Sous macOS l'application est lancée depuis un environnement Python privé.
    # Le programme hoymiles-wifi est donc dans le même dossier que Python, et
    # n'est pas forcément visible dans le PATH général du Mac.
    executable_dir = Path(sys.executable).resolve().parent
    cli_candidates = (executable_dir / "hoymiles-wifi", executable_dir / "hoymiles-wifi.exe")
    hoymiles_cli = next((str(candidate) for candidate in cli_candidates if candidate.exists()), "hoymiles-wifi")

    errors = []
    for host in hosts:
        cmd = [hoymiles_cli, "--host", host, "--as-json", "get-real-data-new"]
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
    if modbus_error:
        errors.insert(0, modbus_error)
    raise RuntimeError(" | ".join(errors))

def reconnect_dtu_wifi():
    """Reconnecte uniquement l'adaptateur Wi-Fi réservé au DTU sous Windows."""
    cfg = CONFIG.get("dtu_wifi_recovery", {})
    if sys.platform != "win32" or not cfg.get("enabled"):
        return "reconnexion Wi-Fi DTU désactivée"
    interface = str(cfg.get("interface", "")).strip()
    profile = str(cfg.get("profile", "")).strip()
    if not interface or not profile:
        return "reconnexion Wi-Fi DTU non configurée"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        # Cette commande ne cible que « Wi-Fi 4 » : le Wi-Fi Livebox/Dinky
        # reste connecté pendant toute l'opération.
        subprocess.run(
            ["netsh", "wlan", "disconnect", f"interface={interface}"],
            capture_output=True, text=True, timeout=12, creationflags=creationflags,
        )
        sleep(2)
        result = subprocess.run(
            ["netsh", "wlan", "connect", f"name={profile}", f"interface={interface}"],
            capture_output=True, text=True, timeout=15, creationflags=creationflags,
        )
        detail = (result.stdout or result.stderr or "commande envoyée").strip().replace("\n", " ")
        if result.returncode != 0:
            raise RuntimeError(detail)
        return f"TP-Link reconnecté au profil {profile} ({detail[:90]})"
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return f"reconnexion TP-Link impossible : {exc}"

def record_dtu_wifi_recovery(message):
    try:
        with DTU_WIFI_RECOVERY_LOG.open("a", encoding="utf-8") as log:
            log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}; {message}\n")
    except OSError:
        pass

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

def read_dinky_history_uncached(period, labels):
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
                # Le Dinky retourne déjà les sept barres dans l'ordre du temps.
                # On les aligne sur la même fenêtre glissante que la production PV.
                index = tick_index
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


# Les pages de bilan et de comparaison peuvent demander plusieurs fois le même
# historique au Dinky pendant un redessin. Ce cache évite des requêtes HTTP
# identiques et rend les boutons immédiatement réactifs, sans changer les données.
DINKY_HISTORY_CACHE_TTL_S = 90
dinky_history_cache = {}


def read_dinky_history(period, labels):
    key = (period, tuple(labels))
    cached = dinky_history_cache.get(key)
    now_tick = monotonic()
    if cached is not None and now_tick - cached[0] < DINKY_HISTORY_CACHE_TTL_S:
        hc, hp = cached[1]
        return list(hc), list(hp)
    result = read_dinky_history_uncached(period, labels)
    if result is None:
        return None
    hc, hp = result
    dinky_history_cache[key] = (now_tick, (list(hc), list(hp)))
    return list(hc), list(hp)

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

def visible_plot_indexes():
    """Limite le nombre de points dessinés, sans supprimer une mesure de l'historique."""
    count = len(times)
    if not count:
        return []
    view = globals().get("history_view", "direct")
    end = times[-1]
    if view == "direct":
        start_index = bisect_left(times, end - timedelta(hours=DIRECT_WINDOW_HOURS))
    elif view == "24h":
        start_index = bisect_left(times, end - timedelta(hours=24))
    elif view == "hier":
        yesterday_end = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start_index = bisect_left(times, yesterday_end - timedelta(days=1))
        count = bisect_left(times, yesterday_end)
    else:
        start_index = 0
    indexes = list(range(start_index, count))
    if len(indexes) <= MAX_VISIBLE_POINTS:
        return indexes
    stride = max(1, (len(indexes) - 1) // (MAX_VISIBLE_POINTS - 1))
    indexes = indexes[::stride]
    if indexes[-1] != count - 1:
        indexes.append(count - 1)
    return indexes


def redraw():
    indexes = visible_plot_indexes()
    plotted_times = [times[index] for index in indexes]
    line_ac.set_data(plotted_times, [ac_power[index] for index in indexes])
    line_grid.set_data(plotted_times, [grid_power[index] for index in indexes])
    line_limit.set_data(plotted_times, [power_limit[index] for index in indexes])
    line_linky.set_data(plotted_times, [linky_power[index] for index in indexes])
    if times and not showing_bilan:
        show_cursor(len(times) - 1)
    if showing_bilan:
        if showing_comparison:
            draw_hoymiles_comparison()
        else:
            draw_bilan()

def update_end_labels():
    """Affiche les valeurs à droite en évitant le chevauchement."""
    if not times:
        return
    linky = linky_power[-1]
    linky_txt = "—" if linky != linky else f"{linky:.0f} W"
    end_labels[0].set_text(f"Limite DTU  {power_limit[-1]:.0f} %")
    end_labels[1].set_text(f"Production PV  {ac_power[-1]:.0f} W")
    end_labels[2].set_text(f"Réseau DDSU  {grid_power[-1]:+.0f} W")
    end_labels[3].set_text(f"Linky Dinky  {linky_txt}")
    return

    series = [
        (ac_power, "Production PV"),
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

def choose_export_date_range():
    """Propose les jours réellement présents dans l'historique."""
    available_dates = sorted({when.strftime("%Y-%m-%d") for when in times})
    if not available_dates:
        raise RuntimeError("aucune date disponible dans l'historique")

    parent = dialog_parent()
    if parent is None:
        start = simpledialog.askstring("Période d'export", "Date de début (AAAA-MM-JJ) :")
        end = simpledialog.askstring("Période d'export", "Date de fin (AAAA-MM-JJ) :")
        return (start, end) if start and end else None

    result = {"range": None}
    dialog = tk.Toplevel(parent)
    dialog.title("Période de l'export historique")
    dialog.resizable(False, False)
    dialog.transient(parent)
    tk.Label(dialog, text="Date de début :").grid(row=0, column=0, padx=14, pady=(14, 7), sticky="w")
    tk.Label(dialog, text="Date de fin :").grid(row=1, column=0, padx=14, pady=7, sticky="w")
    start_value = tk.StringVar(value=available_dates[0])
    end_value = tk.StringVar(value=available_dates[-1])
    start_box = ttk.Combobox(dialog, textvariable=start_value, values=available_dates, state="readonly", width=15)
    end_box = ttk.Combobox(dialog, textvariable=end_value, values=available_dates, state="readonly", width=15)
    start_box.grid(row=0, column=1, padx=(0, 14), pady=(14, 7))
    end_box.grid(row=1, column=1, padx=(0, 14), pady=7)

    def confirm():
        if start_value.get() > end_value.get():
            messagebox.showwarning("Période invalide", "La date de début doit précéder la date de fin.", parent=dialog)
            return
        result["range"] = (start_value.get(), end_value.get())
        dialog.destroy()

    buttons = tk.Frame(dialog)
    buttons.grid(row=2, column=0, columnspan=2, pady=(9, 14))
    tk.Button(buttons, text="Exporter", width=12, command=confirm).pack(side="left", padx=5)
    tk.Button(buttons, text="Annuler", width=12, command=dialog.destroy).pack(side="left", padx=5)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    start_box.focus_set()
    dialog.grab_set()
    dialog.wait_window()
    return result["range"]


def export_history(event=None):
    """Exporte uniquement la période choisie de l'historique."""
    try:
        if not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0:
            raise RuntimeError("aucun historique à exporter")

        selected_period = choose_export_date_range()
        if selected_period is None:
            status_text.set_text("Export annulé")
            fig.canvas.draw_idle()
            return
        start_date, end_date = selected_period
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise RuntimeError("dates attendues au format AAAA-MM-JJ")
        if start_date > end_date:
            raise RuntimeError("la date de début doit précéder la date de fin")
        default_name = f"hoymiles_historique_{start_date.replace('-', '')}_au_{end_date.replace('-', '')}.csv"
        desktop = Path.home() / "Desktop"
        initial_dir = desktop if desktop.exists() else BASE / "Exports"
        parent = dialog_parent()
        selected_dir = filedialog.askdirectory(
            parent=parent,
            title="Choisir le dossier d'export de l'historique",
            initialdir=str(initial_dir),
        )
        if not selected_dir:
            status_text.set_text("Export annulé")
            fig.canvas.draw_idle()
            return
        export_dir = Path(selected_dir)
        destination = export_dir / default_name
        # Le journal interne utilise la virgule (format Python standard). Pour
        # LibreOffice / Excel en français, l'export public utilise le point-
        # virgule et un BOM UTF-8 : les cinq colonnes s'ouvrent alors seules.
        with CSV_FILE.open("r", newline="", encoding="utf-8") as source, \
                destination.open("w", newline="", encoding="utf-8-sig") as target:
            reader = csv.DictReader(source)
            fields = ["date", "heure", "production_ac_w", "reseau_ddsu_w", "consigne_w", "consommation_edf_w"]
            writer = csv.DictWriter(target, fieldnames=fields, delimiter=";")
            writer.writeheader()
            exported_count = 0
            for row in reader:
                date_heure = row.get("date_heure", "").split(" ", 1)
                row_date = date_heure[0] if date_heure else ""
                if not start_date <= row_date <= end_date:
                    continue
                writer.writerow({
                    "date": row_date,
                    "heure": date_heure[1] if len(date_heure) > 1 else "",
                    "production_ac_w": row.get("production_ac_w", ""),
                    "reseau_ddsu_w": row.get("reseau_ddsu_w", ""),
                    "consigne_w": row.get("consigne_w", ""),
                    "consommation_edf_w": row.get("linky_w", ""),
                })
                exported_count += 1
        # Le CSV conserve volontairement ses colonnes de mesures, afin qu'il
        # reste directement importable dans Excel et LibreOffice. La demande
        # SAV est fournie dans un fichier compagnon daté, dans le même dossier.
        sav_note = export_dir / f"{destination.stem}_demande_sav_hoymiles.txt"
        sav_note.write_text(
            "DEMANDE D'ANALYSE — BOÎTE NOIRE HOYMILES\n\n"
            + SAV_CONFIRMATION_REQUEST + "\n\n"
            + f"Période exportée : {start_date} au {end_date}\n"
            + f"Nombre de mesures : {exported_count}\n"
            + f"Export généré le : {datetime.now():%d/%m/%Y %H:%M:%S}\n"
            + f"Version du logiciel : {VERSION}\n",
            encoding="utf-8",
        )
        status_text.set_text(f"Export {start_date} au {end_date} : {exported_count} mesures")
        messagebox.showinfo(
            "Export terminé",
            f"Historique exporté du {start_date} au {end_date}.\n"
            f"{exported_count} mesure(s) exportée(s).\n"
            f"Demande SAV jointe : {sav_note.name}\n\n{destination}",
            parent=parent,
        )
    except Exception as e:
        status_text.set_text(f"Export impossible — {e}")
    fig.canvas.draw_idle()

def capture_screen(event=None):
    """Enregistre la page affichée avec un repère de date et de version."""
    captured_at = datetime.now()
    filename = f"hoymiles_capture_{captured_at.strftime('%Y-%m-%d_%H-%M-%S')}.png"
    initial_dir = Path.home() / "Pictures"
    if not initial_dir.exists():
        initial_dir = BASE
    destination = filedialog.asksaveasfilename(
        title="Enregistrer la capture Hoymiles",
        initialdir=str(initial_dir),
        initialfile=filename,
        defaultextension=".png",
        filetypes=[("Image PNG", "*.png")],
        parent=dialog_parent(),
    )
    if not destination:
        return
    stamp = fig.text(
        0.985, 0.008,
        f"Capture : {captured_at.strftime('%d/%m/%Y %H:%M:%S')}  |  Boîte noire Hoymiles v{VERSION}",
        ha="right", va="bottom", fontsize=8.2, color="#0f172a",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#94a3b8", "alpha": 0.88},
        zorder=100,
    )
    try:
        fig.savefig(destination, dpi=160, facecolor=fig.get_facecolor())
        messagebox.showinfo(
            "Capture enregistrée",
            f"Image prête à envoyer à Hoymiles :\n{destination}",
            parent=dialog_parent(),
        )
    except Exception as exc:
        messagebox.showerror("Capture impossible", str(exc), parent=dialog_parent())
    finally:
        stamp.remove()
        fig.canvas.draw_idle()


def hoymiles_cli_path():
    """Retourne le client local Hoymiles, sous Windows comme sous macOS."""
    executable_dir = Path(sys.executable).resolve().parent
    candidates = (executable_dir / "hoymiles-wifi", executable_dir / "hoymiles-wifi.exe")
    return next((str(candidate) for candidate in candidates if candidate.exists()), "hoymiles-wifi")


def summarize_dtu_links(payload):
    """Résume les liaisons observables sans inventer de qualité de signal."""
    lines = ["", "ÉTAT DES LIAISONS OBSERVABLES"]
    meter_data = payload.get("meterData")
    if isinstance(meter_data, list) and meter_data and isinstance(meter_data[0], dict):
        meter = meter_data[0]
        grid = meter.get("phaseTotalPower", meter.get("phaseAPower"))
        lines.append("DDSU ↔ DTU : réponse compteur reçue")
        if grid is None:
            lines.append("Puissance réseau DDSU : champ absent dans la réponse")
        else:
            lines.append(f"Puissance réseau mesurée par le DDSU : {grid} W")
        lines.append("Qualité DDSU ↔ DTU : le DTU ne publie ni RSSI ni taux d'erreur RS485 ; seule la présence de la réponse est vérifiable.")
    else:
        lines.append("DDSU ↔ DTU : aucune réponse meterData reçue — liaison ou compteur à vérifier.")

    sgs_data = payload.get("sgsData")
    pv_data = payload.get("pvData")
    if isinstance(sgs_data, list) and sgs_data:
        lines.append(f"DTU ↔ micro-onduleurs : réponse passerelle reçue ({len(sgs_data)} groupe(s) de données).")
        warnings = [entry.get("warningNumber") for entry in sgs_data if isinstance(entry, dict) and entry.get("warningNumber") not in (None, 0)]
        if warnings:
            lines.append("Avertissement(s) DTU brut(s) : " + ", ".join(str(value) for value in warnings))
    else:
        lines.append("DTU ↔ micro-onduleurs : aucune donnée passerelle reçue.")

    if isinstance(pv_data, list) and pv_data:
        lines.append(f"Micro-onduleurs / entrées PV répondants : {len(pv_data)}")
        error_codes = []
        for entry in pv_data:
            if not isinstance(entry, dict):
                continue
            code = entry.get("errorCode")
            if code not in (None, 0):
                port = entry.get("portNumber", "?")
                error_codes.append(f"port {port} : code {code}")
        if error_codes:
            lines.append("Codes bruts remontés par les micro-onduleurs : " + " ; ".join(error_codes))
        else:
            lines.append("Codes bruts remontés par les micro-onduleurs : aucun code non nul.")
    else:
        lines.append("Micro-onduleurs / entrées PV : données non publiées par le DTU.")
    lines.append("Qualité DTU ↔ micro-onduleurs : le DTU ne fournit pas de niveau radio exploitable ; ce rapport indique uniquement les réponses, avertissements et codes publiés.")
    return lines


def summarize_local_observations():
    """Ajoute au rapport les seules observations locales vérifiables.

    Cette synthèse n'interprète pas la régulation : elle donne au SAV le
    dernier point connu et la cadence d'acquisition, utiles pour recouper
    une anomalie avec l'historique CSV.
    """
    lines = ["", "SYNTHÈSE DES MESURES LOCALES (lecture de l'application)"]
    if not times:
        return lines + ["Aucune mesure locale enregistrée pendant cette session."]

    index = len(times) - 1
    last_time = times[index]
    pv = ac_power[index] if index < len(ac_power) else float("nan")
    ddsu = grid_power[index] if index < len(grid_power) else float("nan")
    linky = linky_power[index] if index < len(linky_power) else float("nan")
    lines.append(f"Dernière mesure locale : {last_time:%d/%m/%Y %H:%M:%S}")
    lines.append(f"Production PV publiée par le DTU : {pv:.1f} W")
    lines.append(f"Puissance réseau DDSU publiée par le DTU : {ddsu:+.1f} W")
    if linky == linky:  # NaN n'est jamais égal à lui-même.
        lines.append(f"Puissance Linky/Dinky indépendante : {linky:+.1f} W")
        lines.append(f"Écart instantané DDSU ↔ Linky : {ddsu - linky:+.1f} W")
    else:
        lines.append("Puissance Linky/Dinky indépendante : indisponible pour ce point.")

    recent_count = min(len(times), 20)
    recent_times = times[-recent_count:]
    if recent_count >= 2:
        elapsed = (recent_times[-1] - recent_times[0]).total_seconds()
        average_period = elapsed / (recent_count - 1)
        lines.append(
            f"Cadence locale récente : {recent_count} mesures sur {elapsed:.0f} s "
            f"(moyenne {average_period:.1f} s entre deux mesures)."
        )
    lines.append(
        "Note : l'écart DDSU ↔ Linky est un constat de mesure ; il ne permet pas, "
        "à lui seul, d'identifier l'origine du défaut."
    )
    return lines


def collect_dtu_diagnostic():
    """Collecte uniquement des réponses de lecture, sans écrire dans le DTU."""
    startupinfo = None
    creationflags = 0
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    collected_at = datetime.now()
    lines = [
        "RAPPORT DIAGNOSTIC DTU — LECTURE SEULE",
        "À transmettre au SAV Hoymiles avec les captures d'écran et l'historique CSV.",
        SAV_CONFIRMATION_REQUEST,
        "Aucun réglage, aucune limite de puissance et aucun redémarrage ne sont envoyés par cette fonction.",
        "",
        f"Date / heure : {collected_at:%d/%m/%Y %H:%M:%S}",
        f"Version Boîte noire Hoymiles : {VERSION}",
        f"Hôte DTU interrogé : {HOST}",
        f"Dernière réponse DTU : {last_success:%d/%m/%Y %H:%M:%S}" if last_success else "Dernière réponse DTU : aucune pendant cette session",
        f"Échecs de lecture cumulés depuis le lancement : {dtu_failures}",
        "",
        "PARAMÈTRES LOCAUX D'AFFICHAGE (non envoyés au DTU)",
        f"Référence limite Wi-Fi : {CONFIG.get('dtu_wifi_limit_pct', DEFAULT_DTU_LIMIT_PCT)} %",
        f"Référence limite LAN : {CONFIG.get('dtu_lan_limit_pct', DEFAULT_DTU_LIMIT_PCT)} %",
        "",
    ]
    lines.extend(summarize_local_observations())
    lines.extend(("", "RÉPONSES BRUTES DU DTU"))

    # Ces commandes commencent toutes par « get » : elles lisent les données
    # publiées par le DTU et n'appellent jamais les commandes set/restart.
    commands = (
        "get-real-data-new",
        "get-version-info",
        "get-information-data",
        "get-alarm-list",
        "get-config",
    )
    cli = hoymiles_cli_path()
    for command in commands:
        lines.extend(("", f"--- {command} (lecture seule) ---"))
        cmd = [cli, "--host", HOST, "--as-json", "--disable-interactive", "--timeout", "5", command]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=8,
                startupinfo=startupinfo, creationflags=creationflags,
            )
            raw = (result.stdout or result.stderr or "Aucune réponse").strip()
            try:
                parsed = json.loads(raw)
                if command == "get-real-data-new" and isinstance(parsed, dict):
                    lines.extend(summarize_dtu_links(parsed))
                lines.append(json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True))
            except (json.JSONDecodeError, TypeError):
                lines.append(raw)
        except Exception as exc:
            lines.append(f"Erreur de lecture : {exc}")
    return "\n".join(lines) + "\n"


def open_dtu_diagnostic(event=None):
    """Ouvre la page de diagnostic et permet son export pour le SAV Hoymiles."""
    parent = dialog_parent()
    if parent is None:
        messagebox.showwarning("Diagnostic DTU", "La fenêtre de diagnostic n'est pas disponible.")
        return

    dialog = tk.Toplevel(parent)
    dialog.title("Diagnostic DTU — SAV Hoymiles")
    dialog.geometry("820x620")
    dialog.minsize(680, 460)
    dialog.transient(parent)

    header = tk.Label(
        dialog,
        text="Diagnostic DTU — lecture seule\nRapport destiné au SAV Hoymiles : aucune commande de réglage n'est envoyée.",
        justify="left", anchor="w", padx=14, pady=12,
        fg="#0f3b68", font=("Arial", 10, "bold"),
    )
    header.pack(fill="x")
    text_area = tk.Text(dialog, wrap="word", font=("Consolas", 9), padx=12, pady=10)
    text_area.pack(fill="both", expand=True, padx=14, pady=(0, 10))
    footer = tk.Frame(dialog)
    footer.pack(fill="x", padx=14, pady=(0, 14))
    report = {"text": ""}

    def refresh():
        text_area.config(state="normal")
        text_area.delete("1.0", "end")
        text_area.insert("end", "Lecture des informations DTU en cours…\n")
        text_area.config(state="disabled")
        dialog.update_idletasks()
        report["text"] = collect_dtu_diagnostic()
        text_area.config(state="normal")
        text_area.delete("1.0", "end")
        text_area.insert("end", report["text"])
        text_area.config(state="disabled")

    def save_report():
        if not report["text"]:
            return
        filename = f"diagnostic_dtu_sav_hoymiles_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt"
        destination = filedialog.asksaveasfilename(
            title="Enregistrer le rapport diagnostic pour le SAV Hoymiles",
            initialdir=str(Path.home() / "Desktop"), initialfile=filename,
            defaultextension=".txt", filetypes=[("Rapport texte", "*.txt")], parent=dialog,
        )
        if not destination:
            return
        Path(destination).write_text(report["text"], encoding="utf-8")
        messagebox.showinfo(
            "Rapport enregistré",
            f"Rapport prêt à joindre au SAV Hoymiles :\n{destination}", parent=dialog,
        )

    tk.Button(footer, text="Actualiser (lecture seule)", width=25, command=refresh).pack(side="left")
    tk.Button(footer, text="Enregistrer rapport SAV", width=25, command=save_report).pack(side="left", padx=8)
    tk.Button(footer, text="Fermer", width=12, command=dialog.destroy).pack(side="right")
    refresh()

showing_bilan = False
showing_comparison = False
bilan_period = "24h"
edf_cost_details = {"message": "Aucun bilan EDF n'est encore disponible."}
comparison_details = {"message": "Aucune comparaison n'est encore disponible."}
bilan_ax = fig.add_axes([0.08, 0.34, 0.83, 0.46])
bilan_ax.set_visible(False)
bilan_cost_ax = bilan_ax.twinx()
bilan_cost_ax.set_visible(False)
comparison_ax = fig.add_axes([0.08, 0.34, 0.83, 0.46])
comparison_ax.set_visible(False)

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

FRENCH_WEEKDAYS = ("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim")


def rolling_week_window(now):
    """Les sept derniers jours, y compris aujourd'hui, dans l'ordre réel."""
    start = datetime.combine(now.date() - timedelta(days=6), datetime.min.time())
    labels = [
        f"{FRENCH_WEEKDAYS[(start.date() + timedelta(days=offset)).weekday()]} "
        f"{(start.date() + timedelta(days=offset)).day}"
        for offset in range(7)
    ]
    return start, labels


def automatic_energy_series(period, now):
    """Produit les kWh PV et EDF par créneau à partir des mesures enregistrées."""
    if period == "24h":
        start = datetime.combine(now.date(), datetime.min.time())
        labels = [f"{hour:02d} h" for hour in range(24)]
        index_for = lambda when: when.hour
        title = "Bilan automatique — dernières 24 h"
    elif period == "semaine":
        start, labels = rolling_week_window(now)
        index_for = lambda when: (when.date() - start.date()).days
        title = "Bilan automatique — 7 derniers jours"
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

def hoymiles_ddsu_energy_series(period, now):
    """Énergie estimée uniquement avec les données locales DTU + DDSU.

    Cette série n'appelle jamais le Dinky et ne contient donc aucune mesure
    Linky. Le signe du DDSU utilise le réglage déjà présent dans Tarifs EDF.
    """
    if period == "24h":
        start = datetime.combine(now.date(), datetime.min.time())
        labels = [f"{hour:02d} h" for hour in range(24)]
        index_for = lambda when: when.hour
    elif period == "semaine":
        start, labels = rolling_week_window(now)
        index_for = lambda when: (when.date() - start.date()).days
    elif period == "mois":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        labels = [str(day) for day in range(1, calendar.monthrange(now.year, now.month)[1] + 1)]
        index_for = lambda when: when.day - 1
    else:
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
        index_for = lambda when: when.month - 1

    production = [0.0] * len(labels)
    ddsu_import = [0.0] * len(labels)
    ddsu_hc = [0.0] * len(labels)
    ddsu_hp = [0.0] * len(labels)
    direction = 1 if CONFIG["tarifs_edf"].get("ddsu_import_positif", True) else -1
    ranges = parse_hc_ranges(CONFIG["tarifs_edf"].get("plages_hc", ""))
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
            imported = max(0.0, direction * float(grid_power[index])) * factor
            ddsu_import[bucket] += imported
            if is_hc(when, ranges):
                ddsu_hc[bucket] += imported
            else:
                ddsu_hp[bucket] += imported
        except (IndexError, TypeError, ValueError):
            continue
    return labels, production, ddsu_import, ddsu_hc, ddsu_hp, start

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

def automatic_month_subscription(now, daily_subscription):
    """Calcule l'abonnement écoulé depuis le 1er, sans le figer dans un relevé."""
    if daily_subscription <= 0:
        return 0.0
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # EDF met habituellement à jour ses données avec les journées terminées.
    completed_days = max(0, (now.date() - month_start.date()).days)
    return completed_days * daily_subscription

def latest_dinky_indexes():
    """Retourne le dernier index connu, sans imposer une nouvelle lecture réseau."""
    if linky_hc_index and linky_hp_index:
        return {"hc": float(linky_hc_index[-1][1]), "hp": float(linky_hp_index[-1][1])}
    return None

def real_edf_month_totals(now):
    """Total EDF vérifié, complété uniquement par les index après la saisie.

    Le relevé EDF couvre déjà tout ce qui précède sa date de saisie. Les kWh
    enregistrés auparavant par le logiciel ne sont donc jamais ajoutés une
    seconde fois. Après le relevé, les nouveaux index Dinky prolongent le total.
    """
    month = now.strftime("%Y-%m")
    reading = CONFIG.get("releves_edf", {}).get(month, {})
    try:
        hc = max(0.0, float(reading["hc_kwh"]))
        hp = max(0.0, float(reading["hp_kwh"]))
        saved_subscription = max(0.0, float(reading["abonnement_eur"]))
    except (KeyError, TypeError, ValueError):
        return None

    tariffs = CONFIG.get("tarifs_edf", {})
    try:
        daily_subscription = max(0.0, float(tariffs.get("abonnement_journalier_eur", 0.0) or 0.0))
    except (TypeError, ValueError):
        daily_subscription = 0.0
    # Dès qu'un tarif journalier est renseigné, l'abonnement évolue tout seul.
    # L'ancienne valeur manuelle reste un secours pour les anciens relevés.
    subscription = automatic_month_subscription(now, daily_subscription) if daily_subscription > 0 else saved_subscription

    current = latest_dinky_indexes()
    try:
        base_hc = float(reading["dinky_hc_index"])
        base_hp = float(reading["dinky_hp_index"])
        if current is not None:
            hc += max(0.0, current["hc"] - base_hc)
            hp += max(0.0, current["hp"] - base_hp)
    except (KeyError, TypeError, ValueError):
        pass
    return hc, hp, subscription, reading.get("saisi_le", "")

def replace_total(values, total, fallback_index):
    """Conserve la forme des barres lorsque possible, mais rend le total exact."""
    previous = sum(values)
    if previous > 0:
        factor = total / previous
        return [value * factor for value in values]
    result = [0.0] * len(values)
    if result:
        result[max(0, min(fallback_index, len(result) - 1))] = total
    return result

def draw_bilan():
    if not showing_bilan:
        return
    now = datetime.now()
    labels, production, achat_edf, hc, hp, title, dinky_source, start = automatic_energy_series(bilan_period, now)
    tariffs = CONFIG["tarifs_edf"]
    hp_price = float(tariffs.get("hp_eur_kwh", 0.0) or 0.0)
    hc_price = float(tariffs.get("hc_eur_kwh", 0.0) or 0.0)
    daily_subscription = float(tariffs.get("abonnement_journalier_eur", tariffs.get("abonnement_mensuel_eur", 0.0)) or 0.0)
    real_reading = real_edf_month_totals(now)
    real_note = ""
    if real_reading is not None and bilan_period in ("mois", "annee"):
        real_hc, real_hp, real_subscription, entered_at = real_reading
        current_bucket = now.day - 1 if bilan_period == "mois" else now.month - 1
        if bilan_period == "annee":
            # Dans l'année, seule la colonne du mois en cours est remplacée.
            hc[current_bucket] = real_hc
            hp[current_bucket] = real_hp
        # Dans le mois, un relevé EDF est un total cumulatif. Il ne doit pas
        # être placé artificiellement dans la barre du jour de saisie.
        # Les barres journalières restent donc les seules mesures détaillées
        # réellement reçues du Dinky depuis le démarrage du logiciel.
        achat_edf = [hc_value + hp_value for hc_value, hp_value in zip(hc, hp)]
        real_note = f" — relevé EDF réel {entered_at}" if entered_at else " — relevé EDF réel"
    hp_cost = [value * hp_price for value in hp]
    hc_cost = [value * hc_price for value in hc]
    subscription = subscription_series(bilan_period, start, now, len(labels), daily_subscription)
    if real_reading is not None and bilan_period in ("mois", "annee"):
        if bilan_period == "mois":
            subscription = replace_total(subscription, real_reading[2], now.day - 1)
        else:
            subscription[now.month - 1] = real_reading[2]
    bilan_ax.clear()
    bilan_cost_ax.clear()
    bilan_cost_ax.set_visible(True)
    bilan_ax.set_facecolor((1, 1, 1, 0.48))
    bilan_cost_ax.set_facecolor((1, 1, 1, 0.0))
    positions = list(range(len(labels)))
    pv_positions = [position - 0.20 for position in positions]
    edf_positions = [position + 0.20 for position in positions]
    edf_bar_width = 0.38
    bilan_ax.bar(pv_positions, production, width=edf_bar_width, color=PV_COLOR, label="Production PV")
    bilan_cost_ax.bar(
        edf_positions, subscription, width=edf_bar_width, align="center",
        facecolor="#eff6ff", edgecolor="#1d4ed8", linewidth=1.10, label="Abonnement EDF",
    )
    bilan_cost_ax.bar(
        edf_positions, hp_cost, width=edf_bar_width, align="center", bottom=subscription,
        facecolor="#1d4ed8", edgecolor="#1d4ed8", linewidth=1.10, label="Achat Linky/Dinky HP",
    )
    hp_and_subscription = [fixed + hp_value for fixed, hp_value in zip(subscription, hp_cost)]
    bilan_cost_ax.bar(
        edf_positions, hc_cost, width=edf_bar_width, align="center", bottom=hp_and_subscription,
        facecolor="#ffffff", edgecolor="#1d4ed8", linewidth=1.10, hatch="///",
        label="Achat Linky/Dinky HC",
    )
    # Un seul contour extérieur, ajouté après les trois segments : les bords
    # Abonnement / HP / HC restent ainsi strictement sur le même alignement.
    edf_total_cost = [fixed + hp_value + hc_value for fixed, hp_value, hc_value in zip(subscription, hp_cost, hc_cost)]
    bilan_cost_ax.bar(
        edf_positions, edf_total_cost, width=edf_bar_width, align="center",
        facecolor="none", edgecolor="#1d4ed8", linewidth=1.10, label="_nolegend_",
    )
    bilan_ax.set_xticks(positions)
    bilan_ax.set_xticklabels(labels, rotation=0 if len(labels) <= 12 else 60, ha="right" if len(labels) > 12 else "center")
    bilan_ax.set_ylabel("Énergie (kWh)")
    bilan_ax.grid(axis="y", color="#cbd5e1", linewidth=0.45)
    bilan_ax.set_axisbelow(True)
    bilan_ax.spines["top"].set_visible(False)
    bilan_ax.spines["right"].set_visible(False)
    bilan_cost_ax.set_ylabel("Coût EDF (€)", color="#334155")
    # Axe dédié aux euros : il reste toujours à droite, même après un
    # changement de période ou un rafraîchissement du bilan.
    bilan_cost_ax.yaxis.set_label_position("right")
    bilan_cost_ax.yaxis.tick_right()
    bilan_cost_ax.tick_params(axis="y", colors="#334155")
    bilan_cost_ax.spines["top"].set_visible(False)
    bilan_cost_ax.spines["left"].set_visible(False)
    bilan_cost_ax.spines["right"].set_visible(True)
    left_handles, left_labels = bilan_ax.get_legend_handles_labels()
    right_handles, right_labels = bilan_cost_ax.get_legend_handles_labels()
    bilan_ax.legend(
        left_handles + right_handles, left_labels + right_labels,
        loc="lower left", bbox_to_anchor=(0.0, 1.01), frameon=False, ncol=2,
        borderaxespad=0.0, fontsize=9,
    )
    # Le titre est volontairement plus haut que la légende à deux lignes.
    bilan_ax.set_title(f"{title} — v{VERSION}", loc="left", fontsize=14, pad=52)
    total_pv = sum(production)
    chart_hc_total = sum(hc)
    chart_hp_total = sum(hp)
    total_edf = chart_hc_total + chart_hp_total
    subscription_cost = sum(subscription)
    estimated_cost = sum(hp_cost) + sum(hc_cost) + subscription_cost
    if real_reading is not None and bilan_period in ("mois", "annee"):
        # Le relevé manuel est la référence pour les totaux et le coût affichés.
        total_edf = real_reading[0] + real_reading[1]
        subscription_cost = real_reading[2]
        estimated_cost = real_reading[0] * hc_price + real_reading[1] * hp_price + subscription_cost
    tariff_note = "Tarifs à renseigner" if not (tariffs.get("hp_eur_kwh") or tariffs.get("hc_eur_kwh")) else \
        f"HP {hp_price:.4f} €/kWh  |  HC {hc_price:.4f} €/kWh  |  Abo {daily_subscription:.2f} €/jour"
    manual_reading = CONFIG.get("releves_edf", {}).get(now.strftime("%Y-%m"), {})
    manual_details = ""
    try:
        manual_hc = real_reading[0] if real_reading is not None else float(manual_reading["hc_kwh"])
        manual_hp = real_reading[1] if real_reading is not None else float(manual_reading["hp_kwh"])
        manual_subscription = real_reading[2] if real_reading is not None else float(manual_reading["abonnement_eur"])
        manual_energy_cost = manual_hc * hc_price + manual_hp * hp_price
        manual_final_cost = manual_energy_cost + manual_subscription
        manual_details = (
            f"\n\nRelevé EDF manuel — {now:%m/%Y}\n"
            f"• HC : {manual_hc:.2f} kWh\n"
            f"• HP : {manual_hp:.2f} kWh\n"
            f"• Coût énergie HC + HP : {manual_energy_cost:.2f} €\n"
            f"• Abonnement : {manual_subscription:.2f} €\n\n"
            f"TOTAL EDF réel depuis le 1er (abonnement inclus) : {manual_final_cost:.2f} €\n"
            "Ce relevé est utilisé pour le bilan Mois et Année."
        )
    except (KeyError, TypeError, ValueError):
        manual_details = "\n\nAucun relevé EDF manuel enregistré pour ce mois."
    edf_cost_details["message"] = (
        f"{title}\n\n"
        f"Achat Linky : {total_edf:.2f} kWh\n"
        f"• Heures creuses : {(real_reading[0] if real_reading is not None and bilan_period in ('mois', 'annee') else chart_hc_total):.2f} kWh\n"
        f"• Heures pleines : {(real_reading[1] if real_reading is not None and bilan_period in ('mois', 'annee') else chart_hp_total):.2f} kWh\n"
        f"• Abonnement : {subscription_cost:.2f} €\n\n"
        f"Coût EDF : {estimated_cost:.2f} €\n\n"
        f"Source : {dinky_source}{real_note}\n{tariff_note}{manual_details}"
    )
    bilan_cursor_data.update({
        "labels": labels,
        "production": production,
        "hc": hc,
        "hp": hp,
        "subscription": subscription,
    })

def move_bilan_cursor(x, y):
    """Affiche les valeurs réelles d'une colonne du bilan au survol."""
    if not showing_bilan or showing_comparison or x is None or y is None or not bilan_ax.bbox.contains(x, y):
        bilan_cursor_box.set_visible(False)
        fig.canvas.draw_idle()
        return
    labels = bilan_cursor_data["labels"]
    if not labels:
        return
    xdata = bilan_ax.transData.inverted().transform((x, y))[0]
    index = int(round(xdata))
    if not 0 <= index < len(labels):
        bilan_cursor_box.set_visible(False)
        fig.canvas.draw_idle()
        return
    xfig, _ = fig.transFigure.inverted().transform((x, y))
    if xfig > 0.65:
        bilan_cursor_box.set_ha("right")
        bilan_cursor_box.set_position((xfig - 0.012, 0.785))
    else:
        bilan_cursor_box.set_ha("left")
        bilan_cursor_box.set_position((xfig + 0.012, 0.785))
    bilan_cursor_box.set_text(
        f"{labels[index]}\n"
        f"Production PV  {bilan_cursor_data['production'][index]:.2f} kWh\n"
        f"Linky HC    {bilan_cursor_data['hc'][index]:.2f} kWh\n"
        f"Linky HP    {bilan_cursor_data['hp'][index]:.2f} kWh\n"
        f"Abonnement  {bilan_cursor_data['subscription'][index]:.2f} €"
    )
    bilan_cursor_box.set_visible(True)
    fig.canvas.draw_idle()

def show_real_edf_cost(event=None):
    """Affiche le détail du coût sans surcharger la zone du graphique."""
    messagebox.showinfo("Coût EDF réel", edf_cost_details["message"], parent=dialog_parent())

def draw_hoymiles_comparison():
    """Affiche côte à côte l'estimation DTU/DDSU et la mesure Linky/Dinky."""
    if not showing_bilan or not showing_comparison:
        return
    now = datetime.now()
    labels, production, ddsu_import, ddsu_hc, ddsu_hp, start = hoymiles_ddsu_energy_series(bilan_period, now)
    # Cette seule série utilise le Dinky : elle est volontairement séparée de
    # l'estimation Hoymiles afin de rendre l'écart contrôlable visuellement.
    _, _, linky_import, linky_hc, linky_hp, _, linky_source, _ = automatic_energy_series(bilan_period, now)
    real_reading = real_edf_month_totals(now)
    real_linky_hc = sum(linky_hc)
    real_linky_hp = sum(linky_hp)
    real_note = ""
    if real_reading is not None and bilan_period in ("mois", "annee"):
        real_hc, real_hp, _, _ = real_reading
        current_bucket = now.day - 1 if bilan_period == "mois" else now.month - 1
        real_linky_hc, real_linky_hp = real_hc, real_hp
        if bilan_period == "annee":
            linky_hc[current_bucket] = real_hc
            linky_hp[current_bucket] = real_hp
        else:
            real_note = " — relevé mensuel cumulé, non réparti artificiellement par jour"
        linky_import = [hc_value + hp_value for hc_value, hp_value in zip(linky_hc, linky_hp)]
    comparison_ax.clear()
    comparison_ax.set_facecolor((1, 1, 1, 0.40))
    positions = list(range(len(labels)))
    comparison_ax.bar([pos - 0.25 for pos in positions], production, width=0.22,
        color=PV_COLOR, label="Production PV")
    comparison_ax.bar(positions, ddsu_import, width=0.22,
        color="#60a5fa", label="Estimation achat DDSU")
    comparison_ax.bar([pos + 0.25 for pos in positions], linky_import, width=0.22,
        color="#93c5fd", label="Achat réel Linky/Dinky")
    comparison_ax.set_xticks(positions)
    comparison_ax.set_xticklabels(labels, rotation=0 if len(labels) <= 12 else 60,
                                  ha="right" if len(labels) > 12 else "center")
    comparison_ax.set_ylabel("Énergie (kWh)")
    comparison_ax.grid(axis="y", color="#dbe3ef", linewidth=0.7)
    comparison_ax.set_axisbelow(True)
    comparison_ax.spines["top"].set_visible(False)
    comparison_ax.spines["right"].set_visible(False)
    comparison_ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), frameon=False, ncol=3,
                         borderaxespad=0.0, fontsize=9)
    comparison_ax.set_title(f"Comparatif énergie — Hoymiles / Linky — v{VERSION}", loc="left", fontsize=14, pad=52)
    total_ddsu = sum(ddsu_import)
    total_linky = real_linky_hc + real_linky_hp if real_reading is not None and bilan_period in ("mois", "annee") else sum(linky_import)
    difference = total_ddsu - total_linky
    relative_error = abs(difference) / total_linky * 100 if total_linky > 0 else float("nan")
    tariffs = CONFIG["tarifs_edf"]
    hp_price = float(tariffs.get("hp_eur_kwh", 0.0) or 0.0)
    hc_price = float(tariffs.get("hc_eur_kwh", 0.0) or 0.0)
    daily_subscription = float(tariffs.get("abonnement_journalier_eur", tariffs.get("abonnement_mensuel_eur", 0.0)) or 0.0)
    subscription = subscription_series(bilan_period, start, now, len(labels), daily_subscription)
    if real_reading is not None and bilan_period in ("mois", "annee"):
        if bilan_period == "mois":
            subscription = replace_total(subscription, real_reading[2], now.day - 1)
        else:
            subscription[now.month - 1] = real_reading[2]
    subscription_total = sum(subscription)
    ddsu_cost = sum(ddsu_hp) * hp_price + sum(ddsu_hc) * hc_price + subscription_total
    linky_cost = real_linky_hp * hp_price + real_linky_hc * hc_price + subscription_total
    direction = 1 if tariffs.get("ddsu_import_positif", True) else -1
    instant_ddsu = max(0.0, direction * float(grid_power[-1])) if grid_power else float("nan")
    instant_linky = float(linky_power[-1]) if linky_power and linky_power[-1] == linky_power[-1] else float("nan")
    if instant_ddsu == instant_ddsu and instant_linky == instant_linky:
        instant_line = f"Écart instantané DDSU ↔ Linky : {instant_ddsu - instant_linky:+.0f} W"
    else:
        instant_line = "Écart instantané DDSU ↔ Linky : en attente"
    relative_line = f"Erreur relative ........... {relative_error:.1f} %" if relative_error == relative_error else \
                    "Erreur relative ........... —"
    comparison_details["message"] = (
        f"Période comparée : {start:%d/%m/%Y %H:%M} → {now:%d/%m/%Y %H:%M}\n"
        f"Version logiciel : {VERSION}\n\n"
        f"{instant_line}\n\n"
        f"Production PV (mesure DTU) ........ {sum(production):.2f} kWh\n"
        f"Consommation DDSU (estimation) .... {total_ddsu:.2f} kWh\n"
        f"Consommation Linky/Dinky (index) .. {total_linky:.2f} kWh\n\n"
        f"Écart ..................... {difference:+.2f} kWh\n"
        f"{relative_line}\n\n"
        f"Coût estimé DDSU .......... {ddsu_cost:.2f} €\n"
        f"Coût réel Linky ........... {linky_cost:.2f} €\n"
        f"(abonnement inclus : {subscription_total:.2f} €)\n"
        f"Source réelle : {linky_source}{real_note}\n"
        "Les totaux DTU et Linky sont deux mesures indépendantes."
    )
    comparison_cursor_data.update({
        "labels": labels,
        "production": production,
        "ddsu": ddsu_import,
        "linky": linky_import,
    })

def move_comparison_cursor(x, y):
    """Affiche les trois valeurs d'énergie de la période survolée."""
    if not showing_bilan or not showing_comparison or x is None or y is None or not comparison_ax.bbox.contains(x, y):
        bilan_cursor_box.set_visible(False)
        fig.canvas.draw_idle()
        return
    labels = comparison_cursor_data["labels"]
    if not labels:
        return
    xdata = comparison_ax.transData.inverted().transform((x, y))[0]
    index = int(round(xdata))
    if not 0 <= index < len(labels):
        bilan_cursor_box.set_visible(False)
        fig.canvas.draw_idle()
        return
    xfig, _ = fig.transFigure.inverted().transform((x, y))
    if xfig > 0.65:
        bilan_cursor_box.set_ha("right")
        bilan_cursor_box.set_position((xfig - 0.012, 0.785))
    else:
        bilan_cursor_box.set_ha("left")
        bilan_cursor_box.set_position((xfig + 0.012, 0.785))
    bilan_cursor_box.set_text(
        f"{labels[index]}\n"
        f"Production PV    {comparison_cursor_data['production'][index]:.2f} kWh\n"
        f"DDSU estimé      {comparison_cursor_data['ddsu'][index]:.2f} kWh\n"
        f"Linky/Dinky réel {comparison_cursor_data['linky'][index]:.2f} kWh"
    )
    bilan_cursor_box.set_visible(True)
    fig.canvas.draw_idle()

def show_comparison_details(event=None):
    """Montre le tableau chiffré sans masquer les barres du comparatif."""
    messagebox.showinfo("Détail comparaison", comparison_details["message"], parent=dialog_parent())

def toggle_hoymiles_comparison(event=None):
    """Bascule entre le bilan EDF réel et le comparatif indépendant Hoymiles."""
    global showing_comparison
    if not showing_bilan:
        return
    showing_comparison = not showing_comparison
    bilan_ax.set_visible(not showing_comparison)
    bilan_cost_ax.set_visible(not showing_comparison)
    comparison_ax.set_visible(showing_comparison)
    bilan_cursor_box.set_visible(False)
    edf_reading_button.ax.set_visible(not showing_comparison)
    edf_cost_button.ax.set_visible(not showing_comparison)
    comparison_details_button.ax.set_visible(showing_comparison)
    if showing_comparison:
        edf_cost_ax.set_position([0.001, 0.001, 0.001, 0.001])
        comparison_details_ax.set_position([0.75, 0.815, 0.16, 0.042])
    else:
        edf_cost_ax.set_position([0.75, 0.815, 0.16, 0.042])
        comparison_details_ax.set_position([0.001, 0.001, 0.001, 0.001])
    comparison_button.label.set_text("Retour bilan EDF" if showing_comparison else "Estimation Hoymiles")
    if showing_comparison:
        draw_hoymiles_comparison()
    else:
        draw_bilan()
    fig.canvas.draw()

def open_tariffs(event=None):
    tariffs = CONFIG["tarifs_edf"]
    try:
        parent = dialog_parent()
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
        messagebox.showerror("Tarifs EDF", str(exc), parent=dialog_parent())

def open_real_edf_reading(event=None):
    """Enregistre un cumul EDF mensuel et le point de départ Dinky associé."""
    try:
        parent = dialog_parent()
        default_month = datetime.now().strftime("%Y-%m")
        month = simpledialog.askstring(
            "Relevé EDF réel", "Mois du relevé (AAAA-MM) :\nLe cumul commence le 1er jour du mois.",
            initialvalue=default_month, parent=parent
        )
        if month is None:
            return
        month = month.strip()
        datetime.strptime(month + "-01", "%Y-%m-%d")
        previous = CONFIG.setdefault("releves_edf", {}).get(month, {})
        hc = simpledialog.askstring(
            "Relevé EDF réel", "Consommation HC cumulée depuis le 1er du mois (kWh) :",
            initialvalue=str(previous.get("hc_kwh", "")), parent=parent
        )
        if hc is None:
            return
        hp = simpledialog.askstring(
            "Relevé EDF réel", "Consommation HP cumulée depuis le 1er du mois (kWh) :",
            initialvalue=str(previous.get("hp_kwh", "")), parent=parent
        )
        if hp is None:
            return
        indexes, _ = read_dinky_energy_indexes()
        if indexes is None:
            indexes = latest_dinky_indexes() or {}
        try:
            daily_subscription = max(0.0, float(CONFIG.get("tarifs_edf", {}).get("abonnement_journalier_eur", 0.0) or 0.0))
        except (TypeError, ValueError):
            daily_subscription = 0.0
        automatic_subscription = automatic_month_subscription(datetime.now(), daily_subscription)
        CONFIG["releves_edf"][month] = {
            "hc_kwh": float_from_user(hc, "HC EDF réel"),
            "hp_kwh": float_from_user(hp, "HP EDF réel"),
            # Conservé pour compatibilité ; le tarif journalier calcule désormais
            # automatiquement le montant courant du mois.
            "abonnement_eur": float(previous.get("abonnement_eur", 0.0) or 0.0),
            "dinky_hc_index": float(indexes["hc"]) if "hc" in indexes else None,
            "dinky_hp_index": float(indexes["hp"]) if "hp" in indexes else None,
            "saisi_le": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        save_config()
        if showing_bilan:
            draw_bilan()
        fig.canvas.draw_idle()
        messagebox.showinfo(
            "Relevé EDF enregistré",
            f"Relevé {month} enregistré.\n\nHC : {float_from_user(hc, 'HC'):.2f} kWh\n"
            f"HP : {float_from_user(hp, 'HP'):.2f} kWh\n"
            f"Abonnement automatique à ce jour : {automatic_subscription:.2f} €\n\n"
            "Les prochains kWh lus par le Dinky seront ajoutés sans double compte.",
            parent=parent,
        )
    except Exception as exc:
        messagebox.showerror("Relevé EDF réel", str(exc), parent=dialog_parent())

def style_final_button(button, active=False):
    """Conserve les boutons rectangulaires d'origine, avec texte noir lisible."""
    fill = "#bfdbfe" if active else "#eff6ff"
    button.ax.patch.set_visible(True)
    button.ax.patch.set_edgecolor("#1d4ed8")
    button.ax.patch.set_linewidth(0.85)
    button.ax.set_facecolor(fill)
    button.color = fill
    button.hovercolor = "#dbeafe"
    button._final_active = active
    button.label.set_color("#111827")
    button.label.set_fontsize(9.5)


def set_final_button_state(button, active):
    """Met à jour les boutons actifs tout en gardant leur forme rectangulaire."""
    fill = "#bfdbfe" if active else "#eff6ff"
    button.ax.set_facecolor(fill)
    button.color = fill
    button.hovercolor = "#dbeafe"
    button._final_active = active
    button.label.set_color("#111827")


period_buttons = {}
period_caption = fig.text(0.20, 0.285, "Période du bilan", ha="left", va="center", fontsize=9,
                          color="#334155", visible=False,
                          bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dbe3ef", alpha=0.72))

history_buttons = {}
history_view = "direct"
history_caption = fig.text(0.17, 0.225, "Affichage production", ha="left", va="center", fontsize=9,
                           color="#334155", visible=False,
                           bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#dbe3ef", alpha=0.72))

def apply_history_view():
    """Cadre le graphique production sur la période demandée."""
    if not times:
        return
    # La dernière mesure est la référence. Le délai d'une minute entre deux
    # lectures ne doit pas empêcher le retour immédiat au suivi direct.
    end = max(times[-1], datetime.now())
    if history_view == "direct":
        start = end - timedelta(hours=DIRECT_WINDOW_HOURS)
    elif history_view == "24h":
        start = end - timedelta(hours=24)
    elif history_view == "hier":
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
    else:
        start = times[0]
    if start == end:
        end = start + timedelta(minutes=1)
    # Désactive explicitement l'ajustement automatique : sinon Matplotlib peut
    # réafficher tout l'historique après la mise à jour des courbes.
    ax.set_autoscalex_on(False)
    ax.set_xlim(mdates.date2num(start), mdates.date2num(end), auto=False)

def refresh_history_buttons():
    history_caption.set_visible(not showing_bilan)
    for view, button in history_buttons.items():
        button.ax.set_visible(not showing_bilan)
        set_final_button_state(button, view == history_view)

def set_history_view(view):
    global history_view, follow_now
    history_view = view
    follow_now = view == "direct"
    refresh_history_buttons()
    redraw()
    apply_history_view()
    # draw() est volontairement immédiat : le changement de période doit être
    # visible au clic, sans attendre le cycle de lecture du DTU.
    fig.canvas.draw()

def refresh_period_buttons():
    period_caption.set_visible(showing_bilan)
    for period, button in period_buttons.items():
        button.ax.set_visible(showing_bilan)
        set_final_button_state(button, period == bilan_period)

def set_bilan_period(period):
    global bilan_period
    bilan_period = period
    refresh_period_buttons()
    if showing_comparison:
        draw_hoymiles_comparison()
    else:
        draw_bilan()
    fig.canvas.draw_idle()

def toggle_bilan(event=None):
    global showing_bilan, showing_comparison
    showing_bilan = not showing_bilan
    if not showing_bilan:
        showing_comparison = False
    ax.set_visible(not showing_bilan)
    limit_ax.set_visible(not showing_bilan)
    bilan_ax.set_visible(showing_bilan and not showing_comparison)
    bilan_cost_ax.set_visible(showing_bilan and not showing_comparison)
    comparison_ax.set_visible(showing_bilan and showing_comparison)
    dashboard_title.set_visible(not showing_bilan)
    dashboard_subtitle.set_visible(not showing_bilan)
    main_chart_legend.set_visible(not showing_bilan)
    cursor_line.set_visible(False)
    cursor_dot.set_visible(False)
    cursor_box.set_visible(False)
    bilan_cursor_box.set_visible(False)
    bilan_button.label.set_text("Suivi production" if showing_bilan else "Bilan consommation")
    layout_bottom_actions()
    refresh_period_buttons()
    refresh_history_buttons()
    edf_reading_button.ax.set_visible(showing_bilan)
    edf_cost_button.ax.set_visible(showing_bilan)
    comparison_button.ax.set_visible(showing_bilan)
    comparison_details_button.ax.set_visible(False)
    comparison_button.label.set_text("Estimation Hoymiles")
    if showing_bilan:
        draw_hoymiles_comparison() if showing_comparison else draw_bilan()
    fig.canvas.draw_idle()

tariffs_ax = plt.axes([0.31, 0.145, 0.18, 0.048])
tariffs_button = Button(tariffs_ax, "Tarifs EDF", color="#64748b", hovercolor="#475569")
tariffs_button.label.set_color("white")
tariffs_button.on_clicked(open_tariffs)

edf_reading_ax = plt.axes([0.08, 0.145, 0.20, 0.048])
edf_reading_button = Button(edf_reading_ax, "Ajout manuel relevé EDF", color="#0f766e", hovercolor="#115e59")
edf_reading_button.label.set_color("white")
edf_reading_button.on_clicked(open_real_edf_reading)
edf_reading_ax.set_visible(False)

edf_cost_ax = plt.axes([0.75, 0.815, 0.16, 0.042], zorder=25)
edf_cost_button = Button(edf_cost_ax, "Coût EDF réel", color="#0f766e", hovercolor="#115e59")
edf_cost_button.label.set_color("white")
edf_cost_button.on_clicked(show_real_edf_cost)
edf_cost_ax.set_visible(False)

comparison_details_ax = plt.axes([0.75, 0.815, 0.16, 0.042], zorder=25)
comparison_details_button = Button(comparison_details_ax, "Détail comparaison", color="#0f766e", hovercolor="#115e59")
comparison_details_button.label.set_color("white")
comparison_details_button.on_clicked(show_comparison_details)
comparison_details_ax.set_visible(False)

comparison_ax_button = plt.axes([0.57, 0.815, 0.16, 0.042], zorder=25)
comparison_button = Button(comparison_ax_button, "Estimation Hoymiles", color="#c2410c", hovercolor="#9a3412")
comparison_button.label.set_color("white")
comparison_button.on_clicked(toggle_hoymiles_comparison)
comparison_ax_button.set_visible(False)

# Le diagnostic reste volontairement au même endroit sur toutes les pages :
# il ouvre un rapport technique de lecture seule pour le SAV Hoymiles.
# Les actions restent groupées, sous les cartes de statut : elles ne masquent
# ni le titre ni l'infobulle du curseur quand la fenêtre est réduite.
diagnostic_ax = plt.axes([0.61, 0.845, 0.15, 0.042], zorder=30)
diagnostic_button = Button(diagnostic_ax, "Diagnostic DTU", color="#334155", hovercolor="#0f172a")
diagnostic_button.label.set_color("white")
diagnostic_button.on_clicked(open_dtu_diagnostic)

# Même position sur toutes les pages : facilite les captures destinées au support Hoymiles.
capture_ax = plt.axes([0.79, 0.845, 0.12, 0.042], zorder=30)
capture_button = Button(capture_ax, "Capture écran", color="#334155", hovercolor="#0f172a")
capture_button.label.set_color("white")
capture_button.on_clicked(capture_screen)

bilan_button_ax = plt.axes([0.52, 0.145, 0.22, 0.048])
bilan_button = Button(bilan_button_ax, "Bilan consommation", color="#0ea5e9", hovercolor="#0284c7")
bilan_button.label.set_color("white")
bilan_button.on_clicked(toggle_bilan)

for position, (period, label) in enumerate((
    ("24h", "24 h"), ("semaine", "Semaine"), ("mois", "Mois"), ("annee", "Année"),
)):
    # Cette rangée est distincte de celle du suivi production. Même cachés,
    # les axes Matplotlib reçoivent les clics ; ils ne doivent donc jamais se
    # superposer.
    period_ax = plt.axes([0.30 + position * 0.105, 0.255, 0.095, 0.038], zorder=5)
    period_button = Button(period_ax, label, color="#0ea5e9" if period == bilan_period else "#64748b", hovercolor="#334155")
    period_button.label.set_color("white")
    period_button.on_clicked(lambda event, choice=period: set_bilan_period(choice))
    period_ax.set_visible(False)
    period_buttons[period] = period_button

for view, label, x, width in (
    ("direct", "Direct", 0.28, 0.10),
    ("24h", "24 h", 0.40, 0.10),
    ("hier", "Hier", 0.52, 0.10),
    ("historique", "Historique", 0.64, 0.15),
):
    history_ax = plt.axes([x, 0.205, width, 0.038], zorder=20)
    history_button = Button(history_ax, label, color="#0ea5e9" if view == history_view else "#64748b", hovercolor="#334155")
    history_button.label.set_color("white")
    history_button.on_clicked(lambda event, choice=view: set_history_view(choice))
    history_ax.set_visible(True)
    history_buttons[view] = history_button

export_ax = plt.axes([0.77, 0.145, 0.16, 0.048])
export_button = Button(export_ax, "Exporter CSV", color="#475569", hovercolor="#334155")
export_button.label.set_color("white")
export_button.on_clicked(export_history)

# Version finale : les actions gardent exactement les mêmes fonctions,
# avec une surface visuelle cohérente.
style_final_button(tariffs_button)
style_final_button(edf_reading_button)
style_final_button(edf_cost_button)
style_final_button(comparison_details_button)
style_final_button(comparison_button)
style_final_button(diagnostic_button)
style_final_button(capture_button)
style_final_button(bilan_button, active=True)
style_final_button(export_button)
for period, button in period_buttons.items():
    style_final_button(button, active=period == bilan_period)
for view, button in history_buttons.items():
    style_final_button(button, active=view == history_view)

def layout_bottom_actions():
    """Aligne les actions selon la page, sans laisser de vide inutile."""
    if showing_bilan:
        comparison_ax_button.set_position([0.57, 0.815, 0.16, 0.042])
        if showing_comparison:
            edf_cost_ax.set_position([0.001, 0.001, 0.001, 0.001])
            comparison_details_ax.set_position([0.75, 0.815, 0.16, 0.042])
        else:
            edf_cost_ax.set_position([0.75, 0.815, 0.16, 0.042])
            comparison_details_ax.set_position([0.001, 0.001, 0.001, 0.001])
        edf_reading_ax.set_position([0.08, 0.145, 0.20, 0.048])
        tariffs_ax.set_position([0.31, 0.145, 0.18, 0.048])
        bilan_button_ax.set_position([0.52, 0.145, 0.22, 0.048])
        export_ax.set_position([0.77, 0.145, 0.16, 0.048])
    else:
        # Un axe masqué peut tout de même capter les clics Matplotlib : on le
        # retire physiquement du graphique de production.
        edf_cost_ax.set_position([0.001, 0.001, 0.001, 0.001])
        comparison_ax_button.set_position([0.001, 0.001, 0.001, 0.001])
        comparison_details_ax.set_position([0.001, 0.001, 0.001, 0.001])
        tariffs_ax.set_position([0.18, 0.145, 0.18, 0.048])
        bilan_button_ax.set_position([0.40, 0.145, 0.22, 0.048])
        export_ax.set_position([0.66, 0.145, 0.16, 0.048])

layout_bottom_actions()
refresh_history_buttons()

def update(_):
    global last_success, dtu_failures, dtu_failure_since, last_dtu_wifi_recovery
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
        dtu_failure_since = None
        dtu_delay = monotonic() - dtu_started
        set_connection_badge(
            connection_badges[0], "delayed" if dtu_delay > 3 else "online",
            "● DTU délai important" if dtu_delay > 3 else "● DTU connecté",
        )
        # Le DTU répond : son rythme de mise à jour peut être lent sans être une panne.
        set_connection_badge(connection_badges[0], "online", "● DTU connecté")

        source = data.get("_source", "wifi_direct")
        sgs = data["sgsData"][0]
        meter = data["meterData"][0]
        # Selon le firmware, la puissance de production est soit à la racine
        # (dtuPower / activePower), soit dans sgsData. Les champs à zéro sont
        # omis par le DTU dans son JSON : la nuit, leur absence signifie donc 0 W.
        ac_raw = data.get("_modbus_pv_w", data.get("dtuPower", data.get("activePower", sgs.get("activePower", 0))))
        if source == "modbus_tcp":
            ac_raw = float(ac_raw) * 10
        ac = float(ac_raw) / 10
        # Certains firmwares ne renvoient temporairement que la valeur de phase.
        # Les deux champs représentent la même mesure sur cette installation monophasée.
        grid_raw = meter.get("phaseTotalPower", meter.get("phaseAPower"))
        if grid_raw is None:
            raise RuntimeError("puissance réseau absente de la réponse DTU")
        if source == "modbus_tcp":
            grid = float("nan")
            limit_w = float(CONFIG.get("dtu_lan_limit_pct", DEFAULT_DTU_LIMIT_PCT))
        else:
            grid = float(grid_raw)
            # Le champ Wi-Fi ``powerLimit`` fluctue suivant le firmware DTU
            # et peut même reprendre une puissance PV (500 %, 800 %, etc.).
            # Il ne s'agit pas d'une commande envoyée par ce programme. On
            # affiche donc la limite explicitement configurée dans S-Miles,
            # 110 % par défaut, comme le faisait la version macOS 7.0.4.
            limit_w = float(CONFIG.get("dtu_wifi_limit_pct", DEFAULT_DTU_LIMIT_PCT))
        if not 0 <= limit_w <= MAX_DTU_LIMIT_PCT:
            limit_w = DEFAULT_DTU_LIMIT_PCT
        limit_note = ""
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

        if follow_now:
            apply_history_view()

        if lky is None:
            linky_card_txt = "LINKY DINKY\nEN ATTENTE"
        else:
            linky_card_txt = f"LINKY DINKY\n{lky:.0f} W (TIC)"
        live_cards[0].set_text(f"PRODUCTION PV\n{ac:.0f} W")
        live_cards[1].set_text(
            f"RÉSEAU DDSU\n{grid:+.0f} W" if source != "modbus_tcp" else "RÉSEAU DDSU\nN/D (Modbus)"
        )
        live_cards[2].set_text(
            f"LIMITE DTU\n{limit_w:.0f} %" if source != "modbus_tcp" else "LIMITE DTU\nN/D (Modbus)"
        )
        live_cards[3].set_text(linky_card_txt)

        mode = "suivi direct" if follow_now else "historique"
        status_text.set_text(
            f"Dernière mise à jour : {now:%d/%m/%Y %H:%M:%S} — DTU {HOST} connecté ({'Modbus TCP' if source == 'modbus_tcp' else 'Wi-Fi direct'}) — réponse : 0 s — échecs DTU : {dtu_failures}\n"
            f"Historique : {len(times)} mesures / {len(LOADED_HISTORY_FILES)} fichier(s) — {mode} — Linky : {linky_status} — {dinky_index_status}{limit_note}"
        )
    except Exception as e:
        dtu_failures += 1
        set_connection_badge(connection_badges[0], "offline", "● DTU hors ligne")
        failed_at = datetime.now()
        if dtu_failure_since is None:
            dtu_failure_since = failed_at
        recovery_note = ""
        recovery_cfg = CONFIG.get("dtu_wifi_recovery", {})
        try:
            delay_minutes = max(1, int(recovery_cfg.get("after_minutes", 30) or 30))
        except (TypeError, ValueError):
            delay_minutes = 30
        failure_seconds = (failed_at - dtu_failure_since).total_seconds()
        cooldown_elapsed = last_dtu_wifi_recovery is None or \
            (failed_at - last_dtu_wifi_recovery).total_seconds() >= delay_minutes * 60
        if failure_seconds >= delay_minutes * 60 and cooldown_elapsed:
            last_dtu_wifi_recovery = failed_at
            recovery_note = reconnect_dtu_wifi()
            record_dtu_wifi_recovery(
                f"DTU sans réponse depuis {int(failure_seconds)} s — {recovery_note}"
            )
        age = "jamais"
        if last_success is not None:
            age = f"{int((datetime.now() - last_success).total_seconds())} s"
        last_update = last_success.strftime("%d/%m/%Y %H:%M:%S") if last_success else "jamais"
        status_text.set_text(
            f"Dernière mise à jour : {last_update} — DTU sans réponse depuis {age} — échecs DTU : {dtu_failures}\n"
            f"Linky : {linky_status} — {dinky_index_status} — erreur DTU : {str(e)[:110]}"
            + (f" — {recovery_note}" if recovery_note else "")
        )

    return (
        line_ac, line_grid, line_limit, line_linky, cursor_line, cursor_dot, cursor_box,
        *live_cards, status_text, *end_labels, *connection_badges,
    )

redraw()
update_end_labels()
if times:
    apply_history_view()
else:
    # Évite l'axe Matplotlib 31/12 -> 01/01 quand l'historique est neuf.
    now0 = datetime.now()
    ax.set_xlim(now0, now0.replace(second=0, microsecond=0) + __import__("datetime").timedelta(hours=2))
    fig.autofmt_xdate()

# Premier relevé avant d'ouvrir la fenêtre. Sur macOS/Tk, les minuteurs de
# démarrage peuvent être ignorés tant que la fenêtre n'a pas été activée ; un
# relevé Modbus prend ici quelques secondes mais garantit l'affichage direct
# des données dès l'ouverture.
update(None)

# Puis une lecture chaque minute.
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
            toolbar_height = 0 if getattr(manager, "_hoymiles_toolbar_hidden", False) else (toolbar.winfo_height() if toolbar is not None else 0)
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
            if showing_bilan:
                if showing_comparison:
                    move_comparison_cursor(x, y)
                else:
                    move_bilan_cursor(x, y)
                return
            if not times or not ax.bbox.contains(x, y):
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
