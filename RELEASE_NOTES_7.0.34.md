# Boîte noire Hoymiles v7.0.34

## Basculement réel de la bulle du curseur

- Le calcul des deux moitiés du graphique était correct, mais la mauvaise propriété d’alignement Matplotlib était modifiée.
- Dans les 50 % de gauche, la bulle s’affiche maintenant réellement à droite du curseur.
- Dans les 50 % de droite, elle s’affiche réellement à gauche du curseur.
- Le basculement se fait exactement au milieu de la zone du graphique.

Cette correction est commune aux versions Windows et macOS.
