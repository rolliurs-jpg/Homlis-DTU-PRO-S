# Boîte noire Hoymiles v7.0.38

## Installation Mac corrigée

- Le lanceur `.command` appelle explicitement `/bin/bash` pour exécuter l’installateur.
- L’application d’installation utilise la même méthode robuste.
- L’installation ne dépend plus du droit d’exécution conservé ou non lors de l’extraction du ZIP.
- Le script interne reste publié avec son mode exécutable Unix.

Les réglages et historiques existants sont conservés pendant la mise à jour.
