# Boîte noire Hoymiles v7.0.11 — macOS

Cette édition est testée en priorité sur macOS 13 ou plus récent avec Mac Apple Silicon (M1, M2, M3 et suivants). Elle peut aussi fonctionner sur Mac Intel avec une version universelle de Python et Tkinter ; cette configuration reste à tester par la communauté.

## Installation sans Terminal

1. Téléchargez et décompressez le ZIP GitHub.
2. Ouvrez le dossier `macOS-AppleSilicon`.
3. Clic droit sur `Installer Boîte noire Hoymiles.app`, puis **Ouvrir** lors de la première utilisation.
4. Lancez ensuite `Boîte noire Hoymiles` depuis le dossier **Applications**. Si l'interface ne lit pas le réseau local, double-cliquez sur `LANCER_MAC.command` dans ce dossier : il lance la même application depuis Terminal.

Les historiques et réglages sont conservés dans `~/Library/Application Support/BoiteNoireHoymiles`.

## Fonctions incluses dans la version 7.0.11

- suivi direct, 24 h, hier et historique de la production PV, DDSU et Linky/Dinky ;
- bilan EDF HP/HC et abonnement, basé sur les index Dinky 4 ;
- export CSV par période avec fichier compagnon de demande d'analyse au SAV ;
- captures d'écran datées et versionnées ;
- **Diagnostic DTU** en lecture seule : état observable du DDSU, des micro-onduleurs, données brutes et rapport exportable pour le SAV Hoymiles ; les mots de passe, clés Wi-Fi et jetons sont automatiquement masqués avant affichage ou export ;
- logiciel libre, indépendant et non affilié à EDF, Hoymiles ou S-Miles Cloud.

## Réseau DTU

- **DTU-LAN — recommandé** : DTU relié en Ethernet à la box. Le Dinky 4 et le DTU sont sur le réseau de la box ; saisissez l'adresse IP réellement donnée au DTU par la box. La production est lue localement par Modbus TCP (port 502).
- **DTU-WIFI — expérimental** : le DTU utilise son propre Wi-Fi. Le Mac doit garder le Wi-Fi de la box pour le Dinky, et disposer d'un deuxième adaptateur Wi-Fi USB compatible macOS / Apple Silicon pour le DTU.

## Python

L'installateur vérifie que Python 3.10 ou plus récent possède Tkinter. Si nécessaire, installez une version universelle macOS compatible depuis [python.org](https://www.python.org/downloads/macos/), puis relancez l'installateur.
