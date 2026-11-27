import 'dart:io';
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
}
