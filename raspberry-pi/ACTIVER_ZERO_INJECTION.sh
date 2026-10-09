#!/usr/bin/env bash
# Active explicitement la régulation locale des six panneaux.
# Le DTU reçoit uniquement des limites temporaires par Modbus TCP.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$HOME/AppData/Local/BoiteNoireHoymiles"
CONFIG_FILE="$CONFIG_DIR/config_v5.json"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Configuration introuvable : $CONFIG_FILE"
  exit 1
fi

DTU_HOST="$("$INSTALL_DIR/.venv/bin/python" -c 'import json, pathlib; print(json.loads(pathlib.Path.home().joinpath("AppData/Local/BoiteNoireHoymiles/config_v5.json").read_text()).get("dtu_host", ""))')"
if [ -z "$DTU_HOST" ]; then
  echo "Adresse DTU absente de la configuration. Renseignez-la dans Équipements avant l’activation."
  exit 1
fi

"$INSTALL_DIR/.venv/bin/python" - "$DTU_HOST" <<'PY'
import socket
import sys
host = sys.argv[1]
try:
    with socket.create_connection((host, 502), timeout=3):
        pass
except OSError as exc:
    raise SystemExit(f"DTU Modbus inaccessible sur {host}:502 ({type(exc).__name__}). Activation annulée.")
PY

mkdir -p "$CONFIG_DIR"
cp -p "$CONFIG_FILE" "$CONFIG_FILE.before-zero-injection"
"$INSTALL_DIR/.venv/bin/python" - "$CONFIG_FILE" <<'PY'
import json
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
control = data.setdefault("surplus_control", {})
control.update(enabled=True, rated_w=1000, dtu_enabled=True, dtu_rated_w=2000)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

sudo systemctl restart boite-noire-hoymiles
echo "Régulation activée pour le HMS et le DTU."
echo "Elle attend une batterie pleine stable pendant 2 minutes, puis vise environ 30 W achetés au réseau."
echo "Sauvegarde de la configuration : $CONFIG_FILE.before-zero-injection"
