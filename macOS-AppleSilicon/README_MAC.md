# Boîte noire Hoymiles — macOS Apple Silicon

Cette édition est prévue pour macOS 13 ou plus récent sur Mac Apple Silicon (M1, M2, M3 et suivants).

## Installation sans Terminal

1. Téléchargez et décompressez le ZIP GitHub.
2. Ouvrez le dossier `macOS-AppleSilicon`.
3. Clic droit sur `Installer Boîte noire Hoymiles.app`, puis **Ouvrir** lors de la première utilisation.
4. Lancez ensuite `Boîte noire Hoymiles` depuis le dossier **Applications**. Si l'interface ne lit pas le réseau local, double-cliquez sur `LANCER_MAC.command` dans ce dossier : il lance la même application depuis Terminal.

Les historiques et réglages sont conservés dans `~/Library/Application Support/BoiteNoireHoymiles`.

## Réseau DTU

- **DTU-LAN — recommandé** : DTU relié en Ethernet à la box. Le Dinky 4 et le DTU sont sur le réseau de la box ; saisissez l'adresse IP réellement donnée au DTU par la box. La production est lue localement par Modbus TCP (port 502).
- **DTU-WIFI — expérimental** : le DTU utilise son propre Wi-Fi. Le Mac doit garder le Wi-Fi de la box pour le Dinky, et disposer d'un deuxième adaptateur Wi-Fi USB compatible macOS / Apple Silicon pour le DTU.

## Python

L'installateur vérifie que Python 3.10 à 3.13 possède Tkinter. Si nécessaire, installez une version universelle macOS compatible depuis [python.org](https://www.python.org/downloads/macos/), puis relancez l'installateur.
