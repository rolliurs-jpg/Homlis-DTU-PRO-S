import 'package:flutter_test/flutter_test.dart';
import 'package:mon_solaire_mobile/battery_cycle.dart';

void main() {
  test('un bilan sans plein affiche les heures et la fin de décharge', () {
    final now = DateTime(2026,11,27,19,0), start = DateTime(2026,11,27,15,18).millisecondsSinceEpoch / 1000, end = DateTime(2026,11,27,17,24).millisecondsSinceEpoch / 1000;
    final cycle = summarizeCycle({'date':'2026-11-27','ongoing':true,'discharge_at':start,'discharge_end_at':end,'display':['2026-11-27','—','Indisponible','17:13','15:18','2 h 06 min','—','—']}, {'battery_timestamp':now.millisecondsSinceEpoch/1000,'battery_ac_charge_w':0,'battery_ac_discharge_w':0}, now);
    expect(cycle.status,'Bilan en cours · sans plein');
    expect(cycle.solarEnd,'17:13');
    expect(cycle.dischargeStart,'15:18');
    expect(cycle.dischargeEnd,'17:24');
    expect(cycle.durationLabel,'Temps de décharge cumulé');
    expect(cycle.surplus,'Non applicable sans plein');
  });
  test('décharge active et attente de fin ne sont pas confondues', () {
    final now=DateTime(2026,11,27,19), start=DateTime(2026,11,27,18).millisecondsSinceEpoch/1000;
    final cycle=summarizeCycle({'date':'2026-11-27','ongoing':true,'discharge_at':start,'display':['2026-11-27','—','—','En attente','18:00','1 h','—','—']}, {'battery_timestamp':now.millisecondsSinceEpoch/1000,'battery_ac_charge_w':0,'battery_ac_discharge_w':200}, now);
    expect(cycle.dischargeEnd,'En attente');
    expect(cycle.durationLabel,'Temps en décharge en cours');
  });
}
