# Boîte noire Hoymiles macOS v7.0.21

Cette mise à jour aligne l’édition macOS sur la version Windows 7.0.21 et conserve les historiques ainsi que la configuration existante.

## Nouveautés principales

- prise en charge locale du Shelly Pro EM à deux voies, strictement en lecture seule ;
- distinction entre production photovoltaïque et flux réseau EDF signé ;
- alerte, durée, énergie et historique persistant des injections détectées ;
- exports CSV et résumé technique pour constituer une preuve destinée au SAV ;
- écrans de suivi, bilan et comparatif réorganisés comme sur Windows ;
- configuration indépendante du DTU, du Dinky et du Shelly ;
- choix explicite **conserver**, **modifier** ou **désactiver** lors d’une mise à jour ;
- autorisation macOS documentée pour l’accès au réseau local.

## Architecture LAN recommandée

Le DTU peut rejoindre le réseau de la box par Ethernet direct ou par une passerelle configurée en pont Wi-Fi. Le Dinky, le Shelly et le Mac restent sur le même LAN. La passerelle ne doit pas créer un second réseau ni faire de double NAT.

Un test réel final sur Mac reste recommandé après installation, notamment pour vérifier l’autorisation Réseau local et l’accès Modbus TCP au DTU.
