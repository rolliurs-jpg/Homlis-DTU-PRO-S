# Boîte noire Hoymiles v7.0.39

## Accès au réseau local sur Mac corrigé

- Le lanceur `.app` reste actif comme processus parent de Python afin que macOS conserve l’identité de l’application et lui attribue correctement l’accès au réseau local.
- L’adresse `192.168.1.105` du Shelly Pro EM est maintenant proposée par défaut pendant l’installation.
- Les trois adresses du réseau unique restent configurables et les réglages existants sont conservés.

Le fonctionnement depuis Terminal ayant validé le réseau, cette correction reproduit dans le lanceur le mode d’exécution reconnu par macOS.

## Validation macOS 27.0

macOS 27.0 peut néanmoins bloquer un lanceur communautaire non signé par un compte Apple Developer et renvoyer `No route to host`. La procédure officielle Apple pour autoriser le sous-réseau Wi-Fi local est maintenant documentée dans le README, le guide Mac et le site. Après ajout de `192.168.1.0/24` puis redémarrage, le lancement depuis `/Applications` a été validé avec le DTU, le Dinky et le Shelly.
