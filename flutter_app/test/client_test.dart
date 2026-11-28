import 'dart:io';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:mon_solaire_mobile/main.dart';

void main() {
  test('le client lit les mesures JSON du serveur', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) {
      expect(request.uri.path, '/api/status');
      request.response.headers.contentType = ContentType.json;
      request.response.write('{"current":{"production_w":123}}');
      request.response.close();
    });
    try {
      final result = await SolarClient(Uri.parse('http://127.0.0.1:${server.port}/')).get('api/status');
      expect(result['current']['production_w'], 123);
    } finally { await server.close(force: true); }
  });
  test('le délai du bilan batterie peut être plus long que celui du direct', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      await Future<void>.delayed(const Duration(milliseconds:150));
      request.response.headers.contentType = ContentType.json;
      request.response.write('{"days":[{"date":"2026-11-27"}]}');
      await request.response.close();
    });
    try {
      final client=SolarClient(Uri.parse('http://127.0.0.1:${server.port}/'));
      final result=await client.get('api/battery-full',timeout:const Duration(seconds:2));
      expect((result['days'] as List).length,1);
    } finally { await server.close(force:true); }
  });
  test('commande utilise le jeton et ne cache pas les refus du Raspberry', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      if (request.method == 'GET') { request.response.write("const ACTION_TOKEN='test_token-123';"); }
      else {
        expect(request.headers.value('X-Action-Token'), 'test_token-123');
        expect(request.contentLength, greaterThan(0));
        final data = jsonDecode(await utf8.decoder.bind(request).join());
        expect(data['action'], 'settings');
        request.response.headers.contentType = ContentType.json;
        request.response.write('{"error":"Mot de passe incorrect"}');
      }
      await request.response.close();
    });
    try { await expectLater(SolarClient(Uri.parse('http://127.0.0.1:${server.port}/')).action('settings', {}), throwsA(isA<Exception>())); }
    finally { await server.close(force:true); }
  });
}
