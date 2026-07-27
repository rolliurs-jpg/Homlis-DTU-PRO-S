# Prototype DDSU — DTU Pro-S Ethernet

Ce dossier est séparé de l'application principale. Il sert uniquement à rechercher si le firmware du DTU expose une mesure DDSU par Modbus TCP.

`dtu_ddsu_probe.py` est **strictement en lecture seule** : il utilise seulement les fonctions Modbus de lecture `0x03` et `0x04`. Il n'envoie aucune consigne et ne modifie pas le DTU.

## Essai de base

Depuis un ordinateur sur le même réseau que le DTU :

```bash
python dtu_ddsu_probe.py --host IP_DU_DTU
```

Le résultat s'affiche localement au format JSON. Ne publiez pas ce résultat : il peut contenir des informations techniques de votre installation.

## Balayage exploratoire

Le balayage reste en lecture seule mais il effectue de nombreuses requêtes, lentement. Ne l'utilisez que pour un essai ponctuel, lorsque le DTU fonctionne normalement :

```bash
python dtu_ddsu_probe.py --host IP_DU_DTU --scan
```

Si une plage de registres varie en même temps que la puissance affichée par le DDSU dans S-Miles, elle pourra être ajoutée plus tard au logiciel principal après validation. Aucune modification de la version actuelle n'est faite pendant cette phase.
