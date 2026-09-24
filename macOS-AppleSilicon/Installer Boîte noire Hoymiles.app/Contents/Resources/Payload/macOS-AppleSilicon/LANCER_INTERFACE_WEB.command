#!/bin/bash
BASE="$HOME/Library/Application Support/BoiteNoireHoymiles"
PYTHON="$BASE/venv/bin/python"
PROGRAM="$BASE/boite_noire_hoymiles.py"

export MPLCONFIGDIR="$BASE/.matplotlib"
/bin/mkdir -p "$MPLCONFIGDIR"
cd "$BASE" || exit 1
exec "$PYTHON" "$PROGRAM" --web-only
