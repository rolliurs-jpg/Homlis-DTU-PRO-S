# Version 7.0.66 — Raspberry Pi sécurisé en lecture seule

- Le collecteur Raspberry Pi ne transmet plus aucune commande au DTU, aux micro-onduleurs ou à la batterie, même si une ancienne configuration locale avait activé la régulation.
- Le zéro-injection doit être réglé directement dans Hoymiles avec son DDSU/compteur. Le Raspberry conserve le suivi, les historiques, les alertes et le tableau web.
- Le script d’activation de régulation locale est retiré des nouveaux paquets Raspberry.
