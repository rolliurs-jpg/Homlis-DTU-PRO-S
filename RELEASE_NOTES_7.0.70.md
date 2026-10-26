# Version 7.0.70 — pilotage de puissance suspendu

Cette publication retire toute promesse de zéro-injection piloté automatiquement par le logiciel.

- Le suivi local, les historiques, les alertes, les bilans et le tableau web restent disponibles.
- Le bouton de pilotage automatique est suspendu par défaut et ne peut plus être activé sans validation explicite de l'installation.
- Les commandes DTU externes sont bloquées par défaut, y compris lorsqu'un ancien fichier de réglages les avait activées.
- La documentation rappelle que **Gestion des exportations / Limite de puissance d'exportation** dans Hoymiles/DDSU est un contrôle actif, même avec une valeur faible. Il ne doit jamais fonctionner en parallèle d'un contrôleur externe.
- Une future réactivation exigera une vérification de la puissance réellement obtenue, un retour confirmé à 100 % et une libération complète du DTU pour la maintenance S-Miles.
