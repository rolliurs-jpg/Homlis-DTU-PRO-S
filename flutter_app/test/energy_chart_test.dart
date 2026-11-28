// ignore: deprecated_member_use
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mon_solaire_mobile/energy_chart.dart';

void main() {
  test('les courbes utilisent les mesures et distinguent charge et décharge', () {
    final charging = {'production_w':250,'consumption_w':100,'import_w':20,'export_w':0,'battery_charge_w':80,'battery_discharge_w':0};
    final discharging = {'battery_charge_w':0,'battery_discharge_w':45};
    expect(energyValue(charging,EnergySeries.production),250);
    expect(energyValue(charging,EnergySeries.house),100);
    expect(energyValue(charging,EnergySeries.charge),80);
    expect(energyValue(charging,EnergySeries.discharge),isNull);
    expect(energyValue(discharging,EnergySeries.discharge),-45);
    expect(energyValue({'battery_charge_w':3},EnergySeries.charge),isNull);
    expect(energyValue({},EnergySeries.exported),isNull);
  });
  testWidgets('la légende permet d’isoler et de rétablir toutes les courbes', (tester) async {
    await tester.pumpWidget(MaterialApp(home:Scaffold(body:SingleChildScrollView(child:EnergyChart(history:const [{'production_w':10},{'production_w':20}])))));
    expect(find.text('Maison'),findsOneWidget);
    expect(find.text('Injection EDF'),findsOneWidget);
    await tester.tap(find.text('Production'));
    await tester.pumpAndSettle();
    expect(find.text('Toutes les courbes'),findsOneWidget);
    await tester.tap(find.text('Toutes les courbes'));
    await tester.pumpAndSettle();
    expect(find.text('Toutes les courbes'),findsNothing);
  });
  testWidgets('les valeurs suivent le point sélectionné sans sortir du graphique', (tester) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SizedBox(width: 320, child: EnergyChart(history: const [
      {'timestamp':'2026-11-28T10:00:00','production_w':10},
      {'timestamp':'2026-11-28T10:10:00','production_w':250},
    ])))));
    final plot = find.byKey(const ValueKey('energy-plot'));
    await tester.tapAt(tester.getTopRight(plot) + const Offset(-2, 20));
    await tester.pump();
    expect(find.byKey(const ValueKey('energy-tooltip')), findsOneWidget);
    expect(find.text('Production : 250 W'), findsOneWidget);
    final graph = tester.getRect(plot), tooltip = tester.getRect(find.byKey(const ValueKey('energy-tooltip')));
    expect(tooltip.left, greaterThanOrEqualTo(graph.left));
    expect(tooltip.right, lessThanOrEqualTo(graph.right));
    expect(tester.takeException(), isNull);
  });
}
