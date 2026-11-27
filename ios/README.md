# Mon solaire pour iOS — prototype

Ouvrir `MonSolaire.xcodeproj` dans Xcode, installer une plateforme iOS dans les composants Xcode, puis choisir un simulateur iPhone et lancer le projet. La touche « Démo » ouvre des données fictives. Pour l'installation réelle, saisir l'adresse de son propre tableau Raspberry Pi, par exemple `http://adresse-du-raspberry:8765`. Les commandes affichées agissent sur cette installation réelle.

La connexion HTTP locale est nécessaire à la compatibilité actuelle : utiliser un réseau privé de confiance ou Tailscale, sans exposer le port sur Internet. Le tableau collecte des données et permet des commandes ; le mot de passe envoyé en HTTP sur un Wi-Fi local non fiable n'est pas chiffré par l'application. Aucun serveur personnel n'est configuré par défaut.

Le prototype initial a été essayé sur simulateur ; la démo et le fonctionnement sur iPhone physique nécessitent encore des essais. Une distribution iPhone ou App Store nécessite la signature, les tests sur appareil et le respect des exigences Apple. Les données, les réglages et les protections restent ceux du tableau hébergé sur le Raspberry.
