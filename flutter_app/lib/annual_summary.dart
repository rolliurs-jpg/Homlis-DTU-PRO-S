class AnnualSummary {
  const AnnualSummary({this.importKwh, this.energyCost, this.subscription, this.totalCost, this.batterySaving, this.referenceCost, this.solarSaving, this.start, this.end, this.referenceStart, this.referenceEnd});
  final double? importKwh, energyCost, subscription, totalCost, batterySaving, referenceCost, solarSaving;
  final DateTime? start, end, referenceStart, referenceEnd;
}

double? annualNumber(dynamic value) => value is num && value.isFinite ? value.toDouble() : null;
DateTime? annualDate(dynamic value) => value is String && value.isNotEmpty ? DateTime.tryParse(value) : null;
int? inclusiveDays(DateTime? start, DateTime? end) {
  if (start == null || end == null) return null;
  final days = DateTime.utc(end.year,end.month,end.day).difference(DateTime.utc(start.year,start.month,start.day)).inDays;
  return days < 0 ? null : days + 1;
}

AnnualSummary calculateAnnualSummary(Map report, {required DateTime now}) {
  final r = report['annual_real_readings'] is Map ? report['annual_real_readings'] as Map : {};
  final tariff = report['tariffs'] is Map ? report['tariffs'] as Map : {};
  final ref = r['reference_2025'] is Map ? r['reference_2025'] as Map : {};
  final hp=annualNumber(r['hp_kwh']), hc=annualNumber(r['hc_kwh']);
  final hpRate=annualNumber(tariff['hp_eur_kwh']), hcRate=annualNumber(tariff['hc_eur_kwh']), daily=annualNumber(tariff['abonnement_journalier_eur']);
  final start=annualDate(r['start']), end=annualDate(r['as_of']) ?? now, days=inclusiveDays(start,end);
  final totalKwh=hp != null && hc != null ? hp+hc : null;
  final energy=hp != null && hc != null && hpRate != null && hpRate > 0 && hcRate != null && hcRate > 0 ? hp*hpRate+hc*hcRate : null;
  final subscription=days != null && daily != null && daily >= 0 ? days*daily : null;
  final total=energy != null && subscription != null ? energy+subscription : null;
  final discharge=annualNumber(r['battery_discharge_kwh']), battery=discharge != null ? discharge*0.20 : null;
  final refHp=annualNumber(ref['hp_kwh']), refHc=annualNumber(ref['hc_kwh']), refHpRate=annualNumber(ref['hp_eur_kwh']), refHcRate=annualNumber(ref['hc_eur_kwh']), refMonthly=annualNumber(ref['subscription_monthly_eur']);
  final refStart=annualDate(ref['subscription_start']), refEnd=annualDate(ref['end']), refDays=inclusiveDays(refStart,refEnd);
  final refEnergy=refHp != null && refHc != null && refHpRate != null && refHpRate > 0 && refHcRate != null && refHcRate > 0 ? refHp*refHpRate+refHc*refHcRate : null;
  final yearDays=refStart != null && DateTime(refStart.year,3,0).day == 29 ? 366 : 365;
  final refSubscription=refDays != null && refMonthly != null && refMonthly >= 0 ? refMonthly*12*refDays/yearDays : null;
  final reference=refEnergy != null && refSubscription != null ? refEnergy+refSubscription : null;
  final savings=reference != null && total != null && battery != null ? reference-total+battery : null;
  return AnnualSummary(importKwh:totalKwh,energyCost:energy,subscription:subscription,totalCost:total,batterySaving:battery,referenceCost:reference,solarSaving:savings,start:start,end:end,referenceStart:refStart,referenceEnd:refEnd);
}
