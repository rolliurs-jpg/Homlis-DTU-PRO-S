# Boîte noire Hoymiles v7.0.21 — preuves d’injection

- Détection indépendante de l’injection par la pince réseau Shelly Pro EM.
- Alerte après une injection supérieure à 100 W pendant trois minutes.
- Enregistrement continu de la puissance, de la durée et de l’énergie injectée.
- Cumul persistant en kWh, conservé entre deux démarrages du logiciel.
- Export d’un journal CSV détaillé et d’un résumé texte destiné au SAV Hoymiles.
- Les intervalles sont plafonnés à 180 secondes pour éviter de créer une énergie fictive pendant une interruption du logiciel.

Le journal local est enregistré dans `shelly_injection_log.csv`. Aucun réglage du Shelly, du DTU ou du relais n’est modifié par cette fonction.

