# Ventilation du Raspberry Pi 4

Le collecteur peut fonctionner en continu : une ventilation automatique est
donc conseillée dans un boîtier fermé ou près d'équipements solaires.

## Réglage recommandé

Sur le Raspberry, lancez :

```bash
sudo raspi-config
```

Choisissez **Performance Options** puis **Fan** (ou **Ventilateur**, selon la
langue). Activez le ventilateur et indiquez le GPIO précisé par la notice de
votre boîtier. Pour un boîtier Raspberry Pi officiel compatible Pi 4, ce GPIO
est généralement proposé automatiquement ; ne le modifiez pas sans la notice
du boîtier.

Réglez le démarrage vers **60 °C** : c'est un compromis silencieux et prudent
pour un Pi 4 qui reste allumé jour et nuit. Le ventilateur s'arrête de lui-même
lorsque la température redescend.

## Vérifier la température

```bash
vcgencmd measure_temp
```

En usage normal, rester sous 70 °C est confortable. Vers 80 °C, le Raspberry
peut réduire automatiquement sa fréquence pour se protéger.

Si votre boîtier possède son propre interrupteur ou une carte de contrôle, sa
notice prévaut : ce guide n'envoie aucune commande au ventilateur tant que vous
n'avez pas activé l'option dans `raspi-config`.
