# Boîte noire Hoymiles v7.0.21 — macOS

Cette édition utilise le même moteur que la version Windows 7.0.21. Elle est prévue en priorité pour macOS 13 ou plus récent sur Mac Apple Silicon (M1, M2, M3 et suivants). Un Mac Intel peut fonctionner avec une version compatible de Python et Tkinter, mais reste à tester par la communauté.

## Installation sans Terminal

1. Téléchargez puis décompressez le ZIP GitHub.
2. Ouvrez le dossier `macOS-AppleSilicon`.
3. Faites un clic droit sur `Installer Boîte noire Hoymiles.app`, puis choisissez **Ouvrir** lors de la première utilisation.
4. Autorisez l’accès au réseau local si macOS le demande.
5. Lancez ensuite `Boîte noire Hoymiles` depuis le dossier **Applications**.

Si l’application ne lit pas le réseau local, ouvrez **Réglages Système → Confidentialité et sécurité → Réseau local** et autorisez-la. Le fichier `LANCER_MAC.command` permet aussi de lancer le même logiciel depuis Terminal pour le diagnostic.

Les mises à jour conservent les historiques et réglages dans :

`~/Library/Application Support/BoiteNoireHoymiles`

## Réseau recommandé : un seul LAN

Le DTU Pro-S peut être relié directement à la box en Ethernet, ou à une petite passerelle configurée en **pont Wi-Fi / client bridge**. Le pont rejoint le Wi-Fi de la box sans créer un second routeur ni un autre sous-réseau.

```text
DTU Pro-S ── Ethernet ──> pont Wi-Fi ──> box
Linky ──> Dinky 4 ── Wi-Fi ───────────> box ──> Mac
Shelly Pro EM ─────── Wi-Fi/LAN ──────> box
```

Tous les appareils doivent recevoir une adresse dans le même réseau local que le Mac. Il est conseillé de réserver leurs adresses IP dans la box.

- **DTU-LAN — recommandé** : lecture locale de la production par Modbus TCP, port 502.
- **DTU-WIFI — expérimental** : connexion au Wi-Fi propre du DTU ; le Mac doit conserver l’accès à la box et utiliser un second adaptateur Wi-Fi compatible macOS.
- **Dinky 4 — facultatif** : mesure Linky réelle et index HP/HC.
- **Shelly Pro EM — facultatif** : deux mesures indépendantes, strictement en lecture seule.

Lors d’une mise à jour, l’installateur propose séparément de **conserver**, **modifier** ou **désactiver** le Dinky et le Shelly. Le choix « conserver » ne réinitialise pas l’ancienne configuration.

## Fonctions v7.0.21

- suivi direct, 24 h, hier et historique de la production PV, du DDSU et du Linky/Dinky ;
- lecture des deux voies du Shelly Pro EM avec libellés production panneaux et réseau EDF ;
- flux réseau signé : achat EDF positif, injection négative ;
- alerte d’injection persistante, cumul des Wh/kWh injectés et journal de preuves exportable ;
- bilan EDF HP/HC et abonnement basé sur les index réels du Dinky ;
- comparatif Hoymiles / Linky et moyenne quotidienne production-consommation ;
- export CSV, note SAV, captures datées et diagnostic DTU en lecture seule ;
- affichage automatique uniquement des sources activées et disponibles.

Le logiciel n’envoie aucune commande au Shelly, au relais ou au réglage zéro injection Hoymiles.

## Python

L’installateur recherche Python 3.10 ou plus récent avec Tkinter. Si nécessaire, installez une version universelle macOS depuis [python.org](https://www.python.org/downloads/macos/), puis relancez l’installateur.
