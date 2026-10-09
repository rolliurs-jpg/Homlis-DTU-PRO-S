# Version 7.0.65 — régulation zéro-injection Raspberry Pi

- Ajout d’un script d’activation explicite de la régulation locale sur Raspberry Pi. Il pilote les deux panneaux Bluetooth et les quatre panneaux DTU après confirmation du plein batterie.
- Le script vérifie que le DTU Modbus est accessible, sauvegarde la configuration avant modification et laisse le contrôleur revenir à 100 % en cas de mesure incomplète ou de commande DTU non confirmée.
- Aucun pilotage n’est activé dans une installation neuve sans action volontaire de l’utilisateur.
