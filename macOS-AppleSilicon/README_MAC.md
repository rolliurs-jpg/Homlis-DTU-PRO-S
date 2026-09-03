# Boîte noire Hoymiles v7.0.40 — macOS Apple Silicon

La version Mac utilise uniquement la configuration stable à **réseau unique**. Le DTU est relié en Ethernet à un nano-routeur en mode Client/Pont ; le Mac, le Dinky et le Shelly restent sur le Wi-Fi de la box. Il n’y a plus d’option Wi-Fi direct du DTU dans l’installateur Mac.

## Avant l’installation

1. Configurez le nano-routeur sur le Wi-Fi 2,4 GHz de la box en mode **Client/Pont** et **Smart IP (DHCP)**.
2. Reliez le DTU au port Ethernet du nano-routeur.
3. Vérifiez dans la box que le DTU, le Dinky et le Shelly ont chacun une adresse IP, puis réservez ces adresses.
4. Vérifiez que le port Modbus TCP `502` du DTU est accessible. Sur l’installation testée, le port RS485 est réglé sur **Remote Control / Modbus Protocol**, adresse `101`.

Selon le firmware Hoymiles, le mode Modbus peut rendre le DDSU et la gestion d’exportation Hoymiles indisponibles. Vérifiez votre dispositif de zéro-injection avant de conserver ce réglage.

## Installation

1. Téléchargez et décompressez le ZIP GitHub.
2. Ouvrez le dossier `macOS-AppleSilicon`.
3. Faites un clic droit sur `Installer Boîte noire Hoymiles.app`, puis choisissez **Ouvrir**.
4. Saisissez l’adresse IP du DTU, puis configurez si nécessaire le Dinky et le Shelly.
5. Choisissez **Lancer maintenant** à la fin.

Le lanceur ouvre le script avec `/bin/bash` et reste actif comme processus parent. macOS conserve ainsi l’identité de l’application pour l’autorisation réseau locale, même si le ZIP retire le droit d’exécution du script interne.

### Si macOS affiche « No route to host »

Sous macOS 15.5 ou plus récent, un lanceur communautaire sans signature Apple Developer peut être bloqué alors que les mêmes appareils répondent depuis Terminal. Pour autoriser le réseau Wi-Fi local `192.168.1.x`, exécutez :

```bash
sudo defaults write com.apple.network.local-network AllowedWiFiLocalNetworkAddresses -array-add "192.168.1.0/24"
```

Le mot de passe administrateur reste invisible pendant sa saisie. Redémarrez complètement le Mac, puis ouvrez le logiciel depuis `/Applications`. Cette exception système autorise toutes les applications à joindre le sous-réseau `192.168.1.x`. Elle a été validée avec macOS 27.0. Référence : [Apple TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy).

L’installateur crée un seul lanceur dans `/Applications` et un raccourci sur le Bureau. Le logo des panneaux solaires est utilisé et les boutons gardent la forme rectangulaire de Windows.

Les mises à jour conservent les réglages et historiques dans :

`~/Library/Application Support/BoiteNoireHoymiles`

Le paquet communautaire n’est pas notarisé avec un compte Apple Developer. La première ouverture peut nécessiter **clic droit → Ouvrir** et une autorisation d’accès au réseau local. L’installateur retire ensuite la quarantaine et applique une signature locale au lanceur installé.

## Tableau de bord mobile et accès Tailscale

Le logiciel démarre un tableau mobile en lecture seule sur le port `8765`. Cliquez sur **Mobile** pour l’ouvrir et connaître l’adresse à saisir sur le téléphone.

- À la maison : `http://ADRESSE_DU_MAC:8765` sur le même Wi-Fi.
- À distance : installez [Tailscale](https://tailscale.com/download) sur le Mac et le téléphone, connectez-les au même compte, puis ouvrez `http://ADRESSE_TAILSCALE_DU_MAC:8765`.

L’adresse Tailscale commence généralement par `100.`. Aucun port de la box ne doit être ouvert et Tailscale Funnel ne doit pas être activé. Le Mac, l’application et Tailscale doivent rester actifs pendant l’absence.

## Nettoyer d’anciennes installations

Si Launchpad montre plusieurs anciennes icônes, supprimez les anciens dossiers téléchargés contenant une copie des applications et l’ancienne copie éventuelle dans `~/Applications`. Conservez seulement `/Applications/Boîte noire Hoymiles.app` et ne supprimez pas le dossier `Application Support/BoiteNoireHoymiles` si vous souhaitez garder les données.

## Compatibilité

- macOS 13 ou plus récent ;
- Mac Apple Silicon M1, M2, M3 ou suivant ;
- Python 3.10 ou plus récent avec Tkinter, de préférence depuis [python.org](https://www.python.org/downloads/macos/).

Mac Intel reste non testé par la communauté.

## Lecture du graphique

- bleu foncé pur : production PV en trait plein ;
- vert : Linky/Dinky en tirets ;
- jaune lumineux : production Shelly en trait mixte et réseau EDF mesuré par le Shelly en pointillés renforcés ;
- rouge : réseau DDSU ;
- bleu foncé : limite du DTU.

Le curseur utilise les mêmes couleurs pour regrouper immédiatement les valeurs comparables.

La zone située sous 0 W reste transparente. La mention **injection vers le réseau** est placée à gauche pour ne pas masquer les mesures récentes à droite.

La boîte multicolore du curseur reste à l’intérieur du graphique, sous les titres et la légende, avec un fond presque opaque pour préserver la lisibilité.

Dans la moitié gauche du graphique elle s’ouvre vers la droite ; dans la moitié droite elle s’ouvre vers la gauche. La version 7.0.34 corrige l’alignement interne Matplotlib afin que ce basculement soit réellement appliqué.

Lorsque l’injection dépasse −500 W, l’échelle verticale descend automatiquement avec une marge afin de conserver la courbe complète à l’écran.
