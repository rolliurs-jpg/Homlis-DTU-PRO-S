#!/usr/bin/env bash
# Installe ou met à jour le collecteur sur Raspberry Pi OS.
# Les réglages et historiques restent dans le dossier personnel de l'utilisateur.
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${1:-$HOME/solaire}"
SERVICE_NAME="boite-noire-hoymiles.service"
USER_NAME="$(id -un)"

if [ "$(id -u)" -eq 0 ]; then
  echo "Lancez cet installateur depuis votre compte Raspberry habituel, sans sudo."
  exit 1
fi

echo "Installation de Boîte noire Hoymiles dans : $INSTALL_DIR"
sudo apt update
sudo apt install -y python3-venv

mkdir -p "$INSTALL_DIR/raspberry-pi"
FILES=(
  boite_noire_hoymiles.py mobile_dashboard.py dashboard_data.py dashboard_ui.html
  autostart.py monitoring.py energy_analysis.py battery_monitor.py
  surplus_simulation.py surplus_controller.py dtu_control.py PAIRER_HOYMILES.py
  hoymiles_proxy.py HOYMILES_BLE_LICENSE.txt requirements.txt fond_solaire.png
  icone_panneau_solaire.ico config.example.json README.md
)
for file in "${FILES[@]}"; do
  install -m 0644 "$SOURCE_DIR/$file" "$INSTALL_DIR/$file"
done
install -m 0644 "$SOURCE_DIR/raspberry-pi/README.md" "$INSTALL_DIR/raspberry-pi/README.md"
install -m 0644 "$SOURCE_DIR/raspberry-pi/boite-noire-hoymiles.service.example" "$INSTALL_DIR/raspberry-pi/boite-noire-hoymiles.service.example"
install -m 0755 "$SOURCE_DIR/raspberry-pi/ACTIVER_ZERO_INJECTION.sh" "$INSTALL_DIR/raspberry-pi/ACTIVER_ZERO_INJECTION.sh"

if [ ! -f "$HOME/AppData/Local/BoiteNoireHoymiles/config_v5.json" ]; then
  mkdir -p "$HOME/AppData/Local/BoiteNoireHoymiles"
  install -m 0600 "$SOURCE_DIR/config.example.json" "$HOME/AppData/Local/BoiteNoireHoymiles/config_v5.json"
  echo "Configuration vierge créée dans $HOME/AppData/Local/BoiteNoireHoymiles/config_v5.json"
  echo "Renseignez vos propres équipements depuis le tableau web, puis relancez le service."
fi

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/.venv/bin/python" -m pip install -r "$INSTALL_DIR/requirements.txt"

sed \
  -e "s|/home/YOUR_LINUX_USER/solaire|$INSTALL_DIR|g" \
  -e "s|YOUR_LINUX_USER|$USER_NAME|g" \
  "$INSTALL_DIR/raspberry-pi/boite-noire-hoymiles.service.example" \
  | sudo tee "/etc/systemd/system/$SERVICE_NAME" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"

echo
echo "Installation terminée. Ouvrez : http://ADRESSE_DU_RASPBERRY:8765/"
echo "État du service : sudo systemctl status $SERVICE_NAME"
