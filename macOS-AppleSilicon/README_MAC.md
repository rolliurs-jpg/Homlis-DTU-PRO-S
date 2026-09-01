# Boîte noire Hoymiles v7.0.24 — macOS

Cette édition utilise le même moteur que la version Windows 7.0.24. Elle est prévue en priorité pour macOS 13 ou plus récent sur Mac Apple Silicon (M1, M2, M3 et suivants). Un Mac Intel peut fonctionner avec une version compatible de Python et Tkinter, mais reste à tester par la communauté.

## Installation sans Terminal

1. Téléchargez puis décompressez le ZIP GitHub.
2. Ouvrez le dossier `macOS-AppleSilicon`.
3. Faites un clic droit sur `Installer Boîte noire Hoymiles.app`, puis choisissez **Ouvrir** lors de la première utilisation.
4. Autorisez l’accès au réseau local si macOS le demande.
5. L’installateur crée un seul lanceur `Boîte noire Hoymiles` dans le dossier Finder standard `/Applications`, ainsi qu’un raccourci directement visible sur le **Bureau**. Le mot de passe administrateur est demandé pour cette copie.
6. Choisissez **Lancer maintenant** à la fin de l’installation, ou utilisez ensuite le lanceur du Bureau.

Le lanceur utilise le logo des panneaux solaires du projet. Les boutons de l’application macOS utilisent la même forme rectangulaire que la version Windows, afin d’éviter la superposition de deux contours.

Si Launchpad contient plusieurs anciennes icônes, mettez à la corbeille les anciens dossiers téléchargés qui contiennent `Installer Boîte noire Hoymiles.app` ou `Boîte noire Hoymiles.app`, puis supprimez l’ancienne copie éventuelle dans `~/Applications`. Gardez uniquement `/Applications/Boîte noire Hoymiles.app`. Le dossier `~/Library/Application Support/BoiteNoireHoymiles` doit être conservé : il contient les réglages et historiques.

Si l’application ne lit pas le réseau local, ouvrez **Réglages Système → Confidentialité et sécurité → Réseau local** et autorisez-la. Le fichier `LANCER_MAC.command` permet aussi de lancer le même logiciel depuis Terminal pour le diagnostic.

Le paquet communautaire n’est pas notarisé avec un compte Apple Developer payant. La toute première ouverture de l’installateur peut donc nécessiter **clic droit → Ouvrir**. Après cette validation, l’installateur retire la quarantaine du dossier téléchargé, signe localement le lanceur installé et macOS ne devrait plus répéter l’avertissement à chaque lancement. Une nouvelle version peut néanmoins redemander une autorisation unique.

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

## Fonctions v7.0.24

- suivi direct, 24 h, hier et historique de la production PV, du DDSU et du Linky/Dinky ;
- conservation des mesures Dinky et Shelly lorsqu’une synchronisation ou une coupure rend le DTU momentanément indisponible ;
- lecture des deux voies du Shelly Pro EM avec libellés production panneaux et réseau EDF ;
- flux réseau signé : achat EDF positif, injection négative ;
- alerte d’injection persistante, cumul des Wh/kWh injectés et journal de preuves exportable ;
- notification d’injection non bloquante et collecte maintenue pendant la pause DTU ;
- interruption visuelle des courbes lorsqu’une période ne contient aucune mesure ;
- bilan EDF HP/HC et abonnement basé sur les index réels du Dinky ;
- comparatif Hoymiles / Linky et moyenne quotidienne production-consommation ;
- export CSV, note SAV, captures datées et diagnostic DTU en lecture seule ;
- affichage automatique uniquement des sources activées et disponibles.

Le logiciel n’envoie aucune commande au Shelly, au relais ou au réglage zéro injection Hoymiles.

## Python

L’installateur recherche Python 3.10 ou plus récent avec Tkinter. Si nécessaire, installez une version universelle macOS depuis [python.org](https://www.python.org/downloads/macos/), puis relancez l’installateur.
