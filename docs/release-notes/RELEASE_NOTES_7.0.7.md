# Boîte noire Hoymiles v7.0.7

## Rapport DTU enrichi pour le SAV

Le bouton **Diagnostic DTU** reste intégralement en lecture seule. Son rapport ajoute :

- la dernière mesure locale : production PV, puissance réseau DDSU et puissance Linky/Dinky ;
- l'écart instantané DDSU ↔ Linky, lorsqu'une mesure Linky est disponible ;
- la cadence des vingt dernières lectures locales ;
- les informations brutes publiées par le DTU pour le compteur, la passerelle et les entrées PV.

Le rapport n'écrit aucun paramètre dans le DTU, ne redémarre aucun équipement et ne prétend pas mesurer un signal radio non publié par le DTU.
