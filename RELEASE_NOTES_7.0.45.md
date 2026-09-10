# Version 7.0.45 — alarmes du suivi

Cette mise à jour ajoute une surveillance commune à Windows, macOS et au tableau mobile Solaire.

- Bouton **Alarmes** : état du suivi, configuration de l’alerte extérieure et dernière interruption observée.
- Alarme locale après 5 minutes sans aucune mesure valide enregistrée dans le CSV. Une valeur de 0 W reste valide ; les pannes partielles restent affichées par appareil.
- Fenêtre d’alarme non modale et signal sonore système si l’interface peut encore fonctionner. Une interface bloquée ne peut pas afficher sa propre alarme : la surveillance extérieure couvre ce cas.
- Journal local `interruptions_suivi.jsonl`, avec interruption et reprise. Au lancement, la dernière mesure valide de l’historique permet de détecter un arrêt prolongé.
- Bandeau d’alarme sur le tableau mobile ouvert, y compris lorsque l’ordinateur devient inaccessible. Il indique que les anciennes valeurs ne sont plus des mesures en direct.
- Connexion facultative à Healthchecks.io : un signal sans données énergétiques est envoyé uniquement après un enregistrement valide. Aucun signal n’est envoyé pour de simples lignes vides ou pour un historique relu au démarrage.

## Installer

Décompresser le paquet complet. Windows : lancer `INSTALLER_WINDOWS.vbs`. Mac : utiliser l’installateur du dossier `macOS-AppleSilicon`. Les installateurs copient aussi `monitoring.py`. Fermer puis relancer le logiciel pour charger la nouvelle version ; vérifier **v7.0.45** dans le titre. Actualiser ensuite le tableau mobile.

## Activer les notifications quand l’ordinateur est éteint

1. Créer un contrôle sur https://healthchecks.io/ avec un nom explicite, par exemple « Suivi solaire PC maison ».
2. Choisir une périodicité simple : **Period = 1 minute**, **Grace Time = 4 minutes**. Ce réglage donne un seuil d’environ cinq minutes après le dernier signal reçu, auquel s’ajoute le délai de livraison de la notification.
3. Configurer le destinataire et le canal de notification dans Healthchecks. Le logiciel ne crée ni compte ni abonnement.
4. Dans **Alarmes**, coller l’URL privée `https://hc-ping.com/<identifiant>` et enregistrer. Ne pas publier cette URL dans GitHub, un rapport ou une capture.
5. Attendre une nouvelle mesure ; vérifier la réception du signal dans Healthchecks puis tester le canal de notification.
6. Lors d’un créneau approprié, arrêter le logiciel plus de cinq minutes et vérifier la réception de l’alerte. Relancer et vérifier le retour à la normale.

Créer un contrôle différent par ordinateur : partager un contrôle entre PC et Mac masquerait la panne de l’un si l’autre fonctionne encore. Pour un arrêt volontaire prolongé, mettre le contrôle en pause dans Healthchecks, puis le réactiver à la reprise. Vider l’URL dans le logiciel arrête les envois mais ne met pas le contrôle distant en pause.

Une coupure de courant, une fermeture du logiciel, une mise en veille, un arrêt du système ou une panne Internet peuvent produire la même absence de signal. La notification signale l’interruption, sans en inventer la cause. Le téléphone doit lui-même avoir une connexion pour recevoir la notification.

L’appli Solaire reste un tableau web hébergé sur l’ordinateur. Elle n’émet pas à elle seule de notification en arrière-plan lorsque ce serveur est éteint : cette partie exige le service extérieur et un canal de notification configuré. Sans configuration, les alarmes locales sont disponibles mais aucune notification distante n’est promise.

## Vérifications de cette préparation

14 tests Python réussis, dont les tests énergétiques existants ; 4 scénarios JavaScript pour le bandeau mobile. Compilation des modules Python et rendu du tableau principal vérifiés. Tests réalisés avec horloge et envoi réseau simulés, sans accès aux appareils réels. L’installation sur un Mac réel et la livraison d’une notification sur téléphone restent à valider.

Documentation du service : https://healthchecks.io/docs/ et https://healthchecks.io/docs/configuring_checks/
