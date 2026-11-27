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
}
