# Boîte noire Hoymiles — DTU Pro-S, Linky/Dinky et Shelly Pro EM

> Application locale Windows et macOS pour comparer la production Hoymiles, le compteur Linky et les mesures indépendantes du Shelly.

[![Version](https://img.shields.io/badge/version-7.0.28-2563eb)](RELEASE_NOTES_7.0.28.md)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-16a34a)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)](https://www.python.org/)

**[Télécharger la dernière version Windows et Mac](https://github.com/rolliurs-jpg/Homlis-DTU-PRO-S/archive/refs/heads/main.zip)** · [Site du projet](https://rolliurs-jpg.github.io/Homlis-DTU-PRO-S/)

![Suivi de production](docs/assets/suivi-production-v7.png)

## Choisir la bonne version réseau

| Système | Configuration proposée | Usage |
| --- | --- | --- |
| Windows | **Deux connexions Wi-Fi** | Wi-Fi interne vers la box/Dinky/Shelly et seconde antenne Wi-Fi vers le DTU. |
| Windows | **Réseau unique nano-routeur/LAN — recommandé** | DTU en Ethernet sur le nano-routeur Client/Pont ; PC, Dinky et Shelly sur la box. |
| macOS Apple Silicon | **Réseau unique nano-routeur/LAN uniquement** | Même réseau pour tous les appareils, sans changement de Wi-Fi sur le Mac. |

Le choix se fait pendant l’installation Windows. L’installation Mac demande directement l’adresse IP du DTU sur le réseau unique.

## Installation Windows

1. Téléchargez et décompressez le ZIP.
2. Double-cliquez sur `INSTALLER_WINDOWS.vbs`.
3. Choisissez l’une des deux configurations réseau du tableau ci-dessus.
4. Saisissez les adresses IP demandées, puis lancez le raccourci créé sur le Bureau.

Une mise à jour conserve les réglages et historiques existants. Python 3.10 ou plus récent est requis.

## Installation macOS Apple Silicon

1. Configurez d’abord le nano-routeur en **mode Client/Pont** sur le Wi-Fi 2,4 GHz de la box.
2. Reliez le port Ethernet du DTU au nano-routeur.
3. Dans le ZIP, ouvrez `macOS-AppleSilicon`.
4. Faites un clic droit sur `Installer Boîte noire Hoymiles.app`, puis choisissez **Ouvrir**.
5. Saisissez les IP réservées du DTU, du Dinky et du Shelly.

L’installateur place un seul lanceur dans `/Applications` et un raccourci sur le Bureau. Les données sont conservées dans `~/Library/Application Support/BoiteNoireHoymiles`. Voir le [guide Mac détaillé](macOS-AppleSilicon/README_MAC.md).

Le paquet communautaire n’est pas notarisé par Apple. La première ouverture peut donc demander une validation et l’autorisation d’accéder au réseau local.

## Réseau unique recommandé

```text
DTU Pro-S ── Ethernet ──> nano-routeur en mode Client/Pont ── Wi-Fi ──┐
Linky ── Téléinfo ──> Dinky 4 ─────────────────────────────── Wi-Fi ──┼──> Box ──> Windows ou Mac
Shelly Pro EM ─────────────────────────────────────────────── Wi-Fi ──┘
```

Le **[TP-Link TL-WR802N](https://www.tp-link.com/fr/home-networking/wifi-router/tl-wr802n/)** convient : choisissez **Client** puis **Smart IP (DHCP)**. La box doit rester l’unique serveur DHCP. Réservez ensuite une IP fixe au DTU, au Dinky et au Shelly dans la box.

Pour lire localement la production par Modbus TCP, le port 502 du DTU doit être accessible. Sur l’installation testée, cela correspond au réglage RS485 **Remote Control / Modbus Protocol**, adresse `101`. Attention : selon le firmware Hoymiles, ce choix peut rendre le DDSU et la gestion d’exportation Hoymiles indisponibles. Si votre zéro-injection dépend du DDSU, vérifiez son fonctionnement avant de conserver ce réglage.

## Fonctions principales

- production photovoltaïque locale par DTU Pro-S (Wi-Fi direct Windows ou Modbus TCP sur LAN) ;
- puissance et index HP/HC du Linky par Dinky 4 ;
- deux voies Shelly Pro EM en lecture seule : production et achat/injection réseau ;
- vues direct, 24 h, hier et historique ;
- bilan EDF fondé sur les index Linky, export CSV, captures et rapport SAV ;
- continuité des mesures Dinky/Shelly lorsque le DTU est momentanément indisponible ;
- seconde tentative automatique du Dinky avant de signaler une coupure ;
- couleurs regroupées par source : production PV et Linky/Dinky en bleu ciel, les deux mesures Shelly en violet, DDSU en rouge et limite DTU en bleu foncé ;
- curseur organisé avec les mêmes couleurs de groupe pour faciliter la comparaison ;
- zone négative identifiée clairement : toute valeur sous 0 W correspond à une injection vers le réseau ;
- boîte du curseur placée dans le graphique, sous les titres et la légende, avec un fond renforcé ;
- alerte et cumul de l’injection mesurée par le Shelly.

Le logiciel ne commande ni le relais Shelly ni le zéro-injection Hoymiles.

## Données locales

| Système | Dossier |
| --- | --- |
| Windows | `%LOCALAPPDATA%\BoiteNoireHoymiles` |
| macOS | `~/Library/Application Support/BoiteNoireHoymiles` |

Ne publiez jamais `config_v5.json`, vos adresses IP, numéros de série ou mots de passe. Un modèle neutre est fourni dans [config.example.json](config.example.json).

## Support, licence et indépendance

Signalez un problème dans les [Issues GitHub](https://github.com/rolliurs-jpg/Homlis-DTU-PRO-S/issues) en indiquant la version, le modèle de DTU et une capture sans donnée personnelle.

Le logiciel est distribué sous [licence MIT](LICENSE). C’est un projet communautaire indépendant, non affilié à Hoymiles, Enedis, EDF, Tasmota, S-Miles Cloud ou TP-Link. Un [don facultatif](https://paypal.me/RolliursHoymiles) peut soutenir son développement.
