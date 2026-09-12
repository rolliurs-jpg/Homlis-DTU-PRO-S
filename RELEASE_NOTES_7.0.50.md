# Version 7.0.50 — équipements au choix

## Choisir les équipements de mesure

Le DTU Hoymiles reste la source de production habituelle. En complément, choisissez
dans le bouton **Équipements** du logiciel :

| Configuration | Utilisation |
| --- | --- |
| Linky / Dinky seul | Solution économique pour lire la téléinformation du Linky et ses index d’achat HC/HP. La production solaire reste fournie par le DTU. |
| Shelly Pro EM seul | Solution plus coûteuse, avec une mesure indépendante de la production et du flux réseau, selon le câblage des deux voies. Le bilan d’achat est une estimation calculée sur les puissances enregistrées. |
| Linky / Dinky + Shelly Pro EM | Index du compteur pour le bilan d’achat et mesures Shelly pour la production indépendante, le flux réseau et les comparaisons. Les deux mesures réseau ne sont jamais additionnées. |

Ces choix concernent les équipements complémentaires : « Dinky seul » ne signifie
pas que le Dinky mesure la production des panneaux. L’injection disponible par
téléinformation dépend des champs publiés par le compteur et le firmware ; une
puissance de soutirage n’est pas une mesure signée d’injection.

Cochez les équipements utilisés, renseignez leur adresse IP ou nom réseau, puis
**Enregistrer**. Fermez et relancez le logiciel pour appliquer le choix. Les réglages
avancés existants et les historiques sont conservés. Les courbes, légendes, bulles,
états et cartes mobiles des équipements désactivés sont masqués. Un équipement
activé qui tombe en panne reste visible : une coupure ne doit pas disparaître de l’écran.

Avec le Shelly seul, le partage HC/HP utilise les plages configurées dans **Tarifs EDF**.
Le calcul porte sur les mesures enregistrées et limite chaque intervalle à trois
minutes : les interruptions de collecte peuvent sous-estimer l’énergie. Il ne
remplace pas les index du compteur ni une facture. Les relevés EDF saisis manuellement
restent identifiés séparément. Les fonctions d’analyse nécessitant le Shelly ne
sont proposées que lorsqu’il est activé ; la comparaison Linky/Hoymiles nécessite le Dinky.

Sur mobile, les cartes maison et flux signé nécessitent les mesures Shelly ; la
carte Dinky affiche sa mesure de téléinformation. Aucun flux d’injection n’est inventé
à partir d’un soutirage nul.

