#!/bin/bash
# Prototype séparé : lecture des données Wi-Fi du DTU, aucune écriture.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$HOME/Library/Application Support/BoiteNoireHoymiles/venv/bin/python"
PROBE="$SCRIPT_DIR/dtu_wifi_ddsu_probe.py"

echo "PROTOTYPE DDSU — Wi-Fi direct du DTU (lecture seule)"
echo
echo "1. Connectez d'abord ce Mac au réseau Wi-Fi DTUP-… du DTU."
echo "2. Ce test ne change aucun réglage et n'envoie aucune commande au DTU."
echo
read -r -p "Appuyez sur Entrée lorsque le Mac est connecté au Wi-Fi DTU…"

if [[ ! -x "$PYTHON" ]]; then
  echo "Le Python de la Boîte noire Hoymiles est introuvable. Installez d'abord le logiciel."
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi

read -r -p "Durée du test (0 = une mesure, conseillé : 60 secondes) : " WATCH_SECONDS
WATCH_SECONDS="${WATCH_SECONDS:-0}"
ARGS=()
if [[ "$WATCH_SECONDS" =~ ^[0-9]+$ ]] && [[ "$WATCH_SECONDS" -gt 0 ]]; then
  ARGS+=(--watch "$WATCH_SECONDS")
fi

"$PYTHON" "$PROBE" "${ARGS[@]}"
echo
read -r -p "Appuyez sur Entrée pour fermer…"
