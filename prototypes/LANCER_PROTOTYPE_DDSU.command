#!/bin/bash
# Prototype séparé : lecture Modbus uniquement, aucune écriture dans le DTU.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$HOME/Library/Application Support/BoiteNoireHoymiles/venv/bin/python"
PROBE="$SCRIPT_DIR/dtu_ddsu_probe.py"

if [[ ! -x "$PYTHON" ]]; then
  echo "Le Python de la Boîte noire Hoymiles est introuvable. Installez d'abord le logiciel."
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi

read -r -p "Adresse IP Ethernet du DTU : " HOST
if [[ -z "$HOST" ]]; then
  echo "Aucune adresse IP saisie."
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi

echo
echo "Prototype en lecture seule : aucune commande ne sera envoyée au DTU."
"$PYTHON" "$PROBE" --host "$HOST"
echo
read -r -p "Appuyez sur Entrée pour fermer…"
