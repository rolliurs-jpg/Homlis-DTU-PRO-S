typedef CycleJson = Map<String, dynamic>;

class CycleSummary {
  const CycleSummary({required this.status, required this.explanation, required this.day, required this.full, required this.solarEnd, required this.dischargeStart, required this.dischargeEnd, required this.dischargeDuration, required this.durationLabel, required this.recharge, required this.surplus});
  final String status, explanation, day, full, solarEnd, dischargeStart, dischargeEnd, dischargeDuration, durationLabel, recharge, surplus;
}

String cycleClock(dynamic seconds, String day) {
  if (seconds is! num || !seconds.isFinite) return '—';
  final date = DateTime.fromMillisecondsSinceEpoch((seconds * 1000).round()).toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  final time = '${two(date.hour)}:${two(date.minute)}';
  final iso = '${date.year}-${two(date.month)}-${two(date.day)}';
  return iso == day ? time : '${two(date.day)}/${two(date.month)} à $time';
}

CycleSummary summarizeCycle(Map row, Map current, DateTime now) {
  final day = '${row['date'] ?? ''}', display = row['display'] is List ? row['display'] as List : const [];
  String item(int i) => display.length > i && display[i] != null && '${display[i]}'.isNotEmpty ? '${display[i]}' : '—';
  final noFull = row['full_at'] == null, ongoing = row['ongoing'] == true;
  final charge = current['battery_ac_charge_w'], discharge = current['battery_ac_discharge_w'], timestamp = current['battery_timestamp'];
  final fresh = timestamp is num && (now.millisecondsSinceEpoch / 1000 - timestamp).abs() <= 45;
  final charging = ongoing && row['recharge_at'] == null && fresh && charge is num && charge > 20;
  final discharging = ongoing && row['recharge_at'] == null && fresh && discharge is num && charge is num && discharge - charge > 20;
  final dayStart = DateTime.tryParse(day);
  final start = row['discharge_at'];
  final already = noFull && start is num && dayStart != null && start >= dayStart.millisecondsSinceEpoch / 1000 && start <= dayStart.millisecondsSinceEpoch / 1000 + 300;
  final end = row['discharge_end_at'];
  final endLabel = end is num ? cycleClock(end, day) : start is num ? 'En attente' : '—';
  final explanation = charging ? 'La batterie se recharge actuellement. L’heure de début sera ajoutée après confirmation continue.' : noFull ? 'La batterie n’a pas atteint 100 %. Les périodes de charge et de décharge réellement mesurées restent affichées ; le surplus après plein ne s’applique pas.' : item(7) == '—' ? '' : item(7);
  return CycleSummary(status: charging ? 'Bilan en cours · recharge active' : ongoing ? noFull ? 'Bilan en cours · sans plein' : 'Cycle en cours' : noFull ? 'Bilan journalier' : 'Cycle enregistré', explanation: explanation, day: day, full: noFull ? '—' : item(1), solarEnd: item(3), dischargeStart: already ? 'Dès minuit' : item(4), dischargeEnd: endLabel, dischargeDuration: item(5), durationLabel: discharging ? 'Temps en décharge en cours' : 'Temps de décharge cumulé', recharge: charging ? 'En cours' : item(6), surplus: noFull ? 'Non applicable sans plein' : item(2));
}
