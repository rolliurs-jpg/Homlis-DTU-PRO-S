# Boîte noire Hoymiles 7.0.3

## DTU Pro-S en Ethernet et macOS

- Lecture locale de la production PV du DTU Pro-S par **Modbus TCP** (port 502) lorsqu'il est relié en Ethernet à la box.
- Ajout de `macOS-AppleSilicon/LANCER_MAC.command` : ce lanceur ouvre le logiciel depuis Terminal lorsque macOS empêche le paquet `.app` d'accéder au réseau local.
- L'installateur macOS demande l'adresse IP réellement attribuée par la box au DTU : aucune adresse fictive n'est préremplie.
- L'installateur macOS choisit Python 3.10 à 3.13 pour garantir la compatibilité avec les dépendances Hoymiles.

Selon le firmware du DTU, la puissance réseau DDSU et la limite de puissance peuvent ne pas être disponibles par Modbus Ethernet. Elles sont alors indiquées comme non disponibles, sans inventer de valeur.

## Sécurité et confidentialité

- Les réglages personnels, historiques, journaux, fichiers `.env` et caches graphiques sont exclus de Git.
- Cette version ne contient ni mot de passe, ni adresse IP personnelle, ni numéro de série, ni historique utilisateur.
- Ne publiez jamais votre `config_v5.json` ou les exports générés par l'application.
