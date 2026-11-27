# Mon solaire — application Flutter de test

Première version mobile Android/iOS à interface Flutter. Elle lit les données de l'API du tableau solaire existant, sans piloter les appareils. L'adresse du Raspberry est saisie sur le téléphone et enregistrée localement ; aucun appareil personnel n'est configuré par défaut. Un mode démonstration utilise des données fictives.

Les écrans comprennent le direct, les bilans, le budget, les relevés annuels, la batterie, les panneaux et l'état des équipements. Les réglages avancés, la régulation, certains calculs, l'export et le redémarrage ne sont pas encore intégrés : cette version est expérimentale.

Le Raspberry doit être accessible sur le Wi-Fi privé ou via Tailscale. Les adresses HTTP acceptées sont locales ou privées Tailscale. HTTP transporte les données sans chiffrement applicatif : utilisez le réseau privé ou Tailscale. HTTPS est aussi accepté.

## Développement

Installer Flutter stable et les outils Android et iOS, puis :

```sh
flutter pub get
flutter test
flutter run
```

Pour l'APK locale de test : `flutter build apk --debug`. Cette APK est signée avec une clé de débogage ; elle ne constitue pas une version destinée aux boutiques. Pour iOS, ouvrir `ios/Runner.xcworkspace` dans Xcode ou lancer `flutter run` avec un simulateur sélectionné. Une installation sur iPhone ou une distribution exige la signature Apple appropriée.

Ne pas inclure dans une publication les adresses personnelles, mots de passe, fichiers de configuration locaux, clés ou historiques réels. L'ancienne application reste distincte, avec son propre identifiant Android.
