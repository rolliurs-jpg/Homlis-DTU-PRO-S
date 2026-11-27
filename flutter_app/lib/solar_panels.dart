class SolarPanelReading {
  const SolarPanelReading({required this.group, required this.number, this.power, this.voltage, this.current, this.estimated = false});
  final String group;
  final int number;
  final double? power, voltage, current;
  final bool estimated;
}

double? _finite(dynamic value) => value is num && value.isFinite ? value.toDouble() : null;
bool _fresh(Map data, DateTime now, int seconds) {
  final timestamp = _finite(data['timestamp']);
  if (data['state'] != 'online' || timestamp == null) return false;
  final age = now.millisecondsSinceEpoch / 1000 - timestamp;
  return age >= -30 && age < seconds;
}

List<SolarPanelReading> solarPanelReadings(Map current, DateTime now, {bool connectionOk = true}) {
  final simulation = current['surplus_simulation'] is Map ? current['surplus_simulation'] as Map : {};
  final dtu = simulation['dtu'] is Map ? simulation['dtu'] as Map : {};
  final proxy = current['hoymiles_proxy'] is Map ? current['hoymiles_proxy'] as Map : {};
  List<dynamic> rows(Map source, bool fresh) => fresh && source['panels'] is List ? source['panels'] as List : const [];
  Map<int, Map> index(List<dynamic> list, int max) {
    final result = <int,Map>{};
    for (final row in list) {
      if (row is! Map) continue;
      final port = row['port'] is num ? (row['port'] as num).toInt() : int.tryParse('${row['port']}');
      if (port != null && port >= 1 && port <= max) result[port] = row;
    }
    return result;
  }
  final house = index(rows(dtu, connectionOk && _fresh(dtu,now,345)),4);
  final proxyFresh = connectionOk && _fresh(proxy,now,70);
  final shed = index(rows(proxy,proxyFresh),2);
  final total = proxyFresh ? _finite(proxy['power_w']) : null;
  if (shed.isEmpty && total != null && total >= 0) {
    shed[1] = {'power_w':total/2,'estimated':true};
    shed[2] = {'power_w':total/2,'estimated':true};
  }
  SolarPanelReading make(String group, int number, Map? sample) => SolarPanelReading(group:group, number:number, power:_finite(sample?['power_w']), voltage:_finite(sample?['voltage_v']), current:_finite(sample?['current_a']), estimated:sample?['estimated'] == true);
  return [for(var i=1;i<=4;i++) make('Maison',i,house[i]),for(var i=1;i<=2;i++) make('Cabanon',i,shed[i])];
}
