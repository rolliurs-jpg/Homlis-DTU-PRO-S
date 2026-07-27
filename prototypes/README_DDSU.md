# Prototype DDSU — DTU Pro-S Ethernet

Ce dossier est séparé de l'application principale. Il sert uniquement à rechercher si le firmware du DTU expose une mesure DDSU par Modbus TCP.

`dtu_ddsu_probe.py` est **strictement en lecture seule** : il utilise seulement les fonctions Modbus de lecture `0x03` et `0x04`. Il n'envoie aucune consigne et ne modifie pas le DTU.

Sur Mac, le plus simple est de double-cliquer sur `LANCER_PROTOTYPE_DDSU.command`, puis de saisir l'adresse IP Ethernet du DTU. Ce lanceur utilise le Python déjà installé avec la Boîte noire Hoymiles.

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

## Essai comparatif conseillé

Lancez un essai de 60 secondes, puis allumez ou éteignez une charge connue (bouilloire, chauffage…) pendant l'essai. Le Dinky est utilisé seulement comme référence de variation, pas comme remplacement du DDSU :

```bash
python dtu_ddsu_probe.py --host IP_DU_DTU --watch 60 --dinky-host IP_DU_DINKY
```

Envoyez ensuite le texte affiché par Terminal. Le prototype compare la variation du Dinky avec les registres non documentés du DTU pour rechercher la valeur DDSU.

## Essai Wi-Fi direct (nouvelle piste)

L'Ethernet et le Wi-Fi direct du DTU utilisent deux services différents. Le DDSU est bien relié physiquement au DTU en RS485, mais il reste à vérifier si le firmware l'expose de la même façon sur ces deux services.

Sans toucher à l'application actuelle, double-cliquez sur `LANCER_WIFI_DDSU_PROTOTYPE.command` après avoir connecté le Mac au réseau `DTUP-…` du DTU. Le test envoie uniquement la requête de lecture `get-real-data-new`, puis affiche les champs qui évoquent le compteur, le réseau ou la puissance. La valeur `mesure_ddsu.puissance_reseau_w` provient de `meterData[0].phaseTotalPower × 10` : c'est la piste pour la future courbe rouge. Les essais ont aussi confirmé `voltagePhaseA ÷ 100`, `currentPhaseA ÷ 100` et `powerFactorTotal ÷ 1000`.

Choisissez `60` secondes dans le lanceur et faites varier une charge pendant l'essai. Le DTU Wi-Fi répond lentement : ce mode produit environ trois relevés espacés de 15 secondes. Une absence de réponse ponctuelle est indiquée dans le rapport, sans effacer les mesures déjà réussies.

Le Mac quittera temporairement le Wi-Fi de la box : c'est normal. Pour cet essai, ne lancez pas le logiciel principal en parallèle. Envoyez ensuite le texte affiché par Terminal, sans le publier sur GitHub.
