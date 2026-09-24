#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Le script fonctionne aussi dans le petit paquet de réparation où les fichiers
# du programme sont placés directement à côté de lui.
if [ -s "$SCRIPT_DIR/boite_noire_hoymiles.py" ]; then
  SOURCE_DIR="$SCRIPT_DIR"
fi
BASE="$HOME/Library/Application Support/BoiteNoireHoymiles"
PROGRAM="$BASE/boite_noire_hoymiles.py"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS/fr.boitenoirehoymiles.web.plist"
UID_NUMBER=$(/usr/bin/id -u)

status() { printf '\n%s\n' "$1"; }

FILES="boite_noire_hoymiles.py mobile_dashboard.py dashboard_data.py dashboard_ui.html autostart.py monitoring.py energy_analysis.py battery_monitor.py fond_solaire.png icone_panneau_solaire.ico"

for item in $FILES; do
  if [ ! -s "$SOURCE_DIR/$item" ]; then
    status "ERREUR : le nouveau paquet est incomplet : $item est absent."
    exit 1
  fi
done

WEB_LAUNCHER="$SOURCE_DIR/LANCER_INTERFACE_WEB.command"
if [ ! -s "$WEB_LAUNCHER" ] && [ -s "$SCRIPT_DIR/LANCER_INTERFACE_WEB.command" ]; then
  WEB_LAUNCHER="$SCRIPT_DIR/LANCER_INTERFACE_WEB.command"
fi
if [ ! -s "$WEB_LAUNCHER" ]; then
  status "ERREUR : le lanceur invisible Mac est absent."
  exit 1
fi

status "Réparation directe 7.0.52 en cours — réglages et historiques conservés."

# Le lanceur Mac garde volontairement Python actif pendant le suivi. On arrête
# uniquement ce programme précis afin qu'il ne continue pas à servir l'ancienne
# interface chargée en mémoire. Les autres processus Python ne sont pas touchés.
/bin/launchctl bootout "gui/$UID_NUMBER" "$PLIST" >/dev/null 2>&1 || true
if /usr/bin/pgrep -f "$PROGRAM" >/dev/null 2>&1; then
  /usr/bin/pkill -TERM -f "$PROGRAM" >/dev/null 2>&1 || true
  count=0
  while /usr/bin/pgrep -f "$PROGRAM" >/dev/null 2>&1 && [ "$count" -lt 10 ]; do
    /bin/sleep 1
    count=$((count + 1))
  done
  if /usr/bin/pgrep -f "$PROGRAM" >/dev/null 2>&1; then
    /usr/bin/pkill -KILL -f "$PROGRAM" >/dev/null 2>&1 || true
  fi
fi

/bin/mkdir -p "$BASE"
for item in $FILES; do
  if ! /usr/bin/ditto "$SOURCE_DIR/$item" "$BASE/$item"; then
    status "ERREUR : la copie de $item a échoué."
    exit 1
  fi
  if ! /usr/bin/cmp -s "$SOURCE_DIR/$item" "$BASE/$item"; then
    status "ERREUR : la vérification de $item a échoué."
    exit 1
  fi
done

# Un paquet de transfert peut contenir l'historique brut du poste Windows.
# L'import crée d'abord une sauvegarde des CSV Mac, prend Windows comme
# référence jusqu'à sa dernière mesure, puis garde les mesures Mac plus récentes.
IMPORT_SCRIPT="$SOURCE_DIR/importer_historique_windows.py"
WINDOWS_HISTORY="$SOURCE_DIR/Historique Windows"
if [ -s "$IMPORT_SCRIPT" ] && [ -d "$WINDOWS_HISTORY" ]; then
  if [ ! -x "$BASE/venv/bin/python" ]; then
    status "ERREUR : Python Mac est absent ; historique Windows non importé."
    exit 1
  fi
  status "Import sécurisé de l'historique Windows en cours."
  if ! "$BASE/venv/bin/python" "$IMPORT_SCRIPT" "$BASE" "$WINDOWS_HISTORY"; then
    status "ERREUR : l'import de l'historique Windows a échoué."
    exit 1
  fi
fi

if ! /usr/bin/ditto "$WEB_LAUNCHER" "$BASE/LANCER_INTERFACE_WEB.command" ||
   ! /usr/bin/cmp -s "$WEB_LAUNCHER" "$BASE/LANCER_INTERFACE_WEB.command"; then
  status "ERREUR : le lanceur invisible n'a pas été installé."
  exit 1
fi

if ! /usr/bin/grep -q 'VERSION = "7.0.52"' "$PROGRAM" ||
   ! /usr/bin/grep -q 'Version 7.0.52' "$BASE/dashboard_ui.html"; then
  status "ERREUR : les fichiers installés ne correspondent pas à la version 7.0.52."
  exit 1
fi

/usr/bin/xattr -dr com.apple.quarantine "$SOURCE_DIR" >/dev/null 2>&1 || true

/bin/chmod +x "$BASE/LANCER_INTERFACE_WEB.command"
/bin/mkdir -p "$LAUNCH_AGENTS"
/bin/cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>fr.boitenoirehoymiles.web</string>
<key>ProgramArguments</key><array><string>$BASE/LANCER_INTERFACE_WEB.command</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$BASE/service_web.log</string>
<key>StandardErrorPath</key><string>$BASE/service_web_erreur.log</string>
</dict></plist>
EOF

/bin/launchctl bootout "gui/$UID_NUMBER" "$PLIST" >/dev/null 2>&1 || true
if ! /bin/launchctl bootstrap "gui/$UID_NUMBER" "$PLIST"; then
  status "ERREUR : le service invisible n'a pas pu être démarré."
  exit 1
fi
/bin/launchctl enable "gui/$UID_NUMBER/fr.boitenoirehoymiles.web" >/dev/null 2>&1 || true
/bin/launchctl kickstart -k "gui/$UID_NUMBER/fr.boitenoirehoymiles.web" >/dev/null 2>&1 || true

# Ne pas annoncer une réussite tant que le serveur ne répond pas réellement.
ready=0
count=0
while [ "$count" -lt 20 ]; do
  if /usr/bin/curl -fsS --max-time 2 "http://127.0.0.1:8765/api/status" >/dev/null 2>&1; then
    ready=1
    break
  fi
  /bin/sleep 1
  count=$((count + 1))
done
if [ "$ready" -ne 1 ]; then
  status "ERREUR : le service invisible n'a pas démarré."
  status "Dernières informations techniques :"
  /usr/bin/tail -n 12 "$BASE/service_web_erreur.log" 2>/dev/null || true
  exit 1
fi

MAC_IP=""
for interface in en0 en1; do
  candidate=$(/usr/sbin/ipconfig getifaddr "$interface" 2>/dev/null || true)
  if [ -n "$candidate" ]; then
    MAC_IP="$candidate"
    break
  fi
done
WEB_ADDRESS="http://${MAC_IP:-127.0.0.1}:8765"
status "TERMINÉ : version 7.0.52 installée en mode invisible et automatique."
status "Adresse de cette installation Mac : $WEB_ADDRESS"
exit 0
