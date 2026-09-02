# Boîte noire Hoymiles v7.0.22

Cette correction concerne Windows et macOS.

- L’alerte d’injection Shelly devient non bloquante : fermer la notification n’est plus nécessaire pour poursuivre la collecte.
- Pendant la pause maintenance du DTU, les puissances Dinky et Shelly continuent d’être ajoutées à l’historique principal.
- Les valeurs DTU absentes pendant cette pause sont enregistrées comme indisponibles et non comme des zéros ou des valeurs figées.
- Un trou réel de plus de trois minutes provoque désormais une rupture des courbes au lieu d’une ligne droite trompeuse.
- Le curseur indique clairement « DTU en pause » pour les points concernés.
- Sur macOS, l’installateur crée un lanceur sur le Bureau, propose de démarrer immédiatement, retire la quarantaine après la première autorisation et signe localement le paquet installé.
- Les lanceurs macOS utilisent le logo des panneaux solaires et les boutons de l’application adoptent une forme arrondie sur Mac.
