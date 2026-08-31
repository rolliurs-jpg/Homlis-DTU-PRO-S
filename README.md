# Boîte noire Hoymiles — DTU Pro-S, DDSU666, Linky, Dinky 4 et Shelly Pro EM

> **Surveiller localement une installation photovoltaïque Hoymiles et comparer les mesures du DTU/DDSU666 avec les données réelles du Linky.**

[![Version](https://img.shields.io/badge/version-7.0.22-2563eb)](https://github.com/rolliurs-jpg/Homlis-DTU-PRO-S/releases)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-16a34a)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)](https://www.python.org/)

**Boîte noire Hoymiles** est une application Python locale pour Windows et macOS qui réunit, selon les équipements disponibles, un **DTU Pro-S Hoymiles**, le **DDSU666**, un **Linky Téléinfo via Dinky 4 / Tasmota** et les deux pinces d’un **Shelly Pro EM**. Chaque source est facultative selon la configuration, et les données restent sur votre ordinateur.

🌐 **Présentation et guide visuel :** activez GitHub Pages sur le dossier `docs` pour publier la vitrine du projet.

![Suivi v7.0.22 : production Hoymiles, réseau DDSU, Linky Dinky et mesures Shelly Pro EM](docs/assets/suivi-production-v7.png)

## Pourquoi ce logiciel ?

Les données remontées par S-Miles Cloud, le DTU et le DDSU ne correspondent pas toujours à la puissance réellement soutirée au réseau. Cette application permet de conserver un historique local et de comparer, sur la même période :

- la **production photovoltaïque** remontée par le DTU Pro-S ;
- la puissance réseau / estimation du **DDSU666** ;
- la puissance et les index **réels du Linky**, lus par le Dinky 4 ;
- les achats EDF en **heures pleines (HP)**, **heures creuses (HC)** et l’abonnement.

Le Linky/Dinky est la source utilisée pour le bilan EDF. Le DDSU reste affiché comme indicateur technique et de comparaison.

## Fonctionnalités

- Lecture locale du **DTU Pro-S** par Wi-Fi direct ou Modbus TCP en Ethernet.
- Lecture du **Linky Téléinfo** et des index HP/HC avec Dinky 4 / Denky compatible Tasmota.
- Courbes de production PV, réseau DDSU, Linky/Dinky et limite DTU.
- Vues **direct**, **24 h**, **hier** et **historique**.
- Bilan automatique sur 24 h, 7 jours, mois et année.
- Moyenne quotidienne de production photovoltaïque et de consommation réelle Linky/Dinky (HP + HC), calculée à partir des jours avec mesures locales.
- Coût EDF calculé à partir du Linky : HP, HC et abonnement réglables.
- Comparatif énergie **Hoymiles / Linky** pour identifier les écarts DDSU ↔ Linky.
- Lecture locale et strictement en lecture seule des deux voies d’un **Shelly Pro EM**.
- Identification indépendante de la production photovoltaïque et du flux réseau signé : achat EDF positif, injection négative.
- Alerte après une injection supérieure à 100 W pendant trois minutes, sans commander le relais Shelly.
- Alerte d’injection non bloquante : la collecte continue tant que la notification reste ouverte.
- Pendant une pause DTU, le Dinky et le Shelly restent enregistrés ; les courbes DTU sont marquées indisponibles.
- Rupture automatique des courbes lors d’un véritable trou de mesures, sans ligne droite trompeuse.
- Historique indépendant des injections : puissance, durée, Wh/kWh perdus et cumul persistant.
- Export d’un journal CSV et d’un résumé texte utilisables comme preuves auprès du SAV Hoymiles.
- Export CSV filtrable par plage de dates.
- Captures PNG datées et versionnées pour le support Hoymiles.
- Page **Diagnostic DTU** en lecture seule : rapport technique exportable pour le SAV Hoymiles, état observable DDSU ↔ DTU et DTU ↔ micro-onduleurs, dernière mesure locale, écart DDSU ↔ Linky et cadence de lecture récente.
- Chaque export CSV crée aussi une note SAV datée demandant confirmation de réception, résultat de l'analyse et détail des éventuelles corrections appliquées, sans modifier les colonnes du CSV.
- Indicateurs de connexion DTU, Linky/Dinky et Shelly Pro EM.

## Installation rapide Windows

1. Sur cette page, cliquez sur **Code → Download ZIP**, puis décompressez l’archive.
2. Double-cliquez sur **`INSTALLER_WINDOWS.vbs`**.
3. Cochez **DTU-WIFI** (deux cartes Wi-Fi) ou **DTU-LAN** (câble Ethernet, DTU et appareils locaux sur la box).
4. Si un Shelly Pro EM est présent, saisissez son adresse IP. Lors d’une mise à jour, **Non** conserve intégralement sa configuration actuelle.
5. Lancez le raccourci **Boîte noire Hoymiles** créé sur le Bureau.

L’installateur ne laisse pas de fenêtre de terminal ouverte. Il installe les dépendances, sauvegarde les réglages et historiques déjà présents, puis crée le raccourci.

## Installation macOS Apple Silicon

L’édition macOS 7.0.22 se trouve dans le dossier [`macOS-AppleSilicon`](macOS-AppleSilicon). Elle utilise le même moteur et les mêmes fonctions Shelly, injection, bilan et diagnostic que l’édition Windows. Elle est prévue pour les Mac M1, M2, M3 et suivants, sous macOS 13 ou plus récent.

1. Ouvrez `Installer Boîte noire Hoymiles.app` avec un clic droit puis **Ouvrir** lors de la première installation.
2. Choisissez **DTU-LAN** (recommandé) ou **DTU-WIFI** (expérimental), puis configurez séparément les équipements facultatifs Dinky et Shelly.
3. Lancez ensuite l’application depuis le dossier **Applications** et autorisez son accès au réseau local. En dépannage, `LANCER_MAC.command` lance le même logiciel depuis Terminal.

Le mode DTU-WIFI sur Mac demande un second adaptateur Wi-Fi USB réellement compatible macOS / Apple Silicon. Le mode DTU-LAN est à privilégier.

### Prérequis

- Windows 10 ou Windows 11 ;
- Python 3.10 ou plus récent, installé avec l’option **Add Python to PATH** ;
- connexion Internet uniquement lors de la première installation ;
- DTU Pro-S et Dinky accessibles depuis l’ordinateur.

## Réseau : deux configurations possibles

### Configuration A — deux réseaux simultanés

Le **Dinky 4** est relié à la box et l’ordinateur le consulte par le **Wi-Fi de la box**. Le **DTU Pro-S** diffuse son propre Wi-Fi. L’ordinateur doit donc disposer de deux connexions Wi-Fi actives : le Wi-Fi interne vers la box et le Dinky, puis un second adaptateur Wi-Fi USB vers le DTU.

```text
Linky ── Téléinfo ──> Dinky 4 ── Wi-Fi de la box ──> PC
                                                    │
DTU Pro-S ─────────── Wi-Fi propre au DTU ── 2e Wi-Fi du PC
```

### Configuration B — un réseau unique

Si le DTU est raccordé à la box en **Ethernet direct**, ou à une **passerelle configurée en pont Wi-Fi**, le DTU, le Dinky et le Shelly peuvent être sur le même réseau local. L’installateur permet de saisir les adresses IP attribuées par la box. La production PV est alors lue en Modbus TCP (port 502) ; selon le firmware, DDSU et limite de puissance peuvent ne pas être exposés. La passerelle doit fonctionner en pont/client Wi-Fi, sans second serveur DHCP ni double NAT.

```text
Linky ──> Dinky 4 ───────────┐
Shelly Pro EM ───────────────┼── Réseau LAN / Wi-Fi de la box ──> PC ou Mac
DTU Pro-S ─ Ethernet ─ pont Wi-Fi ┘
```

Cette architecture sur un seul LAN est recommandée, notamment sur Mac : tous les appareils restent accessibles sans changer de réseau Wi-Fi.

Réservez si possible les adresses IP du DTU, du Dinky et du Shelly dans la box afin qu’elles ne changent pas après un redémarrage.

### Petite passerelle économique

Le **[TP-Link TL-WR802N](https://www.tp-link.com/fr/home-networking/wifi-router/tl-wr802n/)** convient à cette installation : mode Client/Pont, un port Ethernet 10/100 et alimentation USB. Son débit Wi-Fi 2,4 GHz est très largement suffisant pour le DTU. Il se trouve généralement autour de 25 à 35 €.

Configuration conseillée : **mode Client**, connexion au Wi-Fi 2,4 GHz de la box, puis **Smart IP (DHCP)**. Le DTU se branche sur son port Ethernet et la box reste l’unique serveur DHCP. Le **[TL-WR902AC](https://www.tp-link.com/fr/home-networking/wifi-router/tl-wr902ac/)** est une alternative bi-bande plus chère, utile seulement si le 2,4 GHz est très encombré.

Cette recommandation est indépendante et sans affiliation commerciale.

> Si le Wi-Fi du DTU se coupe, le Dinky peut continuer à enregistrer le Linky mais la production PV ne sera plus relevée jusqu’à la reconnexion du DTU.

## Paramétrage et données locales

Le premier lancement crée :

`%LOCALAPPDATA%\BoiteNoireHoymiles\config_v5.json`

Vous pouvez ensuite fermer le logiciel et modifier l’adresse du DTU, du Dinky, ainsi que les tarifs EDF. Un modèle sans information personnelle est disponible dans [config.example.json](config.example.json).

Les données restent sur votre PC :

| Donnée | Emplacement |
| --- | --- |
| Historique production | `%LOCALAPPDATA%\BoiteNoireHoymiles\hoymiles_log.csv` |
| Index Linky/Dinky | `%LOCALAPPDATA%\BoiteNoireHoymiles\linky_index_log.csv` |
| Preuves d’injection Shelly | `%LOCALAPPDATA%\BoiteNoireHoymiles\shelly_injection_log.csv` |
| Réglages | `%LOCALAPPDATA%\BoiteNoireHoymiles\config_v5.json` |

Sur macOS, les mêmes fichiers se trouvent dans `~/Library/Application Support/BoiteNoireHoymiles`.

Ne publiez jamais votre `config_v5.json`, vos adresses IP, numéros de série ou mots de passe.

## Bilan EDF réel et comparatif DDSU666

Le bilan EDF s’appuie sur les index HP/HC du Linky obtenus par le Dinky. Il ne se base pas sur la puissance DDSU.

![Bilan EDF : production PV, achats HP/HC et abonnement](docs/assets/bilan-edf-v7.png)

Le comparatif distingue volontairement :

| Mesure | Usage dans le logiciel |
| --- | --- |
| Production PV du DTU | Suivi de la génération solaire |
| DDSU666 | Indicateur Hoymiles, comparaison technique |
| Linky/Dinky | Référence pour la consommation et le coût EDF |
| Shelly Pro EM | Mesure indépendante de la production et du flux réseau achat/injection |

Ce projet n’envoie **aucune commande de zéro-injection**. Cette fonction reste gérée par le DTU et/ou S-Miles Cloud. Le Shelly sert de témoin indépendant : le logiciel alerte, cumule et exporte les injections observées, mais ne commande jamais son relais.

## Support et contribution

Vous pouvez ouvrir une [Issue GitHub](https://github.com/rolliurs-jpg/Homlis-DTU-PRO-S/issues) pour signaler une compatibilité DTU, DDSU666, Dinky/Denky ou Linky, ou joindre une capture exportée par l’application.

Pour rester utile à tous, indiquez la version du logiciel, le modèle DTU et le type de Dinky, mais masquez toute donnée personnelle et tout identifiant réseau.

## Soutenir le projet

Le logiciel reste gratuit et accessible à tous. Si son utilisation vous aide et que vous souhaitez soutenir les heures de développement et de tests, vous pouvez faire un don facultatif via [PayPal](https://paypal.me/RolliursHoymiles). Merci.

## Projet communautaire indépendant

Ce projet est indépendant et non affilié à Hoymiles, Enedis, EDF, Tasmota ou S-Miles Cloud. Les valeurs affichées sont des aides de suivi ; elles ne remplacent pas les relevés contractuels d’Enedis ou d’EDF.

## Licence

Licence [MIT](LICENSE).
