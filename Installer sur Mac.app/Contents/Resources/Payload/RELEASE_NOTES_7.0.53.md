# Version 7.0.53 — cycle de batterie continu après minuit

- Une décharge commencée le jour où la batterie était pleine reste rattachée au même cycle après minuit.
- Le nouveau jour ne crée plus un second départ artificiel à 00:00 et ne remet plus la durée affichée à zéro.
- Le cycle reste provisoire et continue de cumuler uniquement les intervalles réellement mesurés jusqu'à la recharge.
- Correction commune à Windows et macOS ; réglages et historiques conservés pendant la mise à jour.
