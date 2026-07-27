# Boîte noire Hoymiles 7.0.4

## DDSU par Wi-Fi direct

- Le mode **DTU-WIFI DDSU** lit la puissance réseau du DDSU depuis le Wi-Fi propre du DTU.
- La valeur `phaseTotalPower` est convertie en watts (`× 10`), validation réalisée avec des charges réelles.
- L'application choisit automatiquement l'interface réseau qui atteint le DTU. Le Dinky peut donc rester sur la box à l'aide d'une seconde clé Wi-Fi USB.
- La configuration est identique sur Windows et macOS Apple Silicon : Wi-Fi interne vers le DTU, clé Wi-Fi USB vers la box/Dinky.
- La courbe bleue conserve la limite configurée dans S-Miles (110 % par défaut), sans interpréter ni modifier le champ Wi-Fi `powerLimit`.

## Ethernet

Le mode DTU-LAN est conservé pour la lecture de production photovoltaïque par Modbus TCP. Selon le firmware du DTU, la puissance DDSU n'est pas exposée sur cette interface et reste indiquée comme non disponible.

## Confidentialité

Les mesures, historiques, adresses IP et numéros de série restent locaux. Ne publiez jamais votre fichier `config_v5.json` ou un export de diagnostic.
