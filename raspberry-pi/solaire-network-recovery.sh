#!/usr/bin/env bash
# Rétablit les deux liaisons Wi-Fi dédiées après un retour du courant ou un
# pilote USB resté bloqué. Ne touche jamais à l'Ethernet ni au Wi-Fi principal.
#
# Important : ce script n'utilise jamais « nmcli device connect ». Cette
# commande peut associer une clé à un autre réseau connu (par exemple la
# Livebox) après une coupure. Seuls les profils explicitement indiqués ici
# peuvent être activés.
set -euo pipefail

NETWORK_ENV="${SOLAIRE_NETWORK_ENV:-/etc/solaire-network.env}"
if [[ -r "$NETWORK_ENV" ]]; then
  # Fichier administré localement : il ne contient pas de mot de passe.
  # shellcheck disable=SC1090
  source "$NETWORK_ENV"
fi

ALFA_DEVICE="${ALFA_DEVICE:-wlan2}"
ALFA_PROFILE="${ALFA_PROFILE:-solaire-cabanon-alfa}"
ALFA_ROUTER_HOST="${ALFA_ROUTER_HOST:-192.168.4.1}"
ALFA_PROXY_HOST="${ALFA_PROXY_HOST:-192.168.4.2}"
DTU_DEVICE="${DTU_DEVICE:-wlan1}"
DTU_HOST="${DTU_HOST:-10.10.100.254}"
# Nom créé lors de l'installation de la liaison Wi-Fi directe DTU.
DTU_PROFILE="${DTU_PROFILE:-dtu-direct-4p}"

activate_profile() {
  local profile="$1" device="$2"
  if /usr/bin/nmcli -t -f NAME connection show | /bin/grep -Fxq "$profile"; then
    /usr/bin/nmcli connection up "$profile" ifname "$device" || true
  else
    logger -t solaire-network-recovery "Profil Wi-Fi absent : $profile ($device)"
    return 1
  fi
}

cycle_device() {
  local device="$1"
  /sbin/ip link set "$device" down 2>/dev/null || true
  sleep 2
  /sbin/ip link set "$device" up 2>/dev/null || true
  sleep 3
}

disable_power_save() {
  local device="$1"
  if command -v iw >/dev/null 2>&1; then
    iw dev "$device" set power_save off 2>/dev/null || true
  fi
}

# Liaison cabanon : le routeur et le proxy ont des IP fixes. Le routeur suffit
# à prouver l'association Wi-Fi ; le proxy peut attendre son propre démarrage.
disable_power_save "$ALFA_DEVICE"
if ! /bin/ping -I "$ALFA_DEVICE" -c 1 -W 2 "$ALFA_ROUTER_HOST" >/dev/null 2>&1; then
  activate_profile "$ALFA_PROFILE" "$ALFA_DEVICE"
  sleep 3
fi
if ! /bin/ping -I "$ALFA_DEVICE" -c 1 -W 2 "$ALFA_ROUTER_HOST" >/dev/null 2>&1; then
  cycle_device "$ALFA_DEVICE"
  activate_profile "$ALFA_PROFILE" "$ALFA_DEVICE"
fi

# Certaines clés Wi-Fi USB TP-Link restent visibles dans Linux mais cessent de
# balayer les réseaux après une coupure ou une veille. Désactiver la veille à
# chaque cycle est inoffensif et couvre aussi les redémarrages du pilote.
disable_power_save "$DTU_DEVICE"

# Ne réinitialise wlan1 que lorsque le DTU séparément alimenté n'est plus
# joignable. Cela évite d'interrompre les autres réseaux du Raspberry.
if /bin/ping -I "$DTU_DEVICE" -c 1 -W 2 "$DTU_HOST" >/dev/null 2>&1; then
  exit 0
fi

# Un cycle de l'interface suffit généralement à réveiller le pilote sans
# devoir débrancher la clé TP-Link. Puis NetworkManager réactive uniquement le
# profil DTU dédié, jamais un réseau voisin.
cycle_device "$DTU_DEVICE"
activate_profile "$DTU_PROFILE" "$DTU_DEVICE"
