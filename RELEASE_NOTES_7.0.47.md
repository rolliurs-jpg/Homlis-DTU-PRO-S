# Version 7.0.47 — installateur Mac autonome

Corrige le faux message « Dossier incomplet » lorsque macOS lance l’installateur à un emplacement isolé. Tous les fichiers nécessaires sont maintenant intégrés dans `Installer sur Mac.app/Contents/Resources/Payload` ; l’application ne cherche plus de dossier voisin.

Le parcours reste un double-clic et des fenêtres graphiques. La première autorisation Apple peut rester nécessaire. Les tests exécutent la vérification des ressources depuis une copie isolée de l’application, hors du dossier du projet, et contrôlent que les fichiers embarqués correspondent aux sources.
