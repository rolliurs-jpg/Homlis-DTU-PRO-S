# Boîte noire Hoymiles — v7.0.6

## Liaisons DTU observables dans le diagnostic SAV

Le rapport de diagnostic ajoute :

- l’état observable de la réponse **DDSU ↔ DTU** ;
- la **puissance réseau mesurée par le DDSU** lorsque le DTU la publie ;
- la présence des données **DTU ↔ micro-onduleurs** ;
- les avertissements et codes bruts publiés par le DTU.

Le DTU Pro-S ne transmet pas de niveau de signal radio ni de taux d’erreur
RS485 exploitable. L’application indique donc honnêtement « réponse reçue » ou
« donnée absente », sans inventer une qualité de liaison.
