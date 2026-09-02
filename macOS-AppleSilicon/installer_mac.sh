#!/bin/bash
# Installation macOS Apple Silicon sans Terminal visible lorsqu'elle est lancée
# depuis « Installer Boîte noire Hoymiles.app ».
set -u

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(cd "$PACKAGE_DIR/.." && pwd)"
BASE="$HOME/Library/Application Support/BoiteNoireHoymiles"
APP_DEST="/Applications/Boîte noire Hoymiles.app"
OLD_USER_APP="$HOME/Applications/Boîte noire Hoymiles.app"
DESKTOP_LINK="$HOME/Desktop/Boîte noire Hoymiles.app"
LAUNCH_APP="$PACKAGE_DIR/Boîte noire Hoymiles.app"
PYTHON_BIN=""

dialog() {
  /usr/bin/osascript -e "display dialog \"$1\" with title \"Boîte noire Hoymiles\" buttons {\"OK\"} default button \"OK\" with icon caution" >/dev/null
}

choose_python() {
  for candidate in \
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3" \
    "$(command -v python3 2>/dev/null || true)"; do
    # Python provenant de python.org : 3.10 ou plus récent, avec Tkinter.
    # Homebrew peut fournir Python sans le module _tkinter : il est refusé.
    if [ -n "$candidate" ] && [ -x "$candidate" ] && "$candidate" -c "import sys, tkinter; raise SystemExit(not (sys.version_info >= (3, 10)))" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      return 0
    fi
  done
  return 1
}

if ! choose_python; then
  dialog "Python 3.10 ou plus récent avec Tkinter est nécessaire. Installez la version universelle macOS depuis python.org, puis relancez l'installation."
  exit 1
fi

if ! /usr/bin/osascript -e 'display dialog "Installer ou mettre à jour Boîte noire Hoymiles 7.0.30 pour macOS ?\n\nCette version utilise le réseau unique : DTU en Ethernet sur le nano-routeur Client/Pont, puis Wi-Fi de la box. Les historiques et réglages existants seront conservés." with title "Boîte noire Hoymiles" buttons {"Annuler", "Continuer"} default button "Continuer" with icon note' >/dev/null; then
  exit 0
fi

mkdir -p "$BASE"
# Après la première ouverture autorisée par l'utilisateur, les relances de ce
# dossier téléchargé ne doivent plus redemander l'autorisation Gatekeeper.
/usr/bin/xattr -dr com.apple.quarantine "$SOURCE_DIR" >/dev/null 2>&1 || true
CONFIG_FILE="$BASE/config_v5.json"
EXISTING_CONFIG="no"
[ -f "$CONFIG_FILE" ] && EXISTING_CONFIG="yes"
DTU_MODE="keep"
DINKY_MODE="keep"
SHELLY_MODE="keep"
DTU_HOST=""
DINKY_HOST=""
SHELLY_HOST=""

if [ "$EXISTING_CONFIG" = "yes" ]; then
  if /usr/bin/osascript -e 'display dialog "Les réglages réseau existants sont conservés.\n\nVoulez-vous modifier la connexion du DTU ?" with title "Boîte noire Hoymiles" buttons {"Conserver", "Modifier"} default button "Conserver" with icon note' | /usr/bin/grep -q "Modifier"; then
    DTU_MODE="change"
  fi
else
  DTU_MODE="new"
fi

if [ "$DTU_MODE" != "keep" ]; then
  DTU_HOST=$(/usr/bin/osascript -e 'text returned of (display dialog "Adresse IP réservée au DTU par votre box :\n\nLe DTU doit être relié en Ethernet au nano-routeur configuré en mode Client/Pont." default answer "192.168.1.137" with title "Réseau unique — nano-routeur/LAN" buttons {"Annuler", "Continuer"} default button "Continuer")') || exit 0

  if [ -z "$DTU_HOST" ]; then
    dialog "L'adresse IP du DTU est nécessaire pour le mode DTU-LAN."
    exit 1
  fi

fi

if [ "$EXISTING_CONFIG" = "yes" ]; then
  dinky_selection=$(/usr/bin/osascript -e 'choose from list {"Conserver le réglage Dinky actuel", "Configurer ou modifier le Dinky", "Désactiver le Dinky"} with title "Dinky / Linky" with prompt "Le Dinky est facultatif. Que souhaitez-vous faire ?" default items {"Conserver le réglage Dinky actuel"} OK button name "Continuer" Cancel button name "Annuler"') || exit 0
else
  dinky_selection=$(/usr/bin/osascript -e 'choose from list {"Configurer un Dinky", "Continuer sans Dinky"} with title "Dinky / Linky" with prompt "Le Dinky est-il présent sur le réseau de la box ?" default items {"Configurer un Dinky"} OK button name "Continuer" Cancel button name "Annuler"') || exit 0
fi

case "$dinky_selection" in
  *"Configurer"*)
    DINKY_MODE="enable"
    DINKY_HOST=$(/usr/bin/osascript -e 'text returned of (display dialog "Adresse IP du Dinky 4 sur le réseau de la box :" default answer "192.168.1.126" with title "Dinky 4" buttons {"Annuler", "Continuer"} default button "Continuer")') || exit 0
    [ -n "$DINKY_HOST" ] || { dialog "L'adresse IP du Dinky est nécessaire."; exit 1; }
    ;;
  *"sans Dinky"*|*"Désactiver"*) DINKY_MODE="disable" ;;
esac

if [ "$EXISTING_CONFIG" = "yes" ]; then
  shelly_selection=$(/usr/bin/osascript -e 'choose from list {"Conserver le réglage Shelly actuel", "Configurer ou modifier le Shelly", "Désactiver le Shelly"} with title "Shelly Pro EM" with prompt "Le Shelly est facultatif et reste strictement en lecture seule." default items {"Conserver le réglage Shelly actuel"} OK button name "Continuer" Cancel button name "Annuler"') || exit 0
else
  shelly_selection=$(/usr/bin/osascript -e 'choose from list {"Configurer un Shelly Pro EM", "Continuer sans Shelly"} with title "Shelly Pro EM" with prompt "Le Shelly est-il présent sur le réseau de la box ?" default items {"Configurer un Shelly Pro EM"} OK button name "Continuer" Cancel button name "Annuler"') || exit 0
fi

case "$shelly_selection" in
  *"Configurer"*)
    SHELLY_MODE="enable"
    SHELLY_HOST=$(/usr/bin/osascript -e 'text returned of (display dialog "Adresse IP du Shelly Pro EM sur le réseau de la box :" default answer "" with title "Shelly Pro EM" buttons {"Annuler", "Continuer"} default button "Continuer")') || exit 0
    [ -n "$SHELLY_HOST" ] || { dialog "L'adresse IP du Shelly est nécessaire."; exit 1; }
    ;;
  *"sans Shelly"*|*"Désactiver"*) SHELLY_MODE="disable" ;;
esac

DTU_MODE="$DTU_MODE" DTU_HOST="$DTU_HOST" DINKY_MODE="$DINKY_MODE" DINKY_HOST="$DINKY_HOST" SHELLY_MODE="$SHELLY_MODE" SHELLY_HOST="$SHELLY_HOST" CONFIG_FILE="$CONFIG_FILE" "$PYTHON_BIN" - <<'PY'
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

if os.environ.get("DTU_MODE") != "keep" and os.environ.get("DTU_HOST"):
    config["dtu_host"] = os.environ["DTU_HOST"]

# Sur macOS, la version prise en charge utilise exclusivement le réseau unique.
# Elle ne doit jamais tenter de basculer le Mac vers le Wi-Fi propre du DTU.
recovery = config.get("dtu_wifi_recovery", {}) if isinstance(config.get("dtu_wifi_recovery"), dict) else {}
config["dtu_wifi_recovery"] = {
    **recovery, "enabled": False, "interface": "", "profile": ""
}

dinky_mode = os.environ.get("DINKY_MODE", "keep")
if dinky_mode == "enable":
    config["linky"] = {
        "enabled": True, "mode": "dinky_http", "host": os.environ["DINKY_HOST"],
        "port": 80, "timeout_s": 2, "path": "Status 8"
    }
elif dinky_mode == "disable":
    linky = config.get("linky", {}) if isinstance(config.get("linky"), dict) else {}
    config["linky"] = {**linky, "enabled": False}

shelly_mode = os.environ.get("SHELLY_MODE", "keep")
if shelly_mode == "enable":
    config["shelly"] = {
        "enabled": True, "host": os.environ["SHELLY_HOST"], "port": 80,
        "timeout_s": 2,
        "channel_a_label": "Production panneaux Shelly",
        "channel_b_label": "Réseau EDF — mesure Shelly",
        "grid_export_positive": False,
    }
elif shelly_mode == "disable":
    shelly = config.get("shelly", {}) if isinstance(config.get("shelly"), dict) else {}
    config["shelly"] = {**shelly, "enabled": False}

path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
PY

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
# Installation dans le véritable dossier Applications de Finder. AppleScript
# demande le mot de passe administrateur uniquement pour cette copie système.
if ! /usr/bin/osascript - "$LAUNCH_APP" "$APP_DEST" <<'APPLESCRIPT'
on run argv
  set sourceApp to item 1 of argv
  set destinationApp to item 2 of argv
  set installCommand to "/bin/rm -rf " & quoted form of destinationApp & " && /usr/bin/ditto " & quoted form of sourceApp & " " & quoted form of destinationApp & " && /bin/chmod +x " & quoted form of (destinationApp & "/Contents/MacOS/BoiteNoireHoymiles") & " && /usr/bin/xattr -dr com.apple.quarantine " & quoted form of destinationApp & " && /usr/bin/codesign --force --deep --sign - " & quoted form of destinationApp
  do shell script installCommand with administrator privileges
end run
APPLESCRIPT
then
  dialog "L'installation dans le dossier Applications a été annulée ou a échoué."
  exit 1
fi

# Supprime uniquement l'ancien lanceur créé par les versions précédentes dans
# ~/Applications. Les historiques et réglages, stockés dans BASE, sont intacts.
if [ -e "$OLD_USER_APP" ] || [ -L "$OLD_USER_APP" ]; then
  /bin/rm -rf "$OLD_USER_APP"
fi

# Le dossier ~/Applications n'est pas toujours celui ouvert par Finder.
# Un lien visible sur le Bureau donne donc un lanceur immédiatement accessible.
if [ -L "$DESKTOP_LINK" ]; then
  /bin/rm -f "$DESKTOP_LINK"
fi
if [ ! -e "$DESKTOP_LINK" ]; then
  /bin/ln -s "$APP_DEST" "$DESKTOP_LINK"
fi

if /usr/bin/osascript -e 'display dialog "Installation terminée.\n\nUn seul lanceur « Boîte noire Hoymiles » est installé dans le dossier Applications de Finder. Un raccourci est également disponible sur le Bureau.\n\nAu premier lancement seulement, macOS peut encore demander l’autorisation d’accéder au réseau local." with title "Boîte noire Hoymiles" buttons {"Fermer", "Lancer maintenant"} default button "Lancer maintenant" with icon note' | /usr/bin/grep -q "Lancer maintenant"; then
  /usr/bin/open "$APP_DEST"
fi
