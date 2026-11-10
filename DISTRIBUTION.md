# Distribution publique et reproductible

Ce dépôt contient tout le code, les installateurs et les modèles nécessaires
pour installer Boîte noire Hoymiles sur Windows, macOS ou Raspberry Pi.

Les archives publiques sont fabriquées depuis une copie propre du dépôt :

```bash
python3 scripts/package_platforms.py
```

Les archives générées sont placées dans `outputs/` et ne sont pas suivies par
Git : elles sont des livrables reproductibles, à publier dans les *Releases*
GitHub. Le code source et les scripts permettant de les recréer sont, eux,
dans GitHub.

## Ce qui est volontairement exclu

Les fichiers suivants restent uniquement sur l'installation de chaque
utilisateur et ne doivent jamais être ajoutés au dépôt ou à une archive :

- `config_v5.json` : adresses, équipements et préférences locales ;
- historiques CSV et dossiers `Historiques_importes/` ;
- journaux, états de surveillance et fichiers `.env` ;
- `esphome/secrets.yaml` et tout mot de passe Wi-Fi ;
- sauvegardes Home Assistant.

Chaque nouvel utilisateur démarre avec `config.example.json`, renseigne ses
propres appareils dans l'interface, puis conserve ses données chez lui.

## Contribution

Les améliorations sont les bienvenues via les Issues et Pull Requests GitHub.
Avant une publication, exécutez les tests de packaging :

```bash
python3 -m unittest -v tests.test_platform_packages tests.test_home_assistant
```
