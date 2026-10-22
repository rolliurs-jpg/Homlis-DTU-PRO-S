#!/usr/bin/env bash
# Rétablit les deux liaisons Wi-Fi dédiées après un retour du courant ou un
# pilote USB resté bloqué. Ne touche jamais à l'Ethernet ni au Wi-Fi principal.
set -euo pipefail

ALFA_DEVICE=wlan2
DTU_DEVICE=wlan1
DTU_HOST=10.10.100.254
# Nom créé lors de l'installation de la liaison Wi-Fi directe DTU. Il peut être
# surchargé sans modifier ce script : DTU_WIFI_PROFILE="mon-profil".
DTU_PROFILE="${DTU_WIFI_PROFILE:-dtu-direct-4p}"

alfa_state="$(/usr/bin/nmcli -g GENERAL.STATE device show "$ALFA_DEVICE" 2>/dev/null || true)"
if [[ "$alfa_state" != "100 (connected)" ]]; then
  /usr/bin/nmcli device connect "$ALFA_DEVICE" || true
fi

# Certaines clés Wi-Fi USB TP-Link restent visibles dans Linux mais cessent de
# balayer les réseaux après une coupure ou une veille. Désactiver la veille à
# chaque cycle est inoffensif et couvre aussi les redémarrages du pilote.
if command -v iw >/dev/null 2>&1; then
  iw dev "$DTU_DEVICE" set power_save off 2>/dev/null || true
fi

# Ne réinitialise wlan1 que lorsque le DTU séparément alimenté n'est plus
# joignable. Cela évite d'interrompre les autres réseaux du Raspberry.
if /bin/ping -I "$DTU_DEVICE" -c 1 -W 2 "$DTU_HOST" >/dev/null 2>&1; then
  exit 0
fi

# Un cycle de l'interface suffit généralement à réveiller le pilote sans
# devoir débrancher la clé TP-Link. Puis NetworkManager réactive son profil.
/sbin/ip link set "$DTU_DEVICE" down 2>/dev/null || true
sleep 2
/sbin/ip link set "$DTU_DEVICE" up 2>/dev/null || true
sleep 3

if /usr/bin/nmcli -t -f NAME connection show | /bin/grep -Fxq "$DTU_PROFILE"; then
  /usr/bin/nmcli connection up "$DTU_PROFILE" ifname "$DTU_DEVICE" || true
else
  /usr/bin/nmcli device connect "$DTU_DEVICE" || true
fi
