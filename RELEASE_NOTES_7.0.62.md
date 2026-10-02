# Version 7.0.62 — gestion solaire et ESP32

- Fenêtre classique : adresses et disponibilité des deux ESP32, état de régulation, arrêt/reprise et accès au tableau de bord.
- Régulation locale coordonnée du HMS 1000 W via ESPHome Bluetooth et du micro-onduleur 2000 W via DTU-Pro-S Modbus. Activation explicite uniquement ; désactivée par défaut pour une nouvelle installation.
- Priorité à la maison et à la charge batterie. Plein confirmé pendant 120 secondes avant réduction. Retour à 100 % demandé en cas de mesures absentes, reprise de charge/décharge ou arrêt, si la liaison répond. L’ordinateur doit rester actif.
- DTU : commandes temporaires uniquement ; limites lues par les quatre ports. Vérification matérielle à 90 % puis retour à 100 % sur Windows.
- Affichage des six panneaux ; les deux panneaux du HMS partagent la limite commune du micro-onduleur.
- Batterie : mesures fraîches, charge/décharge AC, énergie du jour, sélection et rafraîchissement des cycles. Les événements non observés ne sont pas inventés.
- Archives Windows et Mac synchronisées avec les nouveaux modules. Extraction et autorisations Mac contrôlées ; installation réelle et pilotage sur Mac restent à valider. Android utilise le tableau de bord du collecteur : essai réel sur téléphone à effectuer.

L’appairage requiert Python 3.11+ et un proxy ESPHome actif. Renseigner `hoymiles_proxy.host`, `address` et `serial_tail` dans la configuration locale puis exécuter `PAIRER_HOYMILES.py`. Le code Bluetooth est saisi localement ; la configuration privée n’est jamais incluse dans les paquets.
