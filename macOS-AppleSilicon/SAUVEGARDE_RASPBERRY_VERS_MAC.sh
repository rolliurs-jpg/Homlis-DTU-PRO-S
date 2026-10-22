#!/bin/zsh
# Sauvegarde de restauration du Raspberry solaire vers le Bureau du Mac.
# Le fichier contient des secrets Wi-Fi et Hoymiles : il est créé en 600.
set -euo pipefail

PI_USER="${PI_USER:-solar}"
PI_HOST="${1:-192.168.1.52}"
STAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
SCRIPT_DIR="${0:A:h}"
DESTINATION="$HOME/Desktop/Sauvegardes-Solaire"
REMOTE_ARCHIVE="/tmp/solaire-configuration-${STAMP}.tar.gz"
REMOTE_HELPER="/tmp/solaire-backup-${STAMP}.sh"
PARTIAL_ARCHIVE="$DESTINATION/.solaire-configuration-${STAMP}.tar.gz.part"
FINAL_ARCHIVE="$DESTINATION/solaire-configuration-${STAMP}.tar.gz"

umask 077
mkdir -p "$DESTINATION"
chmod 700 "$DESTINATION"

cleanup_remote() {
  ssh -o ConnectTimeout=8 "$PI_USER@$PI_HOST" "rm -f '$REMOTE_ARCHIVE' '$REMOTE_HELPER'" >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT

echo "Préparation de la sauvegarde du Raspberry ${PI_HOST}…"
echo "Le mot de passe du Raspberry peut être demandé (connexion puis sudo)."

# Le script de copie est transféré comme un fichier, puis exécuté sur un vrai
# terminal distant. Le mot de passe sudo est ainsi demandé normalement, sans
# afficher les lignes du script ni les caractères saisis.
scp "$SCRIPT_DIR/SAUVEGARDE_RASPBERRY_DISTANTE.sh" "$PI_USER@$PI_HOST:$REMOTE_HELPER"
ssh -tt "$PI_USER@$PI_HOST" "bash '$REMOTE_HELPER' '$REMOTE_ARCHIVE'"

scp "$PI_USER@$PI_HOST:$REMOTE_ARCHIVE" "$PARTIAL_ARCHIVE"
mv "$PARTIAL_ARCHIVE" "$FINAL_ARCHIVE"
chmod 600 "$FINAL_ARCHIVE"

echo
echo "Sauvegarde créée : $FINAL_ARCHIVE"
echo "Conservez-la hors du Raspberry et ne la partagez pas."
