# Boîte noire Hoymiles v7.0.25

## Réseau et installation

- Windows propose clairement deux configurations : deux connexions Wi-Fi, ou réseau unique nano-routeur/LAN.
- macOS utilise désormais uniquement le réseau unique nano-routeur/LAN.
- L’installateur Mac demande directement l’IP du DTU attribuée par la box.
- La récupération automatique du Wi-Fi propre au DTU est désactivée en mode LAN et sur Mac.
- Les guides expliquent le TP-Link TL-WR802N en mode Client/Pont et la réservation des adresses IP.

## Fiabilité

- Une lecture Dinky momentanément incomplète est retentée automatiquement avant d’afficher une déconnexion.
- Le moteur commun Windows/macOS reste identique et passe en version 7.0.25.

## Documentation

- README simplifié autour des trois choix réellement proposés : deux modes Windows et un seul mode Mac.
- Les anciennes notes de versions sont conservées dans `docs/release-notes` pour alléger la page principale du dépôt.
