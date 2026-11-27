import 'package:flutter_test/flutter_test.dart';
import 'package:mon_solaire_mobile/annual_summary.dart';

void main() {
  test('calcule le bilan comme le tableau à partir des relevés et tarifs', () {
    final result=calculateAnnualSummary({
      'annual_real_readings':{'start':'2026-01-01','as_of':'2026-01-31','hp_kwh':1000,'hc_kwh':500,'battery_discharge_kwh':100,'reference_2025':{'subscription_start':'2025-01-01','end':'2025-12-31','hp_kwh':3000,'hc_kwh':1000,'hp_eur_kwh':0.2,'hc_eur_kwh':0.1,'subscription_monthly_eur':12}},
      'tariffs':{'hp_eur_kwh':0.2,'hc_eur_kwh':0.1,'abonnement_journalier_eur':1},
    },now:DateTime(2026,2));
    expect(result.importKwh,1500);
    expect(result.energyCost,250);
    expect(result.subscription,31);
    expect(result.totalCost,281);
    expect(result.batterySaving,20);
    expect(result.referenceCost,844);
    expect(result.solarSaving,583);
  });
  test('les données manquantes ne deviennent pas des zéros', () {
    final result=calculateAnnualSummary({'annual_real_readings':{'hp_kwh':100,'hc_kwh':null,'battery_discharge_kwh':null},'tariffs':{}},now:DateTime(2026));
    expect(result.importKwh,isNull);
    expect(result.totalCost,isNull);
    expect(result.batterySaving,isNull);
    expect(result.solarSaving,isNull);
  });
  test('les jours sont comptés inclusivement, y compris les années bissextiles', () {
    expect(inclusiveDays(DateTime(2024,2,28),DateTime(2024,3,1)),3);
    expect(inclusiveDays(DateTime(2024,3,1),DateTime(2024,2,28)),isNull);
  });
}
