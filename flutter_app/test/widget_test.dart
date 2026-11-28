// ignore: deprecated_member_use
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mon_solaire_mobile/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('accepte les adresses privées et refuse le HTTP public', () {
    expect(validateAddress('http://192.168.1.10:8765'), isNotNull);
    expect(validateAddress('http://100.100.10.1:8765'), isNotNull);
    expect(validateAddress('http://example.com:8765'), isNull);
    expect(validateAddress('http://user:password@192.168.1.10'), isNull);
    expect(validateAddress('https://example.com'), isNotNull);
  });
  test('une mesure manquante ne devient pas zéro', () {
    expect(number(null, 'W'), '—');
    expect(number(0, 'W'), '0 W');
  });
  test('la décharge est rouge seulement pour une mesure récente et active', () {
    final now=DateTime(2026,11,27,19,34), timestamp=now.millisecondsSinceEpoch/1000;
    expect(batteryFlowColor({'battery_ac_discharge_w':455,'battery_timestamp':timestamp},'battery_ac_discharge_w',now),dischargeRed);
    expect(batteryFlowColor({'battery_ac_discharge_w':0,'battery_timestamp':timestamp},'battery_ac_discharge_w',now),isNull);
    expect(batteryFlowColor({'battery_ac_discharge_w':455,'battery_timestamp':timestamp-120},'battery_ac_discharge_w',now),isNull);
    expect(batteryFlowColor({'battery_ac_discharge_w':455,'battery_timestamp':timestamp},'battery_ac_discharge_w',now,connected:false),isNull);
    expect(batteryFlowColor({'battery_ac_charge_w':100,'battery_timestamp':timestamp},'battery_ac_charge_w',now),green);
  });
  test('le mois, l’année et les dates viennent du bilan', () {
    expect(monthYear('2026-11-01T00:00:00'), 'novembre 2026');
    expect(shortDate('2025-01-03'), '03/01/2025');
    expect(monthYear(null), isNull);
  });
  testWidgets('la jauge affiche le niveau et distingue charge et mesure ancienne', (tester) async {
    final now = DateTime.now().millisecondsSinceEpoch / 1000;
    await tester.pumpWidget(SolarAppForBattery(current: {'battery_soc_pct': 20, 'battery_timestamp': now, 'battery_ac_charge_w': 120, 'battery_ac_discharge_w': 0}, connected: true));
    expect(find.text('20 %'), findsOneWidget);
    expect(find.text('En charge · 120 W'), findsOneWidget);
    expect(find.text('Niveau mesuré : 20 % · ≈ 1,15 kWh / 5,76 kWh'), findsOneWidget);
    await tester.pumpWidget(SolarAppForBattery(current: {'battery_soc_pct': 20, 'battery_timestamp': now - 120, 'battery_ac_charge_w': 120, 'battery_ac_discharge_w': 0}, connected: true));
    expect(find.text('Dernière mesure · état non actualisé'), findsOneWidget);
    expect(find.text('En charge · 120 W'), findsNothing);
  });
  testWidgets('la validation DTU affiche le temps et la barre', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: DtuWaitIndicator(remainingSeconds: 65))));
    expect(find.text('DTU Pro-S'), findsOneWidget);
    expect(find.text('65 s'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('fermer le dialogue adresse ne détruit pas le contrôleur pendant son animation', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const SolarApp());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Adresse du Raspberry'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'adresse invalide');
    await tester.tap(find.text('Connecter'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.textContaining('Adresse invalide'), findsOneWidget);
  });
  testWidgets('les intitulés restent visibles sur un petit écran', (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const SolarApp());
    await tester.pumpAndSettle();
    expect(find.text('Bilan journalier'), findsOneWidget);
    expect(find.text('Budget mensuel'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('sur ordinateur, la navigation est alignée en bas', (tester) async {
    tester.view.physicalSize = const Size(1280, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const SolarApp());
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('navigation-bas')), findsOneWidget);
    expect(tester.getCenter(find.text('Direct')).dy, tester.getCenter(find.text('Équipements')).dy);
    expect(find.text('Bilan journalier'),findsOneWidget);
    expect(find.text('Budget mensuel'),findsOneWidget);
    expect(tester.takeException(),isNull);
  });
  testWidgets('la démonstration affiche des valeurs fictives et les bilans', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const SolarApp());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Essayer la démonstration'));
    await tester.pumpAndSettle();
    expect(find.text('Démonstration · données fictives'), findsOneWidget);
    expect(find.text('1050 W'), findsOneWidget);
    await tester.tap(find.text('Bilan journalier'));
    await tester.pumpAndSettle();
    expect(find.text('8,20 kWh'), findsOneWidget);
    expect(find.text('Acheté à EDF'), findsOneWidget);
    expect(find.text('3,10 kWh'), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0,-350));
    await tester.pumpAndSettle();
    expect(find.text('Coût EDF'), findsOneWidget);
    expect(find.text('0,98 €'), findsOneWidget);
    expect(find.text('1,48 €'), findsOneWidget);
    expect(find.text('Énergie batterie sur la période'), findsOneWidget);
    await tester.tap(find.text('Budget mensuel'));
    await tester.pumpAndSettle();
    expect(find.text('Budget de ${monthYear(DateTime.now().toIso8601String())}'), findsOneWidget);
    await tester.tap(find.text('Annuel'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Relevés cumulés depuis le 01/01/2026'), findsOneWidget);
    expect(find.text('Achat EDF total · HP + HC'), findsOneWidget);
    expect(find.text('Coût EDF global · abonnement inclus'), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0,-500));
    await tester.pumpAndSettle();
    expect(find.text('Économie solaire + batterie'), findsOneWidget);
    await tester.tap(find.text('Batterie'));
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView).first, const Offset(0,-250));
    await tester.pumpAndSettle();
    expect(find.text('Du plein au lendemain'), findsOneWidget);
    expect(find.text('Fin de décharge batterie'), findsOneWidget);
    expect(find.text('Historique des cycles'), findsOneWidget);
    await tester.tap(find.text('Panneaux'));
    await tester.pumpAndSettle();
    final first=find.byKey(const ValueKey('panneau-Maison-1'));
    final last=find.byKey(const ValueKey('panneau-Cabanon-2'));
    expect(first,findsOneWidget);
    expect(last,findsOneWidget);
    expect(tester.getSize(first),tester.getSize(last));
    expect(find.text('95 W'),findsOneWidget);
    await tester.tap(find.text('Équipements'));
    await tester.pumpAndSettle();
    expect(find.text('Ouvrir le tableau web du Raspberry'),findsNothing);
  });
}

class SolarAppForBattery extends StatelessWidget {
  const SolarAppForBattery({super.key, required this.current, required this.connected});
  final Map current;
  final bool connected;
  @override Widget build(BuildContext context) => MaterialApp(home: Scaffold(body: BatteryLevelCard(current: current, connected: connected)));
}
