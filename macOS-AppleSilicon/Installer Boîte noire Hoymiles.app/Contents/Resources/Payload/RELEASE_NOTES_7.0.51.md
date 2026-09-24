# Version 7.0.51 — Batterie Zendure et seconde production

Dans Équipements, activez Batterie Zendure 2400 AC et saisissez son adresse IP, puis enregistrez et relancez le logiciel.
Le Smart Meter reste piloté par Zendure ; les échanges EDF de notre logiciel restent mesurés par le Shelly et le Dinky.

Le bouton Batterie / PV 2 ouvre le suivi réel : niveau, charge/décharge, entrée AC, restitution AC, cumuls journaliers et mensuels et export CSV. Lecture toutes les 15 secondes, sans modifier les réglages de charge. Le niveau apparaît sur le bouton après connexion.

À réception du Shelly EM Gen3, branchez sa pince sur le canal 0, puis activez Shelly EM Gen3 — production 2 dans Équipements et indiquez son IP. La case d’inversion concerne uniquement cette pince de production. Cochez « Toutes les lignes solaires sont mesurées par les Shelly » seulement lorsque les deux productions sont effectivement mesurées.

La consommation maison du tableau mobile se calcule côté AC : production totale + achat net réseau + restitution batterie − entrée AC batterie. Tant que les mesures nécessaires manquent, elle reste indisponible. Les courbes existantes DTU et premier Shelly conservent leur source ; la seconde production est consultable dans Batterie / PV 2.

Les mesures batterie sont conservées dans batterie_production2.csv, indépendamment des historiques précédents. Pas de reconstruction des jours passés. Les interruptions de plus de 45 secondes ne sont pas extrapolées. Les cumuls batterie sont des mesures côté batterie ; entrée et restitution AC sont des mesures différentes, également enregistrées. Ils ne sont pas présentés comme des économies EDF garanties.

Avec la batterie activée, Rapport + batterie ouvre les mesures réelles : l’ancienne simulation de dimensionnement n’est plus appliquée au surplus déjà réduit par la batterie. La facturation HP/HC reste fondée sur les index Dinky existants.

Windows : décompressez tout le ZIP puis lancez INSTALLER_WINDOWS.vbs.
Mac : décompressez tout le ZIP puis utilisez l’installateur dans macOS-AppleSilicon. Si macOS bloque le .command, ouvrez Terminal, tapez /bin/bash suivi d’un espace, glissez installer_mac.sh depuis ce nouveau dossier, puis Entrée (méthode déjà utilisée avec succès). Conservez le dossier complet.

La configuration et les historiques existants sont conservés. Réservez si possible les IP dans la box.

Validation : 31 tests automatisés réussis, affichage de bureau contrôlé et décodage vérifié sur une réponse réelle du SolarFlow 2400 AC. La lecture du Shelly EM Gen3 reste à valider sur le matériel à réception.

Correctif installateur Windows : suppression du BOM UTF-8 incompatible avec VBScript (erreur 800A0408 ligne 1). Script ASCII sans BOM.
