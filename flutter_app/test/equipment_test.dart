import 'package:flutter_test/flutter_test.dart';
import 'package:mon_solaire_mobile/equipment.dart';

void main() {
  test('affiche les équipements activés, désactivés et leur état réel', () {
    final now = DateTime.now();
    final settings = <String,dynamic>{
      for (final key in ['tp_link','tongou_relay','linky','shelly','shelly2','battery']) key:{'enabled':true},
      'wireless_interfaces':[{'interface':'wlan2','name':'Alfa cabanon','connected':true}],
      'esp_devices':[{'id':'proxy','name':'ESP32 proxy','enabled':true,'connected':true,'checked_at':now.millisecondsSinceEpoch/1000}, {'id':'router','name':'ESP32 routeur','enabled':false,'connected':false}],
    };
    final live = <String,dynamic>{'dtu_state':'online','tp_link_state':'offline','tongou_state':'online','linky_state':'online','shelly_state':'online','pv2_w':0,'battery_soc_pct':30,'battery_timestamp':now.millisecondsSinceEpoch/1000};
    final result = equipmentList(settings, live, fresh:true, now:now);
    EquipmentInfo find(String title) => result.firstWhere((d)=>d.name.contains(title));
    expect(find('DTU-Pro-S').health, EquipmentHealth.online);
    expect(find('TP-Link').health, EquipmentHealth.offline);
    expect(find('ESP32 proxy').status, 'Connecté · joignable');
    expect(find('ESP32 routeur').health, EquipmentHealth.disabled);
    expect(find('Shelly EM Gen3').health, EquipmentHealth.online);
    expect(find('Zendure').health, EquipmentHealth.online);
    final stale = equipmentList(settings, live, fresh:false, now:now);
    expect(stale.firstWhere((d)=>d.name.contains('DTU-Pro-S')).health, EquipmentHealth.waiting);
    expect(stale.firstWhere((d)=>d.name.contains('ESP32 proxy')).health, EquipmentHealth.waiting);
  });
}
