#!/bin/bash
# Installation macOS Apple Silicon sans Terminal visible lorsqu'elle est lancée
# depuis « Installer Boîte noire Hoymiles.app ».
set -u

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(cd "$PACKAGE_DIR/.." && pwd)"
BASE="$HOME/Library/Application Support/BoiteNoireHoymiles"
APP_DEST="$HOME/Applications/Boîte noire Hoymiles.app"
LAUNCH_APP="$PACKAGE_DIR/Boîte noire Hoymiles.app"
PYTHON_BIN=""

dialog() {
  /usr/bin/osascript -e "display dialog \"$1\" with title \"Boîte noire Hoymiles\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null
}

choose_python() {
  for candidate in \
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3" \
    "$(command -v python3 2>/dev/null || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ] && "$candidate" -c "import tkinter" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      return 0
    fi
  done
  return 1
}

if ! choose_python; then
  dialog "Python avec Tkinter est nécessaire. Installez Python depuis python.org (version universelle macOS), puis relancez l'installation."
  exit 1
fi

if ! /usr/bin/osascript -e 'display dialog "Installer ou mettre à jour Boîte noire Hoymiles pour macOS ?\n\nLes historiques et réglages existants seront conservés." with title "Boîte noire Hoymiles" buttons {"Annuler", "Continuer"} default button "Continuer" with icon note' >/dev/null; then
  exit 0
fi

mkdir -p "$BASE" "$HOME/Applications"
CONFIG_FILE="$BASE/config_v5.json"
MODE=""

if [ -f "$CONFIG_FILE" ]; then
  if /usr/bin/osascript -e 'display dialog "Les réglages réseau existants sont conservés.\n\nVoulez-vous modifier la connexion du DTU ?" with title "Boîte noire Hoymiles" buttons {"Conserver", "Modifier"} default button "Conserver" with icon note' | /usr/bin/grep -q "Modifier"; then
    MODE="change"
  fi
else
  MODE="new"
fi

if [ -n "$MODE" ]; then
  selection=$(/usr/bin/osascript -e 'choose from list {"DTU-LAN — recommandé : câble Ethernet vers la box, DTU et Dinky 4 sur la box", "DTU-WIFI — expérimental : Wi-Fi propre du DTU, adaptateur Wi-Fi USB compatible macOS requis"} with title "Connexion du DTU" with prompt "Choisissez une seule connexion pour le DTU Pro-S." default items {"DTU-LAN — recommandé : câble Ethernet vers la box, DTU et Dinky 4 sur la box"} OK button name "Continuer" Cancel button name "Annuler"') || exit 0

  if /usr/bin/printf '%s' "$selection" | /usr/bin/grep -q "DTU-LAN"; then
    DTU_HOST=$(/usr/bin/osascript -e 'text returned of (display dialog "Adresse IP attribuée au DTU par votre box :" default answer "192.168.1.200" with title "DTU-LAN sur la box" buttons {"Annuler", "Continuer"} default button "Continuer")') || exit 0
  else
    DTU_HOST="10.10.100.254"
  fi

  if [ -z "$DTU_HOST" ]; then
    dialog "L'adresse IP du DTU est nécessaire pour le mode DTU-LAN."
    exit 1
  fi

  if [ "$MODE" = "new" ]; then
    DINKY_HOST=$(/usr/bin/osascript -e 'text returned of (display dialog "Adresse IP du Dinky 4 sur votre box :" default answer "192.168.1.126" with title "Dinky 4" buttons {"Annuler", "Continuer"} default button "Continuer")') || exit 0
    [ -n "$DINKY_HOST" ] || DINKY_HOST="192.168.1.126"
  fi

  DTU_HOST="$DTU_HOST" DINKY_HOST="${DINKY_HOST:-}" CONFIG_FILE="$CONFIG_FILE" "$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["CONFIG_FILE"])
if path.exists():
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config = {}
else:
    config = {}

config["dtu_host"] = os.environ["DTU_HOST"]
if not config:
    config = {"dtu_host": os.environ["DTU_HOST"]}
if os.environ.get("DINKY_HOST"):
    config["linky"] = {
        "enabled": True, "mode": "dinky_http", "host": os.environ["DINKY_HOST"],
        "port": 80, "timeout_s": 2, "path": "Status 8"
    }
path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
PY
fi

if [ ! -d "$BASE/venv" ]; then
  "$PYTHON_BIN" -m venv "$BASE/venv" || { dialog "Impossible de créer l'environnement Python privé."; exit 1; }
fi

"$BASE/venv/bin/python" -m pip install --upgrade pip >/dev/null 2>&1
if ! "$BASE/venv/bin/python" -m pip install -r "$SOURCE_DIR/requirements.txt" >/dev/null 2>&1; then
  dialog "L'installation des dépendances Python a échoué. Vérifiez la connexion Internet puis relancez l'installation."
  exit 1
fi

/usr/bin/ditto "$SOURCE_DIR/boite_noire_hoymiles.py" "$BASE/boite_noire_hoymiles.py"
/usr/bin/ditto "$SOURCE_DIR/fond_solaire.png" "$BASE/fond_solaire.png"
/usr/bin/ditto "$LAUNCH_APP" "$APP_DEST"
/usr/bin/xattr -dr com.apple.quarantine "$APP_DEST" >/dev/null 2>&1 || true

/usr/bin/osascript -e 'display dialog "Installation terminée.\n\nLancez « Boîte noire Hoymiles » depuis le dossier Applications." with title "Boîte noire Hoymiles" buttons {"OK"} default button "OK" with icon note' >/dev/null
