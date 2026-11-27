typedef EquipmentJson = Map<String, dynamic>;

enum EquipmentHealth { online, offline, disabled, waiting, warning }

class EquipmentInfo {
  const EquipmentInfo(this.group, this.name, this.status, this.health, {this.detail = ''});
  final String group, name, status, detail;
  final EquipmentHealth health;
}

List<EquipmentInfo> equipmentList(EquipmentJson settings, EquipmentJson live, {required bool fresh, required DateTime now}) {
  const house = 'Installation maison', shed = 'Installation cabanon', common = 'Équipement commun';
  final result = <EquipmentInfo>[];
  final sim = live['surplus_simulation'] is Map ? live['surplus_simulation'] as Map : {};
  final dtu = sim['dtu'] is Map ? sim['dtu'] as Map : {};
  final dtuOnline = live['dtu_state'] == 'online' || dtu['state'] == 'online';
  final fallback = !dtuOnline && '${live['production_source'] ?? ''}'.contains('Shelly');
  result.add(EquipmentInfo(house, 'Hoymiles · DTU-Pro-S', !fresh ? 'État non actualisé' : dtuOnline ? 'Connecté · lecture reçue' : fallback ? 'DTU indisponible · mesure Shelly utilisée' : 'Lecture DTU indisponible', !fresh ? EquipmentHealth.waiting : dtuOnline ? EquipmentHealth.online : fallback ? EquipmentHealth.warning : EquipmentHealth.offline));

  void configured(String key, String group, String name, dynamic state) {
    final config = settings[key] is Map ? settings[key] as Map : null;
    if (config == null || config['enabled'] == null) { result.add(EquipmentInfo(group, name, 'Configuration indisponible', EquipmentHealth.waiting)); return; }
    if (config['enabled'] != true) { result.add(EquipmentInfo(group, name, 'Désactivé', EquipmentHealth.disabled)); return; }
    if (!fresh) { result.add(EquipmentInfo(group, name, 'État non actualisé', EquipmentHealth.waiting)); return; }
    final status = state == 'online' ? EquipmentHealth.online : state == 'offline' ? EquipmentHealth.offline : EquipmentHealth.waiting;
    result.add(EquipmentInfo(group, name, status == EquipmentHealth.online ? 'Connecté' : status == EquipmentHealth.offline ? 'Non connecté' : 'En attente de mesure', status));
  }

  final links = settings['wireless_interfaces'] is List ? settings['wireless_interfaces'] as List : [];
  void addLink(dynamic value) {
    if (value is! Map) return;
    final iface = '${value['interface'] ?? ''}'.toLowerCase(), connected = value['connected'] == true;
    final optional = iface == 'wlan1' && !connected && dtu['state'] == 'online';
    final health = !fresh ? EquipmentHealth.waiting : connected ? EquipmentHealth.online : optional ? EquipmentHealth.warning : EquipmentHealth.offline;
    result.add(EquipmentInfo(iface == 'wlan2' ? shed : house, '${value['name'] ?? 'Liaison Wi-Fi'}', !fresh ? 'État non actualisé' : connected ? 'Connectée' : optional ? 'Wi-Fi direct non requis · Modbus actif' : 'Non connectée', health, detail: '${value['role'] ?? ''}'));
  }
  for (final link in links.where((v) => v is Map && '${v['interface']}'.toLowerCase() == 'wlan1')) { addLink(link); }
  configured('tp_link', house, 'Nano-routeur TP-Link', live['tp_link_state']);
  configured('tongou_relay', house, 'Tongou · relais de relance DTU', live['tongou_state']);
  configured('linky', house, 'Linky & Denky D4', live['linky_state']);
  configured('shelly', house, 'Shelly Pro EM · réseau et panneaux', live['shelly_state']);
  for (final link in links.where((v) => v is Map && '${v['interface']}'.toLowerCase() == 'wlan2')) { addLink(link); }
  configured('shelly2', shed, 'Shelly EM Gen3 · panneaux cabanon', live['pv2_w'] is num ? 'online' : null);

  final alfaConnected = links.any((w) => w is Map && '${w['interface']}'.toLowerCase() == 'wlan2' && w['connected'] == true);
  final espDevices = settings['esp_devices'] is List ? settings['esp_devices'] as List : [];
  for (final e in espDevices) {
    if (e is! Map) continue;
    final enabled = e['enabled'] == true;
    final checked = e['checked_at'] is num ? (e['checked_at'] as num).toDouble() : null;
    final checkFresh = fresh && checked != null && (now.millisecondsSinceEpoch / 1000 - checked).abs() <= 90;
    final proxy = live['hoymiles_proxy'] is Map ? live['hoymiles_proxy'] as Map : {};
    final proxyTime = proxy['timestamp'] is num ? (proxy['timestamp'] as num).toDouble() : null;
    final proxyFresh = fresh && e['id'] == 'proxy' && proxy['state'] == 'online' && proxyTime != null && (now.millisecondsSinceEpoch / 1000 - proxyTime).abs() <= 45;
    final reachable = checkFresh && e['connected'] == true;
    final linked = checkFresh && e['id'] == 'router' && alfaConnected && !reachable;
    final health = !enabled ? EquipmentHealth.disabled : proxyFresh || reachable ? EquipmentHealth.online : !checkFresh ? EquipmentHealth.waiting : linked ? EquipmentHealth.warning : EquipmentHealth.offline;
    final label = !enabled ? 'Désactivé' : proxyFresh ? 'Connecté · lecture Hoymiles' : reachable ? 'Connecté · joignable' : !checkFresh ? 'État non actualisé' : linked ? 'Wi-Fi associé · réponse en attente' : 'Non joignable';
    result.add(EquipmentInfo(shed, '${e['name'] ?? 'ESP32'}', label, health, detail: '${e['role'] ?? ''}'));
  }
  final batteryTime = live['battery_timestamp'] is num ? (live['battery_timestamp'] as num).toDouble() : null;
  final batteryFresh = batteryTime != null && (now.millisecondsSinceEpoch / 1000 - batteryTime).abs() <= 90;
  configured('battery', common, 'Batterie Zendure · Smart Meter', batteryFresh && live['battery_soc_pct'] is num ? 'online' : null);
  return result;
}
