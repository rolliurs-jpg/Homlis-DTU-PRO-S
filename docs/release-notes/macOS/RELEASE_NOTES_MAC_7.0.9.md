# Boîte noire Hoymiles macOS v7.0.9

La version macOS installe le même programme Python que la version Windows et inclut donc toutes les fonctions v7.0.9 : diagnostic DTU en lecture seule, rapport SAV enrichi, export CSV par période, demande de confirmation SAV, captures datées et bilan Linky/Dinky.

L'installateur accepte maintenant Python 3.10 ou plus récent lorsqu'il contient Tkinter. Les distributions Homebrew sans `_tkinter` restent refusées afin d'éviter une installation inutilisable.

Apple Silicon est la plateforme testée. Les Mac Intel peuvent être compatibles avec Python universel et Tkinter, mais restent expérimentaux.
