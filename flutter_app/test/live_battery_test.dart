import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:mon_solaire_mobile/main.dart';

void main() {
  final address=Platform.environment['SOLAR_TEST_URL'];
  test('le bilan batterie réel répond dans le délai prévu', () async {
    final uri=validateAddress(address!);
    expect(uri,isNotNull);
    final client=SolarClient(uri!);
    final status=await client.get('api/status');
    expect(status['current'],isA<Map>());
    final history=await client.get('api/battery-full',timeout:const Duration(seconds:90));
    expect(history['days'],isA<List>());
    expect((history['days'] as List).isNotEmpty,isTrue);
  },skip:address == null ? 'Définir SOLAR_TEST_URL pour tester son propre Raspberry.' : false,timeout:const Timeout(Duration(seconds:110)));
}
