import 'package:flutter_test/flutter_test.dart';
import 'package:mon_solaire_mobile/solar_panels.dart';

void main() {
  test('six panneaux : mesures individuelles, estimation et données périmées', () {
    final now=DateTime(2026,11,27,12), t=now.millisecondsSinceEpoch/1000;
    final current={'surplus_simulation':{'dtu':{'state':'online','timestamp':t,'panels':[{'port':1,'power_w':0},{'port':2,'power_w':125}]}},'hoymiles_proxy':{'state':'online','timestamp':t,'power_w':240}};
    final result=solarPanelReadings(current,now);
    expect(result.length,6);
    expect(result[0].power,0);
    expect(result[1].power,125);
    expect(result[2].power,isNull);
    expect(result[4].power,120);
    expect(result[5].power,120);
    expect(result[4].estimated,isTrue);
    final stale=solarPanelReadings(current,now.add(const Duration(minutes:7)));
    expect(stale.every((p)=>p.power==null),isTrue);
    expect(solarPanelReadings(current,now,connectionOk:false).every((p)=>p.power==null),isTrue);
  });
  test('les mesures individuelles du cabanon ne sont jamais remplacées par une estimation', () {
    final now=DateTime(2026,11,27,12), t=now.millisecondsSinceEpoch/1000;
    final result=solarPanelReadings({'hoymiles_proxy':{'state':'online','timestamp':t,'power_w':300,'panels':[{'port':1,'power_w':80},{'port':2,'power_w':220}]}},now);
    expect(result[4].power,80);
    expect(result[5].power,220);
    expect(result[4].estimated,isFalse);
  });
}
