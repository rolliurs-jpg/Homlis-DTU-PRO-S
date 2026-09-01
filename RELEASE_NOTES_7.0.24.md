# Boîte noire Hoymiles v7.0.24

## Coupures DTU sans perte des autres mesures

- Les lectures Dinky et Shelly sont désormais enregistrées dans le CSV et affichées sans interruption lorsque le DTU ne répond pas.
- Pendant ces périodes, seuls les champs production DTU et réseau DDSU restent vides : aucune valeur artificielle n’est inventée.
- Les cartes de production et DDSU indiquent explicitement « indisponible » au lieu de conserver une ancienne valeur.
- Une indisponibilité DTU inférieure à trois minutes apparaît comme une réponse intermittente ; l’état « hors ligne » est réservé aux coupures plus longues.
- Le curseur emploie le libellé générique « DTU indisponible », valable pour une pause ou une perte de réponse.

Cette correction concerne Windows et macOS.
