#!/usr/bin/env bash
# Reprend la liaison Alfa vers le cabanon si NetworkManager ne l'a pas
# reassocie apres le retour du courant. Ne touche ni au DTU (wlan1), ni a
# l'Ethernet : le WLAN2 garde son profil NetworkManager existant.
set -euo pipefail

DEVICE=wlan2
STATE="$(/usr/bin/nmcli -g GENERAL.STATE device show "$DEVICE" 2>/dev/null || true)"

if [[ "$STATE" == "100 (connected)" ]]; then
  exit 0
fi

/usr/bin/nmcli device connect "$DEVICE"
