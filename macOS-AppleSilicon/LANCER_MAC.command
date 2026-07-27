#!/bin/bash
# Lance la Boîte noire depuis Terminal lorsque macOS restreint le paquet .app.
set -euo pipefail

BASE="$HOME/Library/Application Support/BoiteNoireHoymiles"
PYTHON="$BASE/venv/bin/python"
PROGRAM="$BASE/boite_noire_hoymiles.py"

if [[ ! -x "$PYTHON" || ! -f "$PROGRAM" ]]; then
  echo "Le logiciel n'est pas encore installé. Ouvrez d'abord « Installer Boîte noire Hoymiles.app »."
  read -r -p "Appuyez sur Entrée pour fermer…"
  exit 1
fi

export MPLCONFIGDIR="$BASE/.matplotlib"
mkdir -p "$MPLCONFIGDIR"
cd "$BASE"
exec "$PYTHON" "$PROGRAM"
