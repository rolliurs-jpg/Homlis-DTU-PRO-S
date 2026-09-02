# Boîte noire Hoymiles v7.0.17

## Nouveau : consommation maison estimée

La page **Suivi de production** affiche désormais une courbe en vert foncé :
**Consommation maison (estimée)**.

Elle est calculée uniquement à partir des deux mesures indépendantes suivantes :

```
Consommation maison = production PV + puissance nette Linky/Dinky
```

- Linky/Dinky à `0 W` : la consommation de la maison est égale à la production PV.
- Linky/Dinky positif : l'achat EDF s'ajoute à la production PV.
- Linky/Dinky négatif : une éventuelle injection est retirée de la consommation calculée.

Le DDSU n'est volontairement pas utilisé pour cette estimation. Il reste affiché
comme mesure comparative du DTU, mais ne peut pas altérer la lecture issue du
Linky/Dinky.

La valeur est aussi disponible dans la bulle qui suit le curseur sur le graphique.
