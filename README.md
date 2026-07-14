# Boîte noire Hoymiles — DTU Pro-S / Dinky / Linky

Application Python sous Windows pour suivre localement une installation Hoymiles : production AC, puissance réseau DDSU, limite du DTU et, en option, Téléinfo Linky via un Dinky/Denky compatible Tasmota.

Elle propose un historique CSV, une visualisation de production, un bilan d'autoconsommation et d'achat EDF, ainsi qu'une estimation HP/HC réglable par l'utilisateur.

> Ce projet communautaire n'est pas affilié à Hoymiles, Enedis ou EDF. Il n'envoie aucune commande de limitation au DTU : le zéro-injection doit être configuré et contrôlé dans le DTU / S-Miles Cloud.

## Fonctions

- Lecture locale du DTU via la commande `hoymiles-wifi` (toutes les 60 secondes).
- Lecture Dinky/Denky par HTTP Tasmota (`Status 8`) ou TIC TCP existante.
- Historique local CSV, export CSV et consultation à la souris.
- Bilan suivi / jour / semaine / mois / année : PV, autoconsommation et achat EDF.
- Tarifs HP, HC, abonnement et plages HC personnalisables.
- Indicateurs d'état DTU et Linky/Dinky.

## Prérequis

- Windows 10/11 et Python 3.10 ou plus récent.
- Un DTU Pro-S accessible depuis le PC.
- Pour le DTU : l'outil en ligne de commande `hoymiles-wifi` doit être installé et disponible dans le `PATH`.
- Python : `pip install -r requirements.txt`

## Installation et premier démarrage

1. Téléchargez ce dépôt puis décompressez-le.
2. Double-cliquez sur `LANCER.cmd`.
3. Fermez l'application après son premier démarrage : le fichier de configuration est créé dans `%LOCALAPPDATA%\BoiteNoireHoymiles\config_v5.json`.
4. Renseignez au minimum `dtu_host` avec l'adresse IP de votre DTU, puis relancez l'application.

Exemple de configuration : [config.example.json](config.example.json). Ne publiez jamais votre propre `config_v5.json`, car il contient les adresses IP de votre réseau.

## Dinky / Linky

Pour un Dinky/Denky sous Tasmota, activez `linky.enabled`, définissez `mode` sur `dinky_http` et saisissez son adresse IP dans `linky.host`. La valeur lue dépend de la configuration Téléinfo et du compteur ; vérifiez toujours le sens de la puissance réseau avec votre installation.

## Bilan et tarifs

Depuis l'application, ouvrez **Tarifs EDF** et renseignez vos prix HP/HC, abonnement mensuel et plages HC. Le bilan est une estimation locale à partir des mesures collectées, et ne remplace pas la facture EDF.

## Données locales

Les données restent sur le PC :

- historique : `%LOCALAPPDATA%\BoiteNoireHoymiles\hoymiles_log.csv`
- configuration : `%LOCALAPPDATA%\BoiteNoireHoymiles\config_v5.json`

## Contribution

Les retours de compatibilité DTU, DDSU, Dinky/Denky et Linky sont bienvenus via les **Issues** GitHub. Merci de ne jamais joindre d'adresse IP publique, de numéro de série, de mot de passe ou de fichier de configuration réel.

## Licence

Publié sous licence MIT. Voir [LICENSE](LICENSE).
