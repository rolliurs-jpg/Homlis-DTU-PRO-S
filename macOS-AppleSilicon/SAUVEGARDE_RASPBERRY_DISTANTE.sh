#!/usr/bin/env bash
# Helper lancé temporairement sur le Raspberry par SAUVEGARDE_RASPBERRY_VERS_MAC.sh.
set -euo pipefail

ARCHIVE="${1:?Archive de destination manquante}"
stage="$(mktemp -d /tmp/solaire-backup.XXXXXX)"
cleanup() { sudo rm -rf "$stage"; }
trap cleanup EXIT

save_item() {
  local source="$1" relative
  if sudo test -e "$source"; then
    relative="${source#/}"
    sudo mkdir -p "$stage/$(dirname "$relative")"
    sudo cp -a "$source" "$stage/$relative"
  fi
}

# L'application se réinstalle depuis Git ; seuls ses réglages spécifiques et
# les éléments système nécessaires après une coupure sont sauvegardés ici.
save_item "$HOME/AppData/Local/BoiteNoireHoymiles/config_v5.json"
save_item "$HOME/solaire/raspberry-pi"
save_item "$HOME/solaire-source/raspberry-pi"
save_item /etc/solaire-network.env
save_item /etc/systemd/system/boite-noire-hoymiles.service
save_item /etc/systemd/system/solaire-network-recovery.service
save_item /etc/systemd/system/solaire-network-recovery.timer

# Peut contenir les clés WPA : l'archive est protégée par les permissions Mac.
save_item /etc/NetworkManager/system-connections

cat > "$stage/README-RESTAURATION.txt" <<'EOF'
Sauvegarde de configuration solaire Raspberry Pi.

Contenu : configuration de l'application, profils Wi-Fi, unités systemd et
scripts de reprise réseau. Les sources du logiciel restent disponibles dans
le dépôt Git ; ne partagez jamais cette archive car elle peut contenir des
clés Wi-Fi et les identifiants de liaison Hoymiles.
EOF

sudo tar -C "$stage" -czf "$ARCHIVE" .
sudo chown "$(id -u):$(id -g)" "$ARCHIVE"
