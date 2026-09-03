# Boîte noire Hoymiles v7.0.39

## Accès au réseau local sur Mac corrigé

- Le lanceur `.app` reste actif comme processus parent de Python afin que macOS conserve l’identité de l’application et lui attribue correctement l’accès au réseau local.
- L’adresse `192.168.1.105` du Shelly Pro EM est maintenant proposée par défaut pendant l’installation.
- Les trois adresses du réseau unique restent configurables et les réglages existants sont conservés.

Le fonctionnement depuis Terminal ayant validé le réseau, cette correction reproduit dans le lanceur le mode d’exécution reconnu par macOS.
