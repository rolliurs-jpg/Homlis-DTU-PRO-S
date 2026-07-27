# Boîte noire Hoymiles — macOS Apple Silicon

Cette édition est prévue pour macOS 13 ou plus récent sur Mac Apple Silicon (M1, M2, M3 et suivants).

## Installation sans Terminal

1. Téléchargez et décompressez le ZIP GitHub.
2. Ouvrez le dossier `macOS-AppleSilicon`.
3. Clic droit sur `Installer Boîte noire Hoymiles.app`, puis **Ouvrir** lors de la première utilisation.
4. Lancez ensuite `Boîte noire Hoymiles` depuis le dossier **Applications**.

Les historiques et réglages sont conservés dans `~/Library/Application Support/BoiteNoireHoymiles`.

## Réseau DTU

- **DTU-LAN — recommandé** : DTU relié en Ethernet à la box. Le Dinky 4 et le DTU sont sur le réseau de la box ; saisissez l'adresse IP donnée au DTU par la box.
- **DTU-WIFI — expérimental** : le DTU utilise son propre Wi-Fi. Le Mac doit garder le Wi-Fi de la box pour le Dinky, et disposer d'un deuxième adaptateur Wi-Fi USB compatible macOS / Apple Silicon pour le DTU.

## Python

L'installateur vérifie que Python possède Tkinter. Si nécessaire, installez la version universelle macOS depuis [python.org](https://www.python.org/downloads/macos/), puis relancez l'installateur.
