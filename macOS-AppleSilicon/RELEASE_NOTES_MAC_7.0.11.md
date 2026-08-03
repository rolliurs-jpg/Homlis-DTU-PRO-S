# Boîte noire Hoymiles macOS v7.0.11

Cette version macOS installe exactement le même programme Python que l'édition Windows v7.0.11.

Nouveautés :

- correction de l'affichage local de la limite DTU : toute valeur anormale supérieure à 120 % est remplacée par la référence locale de 110 % ;
- confidentialité renforcée : le diagnostic DTU masque automatiquement les mots de passe, clés Wi-Fi, PSK, jetons et autres secrets avant affichage ou export pour le SAV ;
- aucune commande de réglage ou de redémarrage n'est envoyée au DTU.

Apple Silicon est la plateforme testée. Les Mac Intel restent expérimentaux avec un Python universel contenant Tkinter.
