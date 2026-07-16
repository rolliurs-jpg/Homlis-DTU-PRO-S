# Boîte noire Hoymiles — DTU Pro-S / Dinky 4 / Linky

Application Python locale sous Windows pour suivre une installation Hoymiles : production photovoltaïque, puissance DDSU, limite DTU et consommation réelle du Linky via Dinky/Denky compatible Tasmota.

Version actuelle : **6.7.8**.

> Projet communautaire indépendant, non affilié à Hoymiles, Enedis ou EDF. Aucune commande de zéro-injection n'est envoyée par cette application : ce réglage reste géré par le DTU / S-Miles Cloud.

## Fonctions

- Lecture locale du DTU Pro-S toutes les 60 secondes via `hoymiles-wifi`.
- Lecture de la puissance Linky et des index HC/HP avec un Dinky/Denky Tasmota.
- Historique local CSV, export CSV et lecture de la courbe à la souris.
- Bilan automatique : production PV en kWh, achats EDF HC/HP depuis le Linky, coût estimé et abonnement journalier.
- Graphiques 24 h, semaine, mois et année.
- Tarifs EDF HP/HC et abonnement journalier réglables.
- Indicateurs de connexion DTU et Linky/Dinky.
- Comparatif indépendant Hoymiles (DTU/DDSU) et Linky/Dinky, avec dates/heures de la période analysée.
- Capture PNG de chaque page, datée et portant la version du logiciel, pour les échanges avec le support.

## Installation Windows

1. Téléchargez le dépôt avec **Code → Download ZIP**, puis décompressez-le.
2. Double-cliquez sur `INSTALLER_WINDOWS.cmd`.
3. L'installateur installe les dépendances Python, crée un raccourci sur le Bureau et conserve les données déjà présentes sur le PC.
4. Lancez le raccourci **Boîte noire Hoymiles**.

### Prérequis

- Windows 10 ou Windows 11.
- Python 3.10 ou plus récent, installé avec l'option **Add Python to PATH**.
- DTU Pro-S accessible sur le réseau local.
- Pour le DTU, le paquet `hoymiles-wifi` est installé automatiquement par l'installateur.

## Configuration initiale

Au premier lancement, le fichier suivant est créé :

`%LOCALAPPDATA%\BoiteNoireHoymiles\config_v5.json`

Fermez l'application puis indiquez l'adresse IP du DTU dans `dtu_host`. Pour un Dinky 4, activez `linky.enabled`, choisissez `dinky_http` et indiquez l'adresse IP du Dinky. Un exemple sans données personnelles est fourni dans [config.example.json](config.example.json).

Ne publiez jamais votre propre fichier `config_v5.json` : il contient les adresses IP de votre réseau.

## Bilan EDF réel

Le bilan utilise les index HC/HP du Linky fournis par le Dinky 4. Le DDSU est affiché pour le suivi technique, mais il n'est pas utilisé pour calculer les achats EDF.

Un relevé EDF manuel est un total cumulatif : il est utilisé pour les totaux et coûts mensuels, sans être artificiellement affecté à une seule journée du graphique.

Le graphique affiche :

- à gauche, l'énergie de production PV en kWh ;
- à droite, le coût EDF en euros, réparti entre abonnement, HP et HC.

Les premières valeurs exactes apparaissent dès que le Dinky a enregistré ses index. Laissez l'application ouverte pour conserver une courbe continue.

## Données locales et sauvegarde

Les données restent uniquement sur le PC :

- historique de production : `%LOCALAPPDATA%\BoiteNoireHoymiles\hoymiles_log.csv`
- index Linky : `%LOCALAPPDATA%\BoiteNoireHoymiles\linky_index_log.csv`
- configuration : `%LOCALAPPDATA%\BoiteNoireHoymiles\config_v5.json`

L'installateur sauvegarde ces fichiers avant une mise à jour dans le dossier `sauvegarde_avant_mise_a_jour`.

## Contribution

Les retours de compatibilité DTU, DDSU, Dinky/Denky et Linky sont bienvenus via les **Issues** GitHub. N'ajoutez jamais une IP publique, un numéro de série, un mot de passe ou une configuration personnelle.

## Licence

Licence MIT. Voir [LICENSE](LICENSE).
