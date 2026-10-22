#!/bin/zsh
# Sauvegarde de restauration du Raspberry solaire vers le Bureau du Mac.
# Le fichier contient des secrets Wi-Fi et Hoymiles : il est créé en 600.
set -euo pipefail

PI_USER="${PI_USER:-solar}"
PI_HOST="${1:-192.168.1.52}"
STAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
DESTINATION="$HOME/Desktop/Sauvegardes-Solaire"
REMOTE_ARCHIVE="/tmp/solaire-configuration-${STAMP}.tar.gz"
PARTIAL_ARCHIVE="$DESTINATION/.solaire-configuration-${STAMP}.tar.gz.part"
FINAL_ARCHIVE="$DESTINATION/solaire-configuration-${STAMP}.tar.gz"

umask 077
mkdir -p "$DESTINATION"
chmod 700 "$DESTINATION"

cleanup_remote() {
  ssh -o ConnectTimeout=8 "$PI_USER@$PI_HOST" "rm -f '$REMOTE_ARCHIVE'" >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT

echo "Préparation de la sauvegarde du Raspberry ${PI_HOST}…"
echo "Le mot de passe du Raspberry peut être demandé (connexion puis sudo)."

# La liste est volontairement limitée aux éléments nécessaires à une
# restauration : l'application se réinstalle depuis Git, tandis que ces
# fichiers contiennent les réglages spécifiques à cette installation.
ssh -tt "$PI_USER@$PI_HOST" "ARCHIVE='$REMOTE_ARCHIVE' bash -s" <<'REMOTE'
set -euo pipefail
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

# Réglages applicatifs et fichiers de reprise réseau.
save_item "$HOME/AppData/Local/BoiteNoireHoymiles/config_v5.json"
save_item "$HOME/solaire/raspberry-pi"
save_item "$HOME/solaire-source/raspberry-pi"
save_item /etc/solaire-network.env
save_item /etc/systemd/system/boite-noire-hoymiles.service
save_item /etc/systemd/system/solaire-network-recovery.service
save_item /etc/systemd/system/solaire-network-recovery.timer

# Les profils Wi-Fi sont indispensables après une réinstallation ; ils peuvent
# contenir les clés WPA, d'où les permissions strictes sur l'archive finale.
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
REMOTE

scp "$PI_USER@$PI_HOST:$REMOTE_ARCHIVE" "$PARTIAL_ARCHIVE"
mv "$PARTIAL_ARCHIVE" "$FINAL_ARCHIVE"
chmod 600 "$FINAL_ARCHIVE"

echo
echo "Sauvegarde créée : $FINAL_ARCHIVE"
echo "Conservez-la hors du Raspberry et ne la partagez pas."
