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
  testWidgets('la démonstration affiche des valeurs fictives et les bilans', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const SolarApp());
    await tester.pumpAndSettle();
    await tester.tap(find.text('Essayer la démonstration'));
    await tester.pumpAndSettle();
    expect(find.text('Démonstration · données fictives'), findsOneWidget);
    expect(find.text('1050 W'), findsOneWidget);
    await tester.tap(find.text('Bilan'));
    await tester.pumpAndSettle();
    expect(find.text('8,20 kWh'), findsOneWidget);
  });
}
