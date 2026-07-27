# Boîte noire Hoymiles 7.0.4

Correctif de fiabilité pour le suivi de la limite DTU.

- la limite affichée est la limite configurée (110 % par défaut) ;
- le champ Wi-Fi `powerLimit`, instable selon certains firmwares DTU, n'est plus utilisé pour le graphique ;
- les valeurs historiques impossibles (plus de 120 %) restent conservées dans le CSV brut, mais ne déforment plus l'affichage ;
- aucune commande n'est envoyée au DTU : l'application reste en lecture seule.
