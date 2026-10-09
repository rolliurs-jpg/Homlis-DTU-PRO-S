# Raspberry Pi : collecteur web permanent recommandé

Cette édition fait tourner la collecte sur un Raspberry Pi relié au réseau de
la maison. Windows, macOS, Android et iOS consultent ensuite le même tableau
dans un navigateur. C'est la configuration recommandée pour une installation
permanente : le Raspberry collecte même lorsque les ordinateurs sont éteints.
Un seul collecteur doit être actif à la fois.

## Sécurité à respecter

- Garder le Raspberry, les téléphones et les ordinateurs sur un réseau privé.
- Ne jamais créer de redirection de port sur la box pour le port `8765`.
- Ne jamais activer **Tailscale Funnel**. Tailscale suffit pour l'accès
  extérieur chiffré.
- Utiliser un compte Tailscale distinct par personne et activer l'authentification
  à deux facteurs sur le compte qui administre le tailnet.
- Protéger les interfaces Wi-Fi des ESP32 et du routeur par WPA2/WPA3, avec des
  mots de passe différents de celui de la box.
- Conserver `config_v5.json`, les CSV, les jetons Tailscale et les mots de passe
  hors de Git. Ils ne doivent jamais être ajoutés ou envoyés sur GitHub.

Le serveur refuse les clients Internet publics dans son code : seuls loopback,
le LAN privé et les plages privées Tailscale sont acceptés. Cette protection ne
remplace pas les règles de la box et de Tailscale.

## Installation en une étape

Ces instructions visent Raspberry Pi OS 64 bits et Python 3.11 ou plus récent.
Téléchargez l’archive **[Raspberry Pi — installateur](https://github.com/rolliurs-jpg/Homlis-DTU-PRO-S/releases/latest/download/3-RASPBERRY-Hoymiles-7.0.64-INSTALLATEUR.tar.gz)** directement sur le Raspberry, puis exécutez :

```bash
cd ~/Downloads
tar -xzf 3-RASPBERRY-Hoymiles-7.0.64-INSTALLATEUR.tar.gz
cd Hoymiles-7.0.64-Raspberry
bash raspberry-pi/INSTALLER_RASPBERRY.sh
```

L’installateur demande le mot de passe administrateur uniquement pour installer
Python et activer le service au démarrage. Il ne demande ni ne transmet de mot
de passe Wi-Fi, et ne contient aucune adresse de votre réseau. Il installe le
logiciel dans `~/solaire`, préserve les données déjà présentes et crée une
configuration locale vierge dans `~/AppData/Local/BoiteNoireHoymiles/`.

Ouvrez ensuite `http://ADRESSE_DU_RASPBERRY:8765/`, allez dans **Équipements**
et activez uniquement les appareils réellement présents (DTU, Dinky, Shelly,
batterie, TP-Link ou ESP32). Après l’enregistrement, relancez le service :

```bash
sudo systemctl restart boite-noire-hoymiles
```

Pour une installation depuis le code source GitHub, le même script est inclus :

```bash
git clone https://github.com/rolliurs-jpg/Homlis-DTU-PRO-S.git ~/solaire-source
cd ~/solaire-source
bash raspberry-pi/INSTALLER_RASPBERRY.sh
```

Sur Raspberry, laissez le réglage web **Démarrage automatique** sur **Non** :
le service systemd ci-dessus est déjà responsable du lancement au démarrage.

## Connexion depuis les autres appareils

Le tableau utilise le port `8765`.

| Appareil | À la maison | À distance privée |
| --- | --- | --- |
| Windows / macOS | `http://IP_DU_RASPBERRY:8765/` | `http://IP_TAILSCALE_DU_RASPBERRY:8765/` |
| Android | Chrome, même adresse | Chrome + Tailscale, même adresse |
| iPhone / iPad | Safari, même adresse | Safari + Tailscale, même adresse |

Pour connaître l'adresse Tailscale du Raspberry :

```bash
tailscale ip -4
```

Si Tailscale n'est pas encore installé sur le Raspberry, installez-le puis
associez-le à votre réseau privé Tailscale :

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Ouvrez le lien de connexion affiché, puis installez Tailscale sur chaque Mac,
PC, téléphone ou tablette avec le même compte. Hors de la maison, l'adresse à
ouvrir est `http://IP_TAILSCALE_DU_RASPBERRY:8765/`. Aucun port de la box ne
doit être ouvert.

Ajoutez ensuite la page à l'écran d'accueil depuis Chrome (Android) ou Safari
(iOS). Sur Android, Chrome propose **Installer l'application** ou **Ajouter à
l'écran d'accueil** dans le menu `⋮`. L'accès Tailscale reste privé et chiffré
; il ne demande aucun port ouvert sur Internet.
