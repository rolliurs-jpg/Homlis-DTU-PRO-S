# Essai OpenDTU local — sans modifier l'installation

Ce test ne modifie pas `config_v5.json`, ne contacte pas Hoymiles Cloud et
n'envoie aucune commande aux micro-onduleurs. Il ne fait qu'une lecture locale
de l'API OpenDTU `/api/livedata/status`.

## Préparer le fichier d'essai

Sur le Raspberry, dans `~/solaire`, copier le modèle sous un nom privé :

```bash
cp opendtu_trial.example.json opendtu_trial.json
nano opendtu_trial.json
```

Renseigner seulement l'adresse IP de l'OpenDTU et, si une authentification est
activée, son identifiant et mot de passe. Mettre ensuite `enabled` à `true`.
Ce fichier contient un mot de passe éventuel : il ne doit pas être envoyé ni
ajouté à Git.

## Lancer l'essai

```bash
cd ~/solaire
python3 opendtu_trial.py opendtu_trial.json
```

Un essai réussi affiche `"state": "online"`, le nombre de micro-onduleurs
vus et, lorsque le firmware l'expose sous une forme reconnue, leur puissance
totale. Il n'y a pas de fonction de commande dans ce programme.

## Étape suivante, uniquement après validation

Lorsque l'OpenDTU voit tous les micro-onduleurs et que les puissances sont
cohérentes, son état sera intégré au tableau existant. Ensuite seulement,
une régulation distincte et explicitement activée pourra être construite :
batterie prioritaire, puis limite non persistante après batterie pleine.

La configuration historique `config_v5.json` et le service actif restent
intacts pendant toute cette phase.
