# Boîte noire Hoymiles — DTU Pro-S / Dinky 4 / Linky

Application Python locale sous Windows pour suivre une installation Hoymiles : production photovoltaïque, puissance DDSU, limite DTU et consommation réelle du Linky via Dinky/Denky compatible Tasmota.

Version actuelle : **7.0.0**.

> Projet communautaire indépendant, non affilié à Hoymiles, Enedis ou EDF. Aucune commande de zéro-injection n'est envoyée par cette application : ce réglage reste géré par le DTU / S-Miles Cloud.

## Fonctions

- Lecture locale du DTU Pro-S toutes les 60 secondes via `hoymiles-wifi`.
- Lecture de la puissance Linky et des index HC/HP avec un Dinky/Denky Tasmota.
- Historique local CSV, export CSV par plage de dates et lecture de la courbe à la souris.
- Bilan automatique : production PV en kWh, achats EDF HC/HP depuis le Linky, coût estimé et abonnement journalier.
- Graphiques 24 h, 7 derniers jours, mois et année.
- Tarifs EDF HP/HC et abonnement journalier réglables.
- Indicateurs de connexion DTU et Linky/Dinky.
- Comparatif indépendant Hoymiles (DTU/DDSU) et Linky/Dinky, avec dates/heures de la période analysée.
- Capture PNG de chaque page, datée et portant la version du logiciel, pour les échanges avec le support.

## Installation Windows

1. Téléchargez le dépôt avec **Code → Download ZIP**, puis décompressez-le.
2. Double-cliquez sur `INSTALLER_WINDOWS.vbs`.
3. Confirmez l'installation puis choisissez le réseau du DTU au premier passage. L'installateur travaille sans fenêtre de terminal, installe les dépendances Python, crée un raccourci sur le Bureau et conserve les données déjà présentes sur le PC.
4. Lancez le raccourci **Boîte noire Hoymiles**.

### Prérequis

- Windows 10 ou Windows 11.
- Python 3.10 ou plus récent, installé avec l'option **Add Python to PATH**.
- DTU Pro-S accessible sur le réseau local.
- Une connexion Internet est nécessaire lors de la première installation, afin d'installer `matplotlib` et `hoymiles-wifi`.

## Configuration initiale

Au premier lancement, le fichier suivant est créé :

`%LOCALAPPDATA%\BoiteNoireHoymiles\config_v5.json`

Fermez l'application puis indiquez l'adresse IP du DTU dans `dtu_host`. Pour un Dinky 4, activez `linky.enabled`, choisissez `dinky_http` et indiquez l'adresse IP du Dinky. Un exemple sans données personnelles est fourni dans [config.example.json](config.example.json).

Ne publiez jamais votre propre fichier `config_v5.json` : il contient les adresses IP de votre réseau.

## Réseaux nécessaires : DTU et Dinky ne sont pas sur le même réseau

La configuration testée par ce projet utilise **deux réseaux distincts**, accessibles en même temps par l'ordinateur :

- Le **Dinky 4** est connecté à la box Internet. Il lit la Téléinfo du Linky et fournit au logiciel la puissance et les index HC/HP via le réseau local de la maison.
- Le **DTU Pro-S** diffuse son propre réseau Wi-Fi. L'ordinateur s'y connecte directement pour lire les données locales du DTU ; ce réseau n'a généralement pas accès à Internet.

Il faut donc deux connexions simultanées : par exemple le Wi-Fi interne (ou Ethernet) vers la box et le Dinky, et un second adaptateur Wi-Fi USB vers le DTU. Sur un Mac ou un PC disposant de deux interfaces Wi-Fi, le principe est identique.

```text
Linky ──Téléinfo──> Dinky 4 ──réseau de la box──> ordinateur
                                                     │
DTU Pro-S ──son propre Wi-Fi─────────────────────────┘
```

Si l'adaptateur Wi-Fi du DTU se déconnecte, le Dinky peut continuer à enregistrer le Linky mais la production DTU n'est plus lue jusqu'à la reconnexion.

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
