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

## Installation

Ces instructions visent Raspberry Pi OS 64 bits et Python 3.11 ou plus récent.
Adapter `solar` et `/home/solar/solaire` à votre installation.

```bash
sudo apt update
sudo apt install -y git python3-venv
git clone https://github.com/rolliurs-jpg/Homlis-DTU-PRO-S.git /home/solar/solaire
cd /home/solar/solaire
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Créez ensuite la configuration locale à partir de `config.example.json`. Ne
publiez jamais cette copie : elle contient les adresses de votre installation.
Activez seulement les équipements réellement présents.

Pour lancer automatiquement le collecteur au démarrage, copiez
`boite-noire-hoymiles.service.example` vers
`/etc/systemd/system/boite-noire-hoymiles.service`, remplacez
`YOUR_LINUX_USER`, puis exécutez :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now boite-noire-hoymiles.service
sudo systemctl status boite-noire-hoymiles.service
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
