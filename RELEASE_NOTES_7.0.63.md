# Version 7.0.63 — Raspberry Pi téléchargeable et suivi du nano-routeur

- Ajout d’une archive Raspberry Pi autonome, téléchargeable depuis la page des versions GitHub. Elle contient un installateur, le service systemd et le guide dédié.
- Le paquet Windows 7.0.63 contient les mêmes évolutions du collecteur et du tableau : suivi du TP-Link, bilan batterie corrigé et réglages de démonstration neutres.
- L’archive ne contient aucune configuration active, adresse de réseau locale, mot de passe, historique CSV, jeton ou clé Bluetooth. La configuration est créée localement au premier lancement.
- Le tableau **Équipements** affiche maintenant le TP-Link en mode Client/Pont : il permet de distinguer une panne du pont Wi-Fi d’une panne du DTU.
- Le suivi batterie conserve la dernière fin solaire confirmée même si une mesure manque plus tard et affiche le bilan quotidien quand le plein n’a pas été observé.
- Le site et le README indiquent le téléchargement Raspberry et l’installation en une commande.
