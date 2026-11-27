import 'dart:async';
import 'dart:convert';
import 'dart:io';
// ignore: deprecated_member_use
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'equipment.dart';
import 'energy_chart.dart';
import 'battery_cycle.dart';
import 'solar_panels.dart';
import 'annual_summary.dart';

const bg = Color(0xff071321);
const panel = Color(0xff101f31);
const green = Color(0xff4ee2a4);
const gold = Color(0xffffd27a);
const blue = Color(0xff94baff);
const dischargeRed = Color(0xffff8797);
typedef Json = Map<String, dynamic>;

void main() => runApp(const SolarApp());

Uri? validateAddress(String input) {
  final uri = Uri.tryParse(input.trim());
  if (uri == null || !['http', 'https'].contains(uri.scheme) || uri.host.isEmpty ||
      uri.userInfo.isNotEmpty || uri.hasQuery || uri.hasFragment ||
      (uri.path.isNotEmpty && uri.path != '/')) { return null; }
  if (uri.scheme == 'http') {
    final host = uri.host.toLowerCase(), ip = InternetAddress.tryParse(host);
    final octets = ip?.type == InternetAddressType.IPv4 ? ip!.rawAddress : null;
    final privateIp = octets != null && (octets[0] == 10 || octets[0] == 127 ||
        (octets[0] == 192 && octets[1] == 168) || (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31) ||
        (octets[0] == 100 && octets[1] >= 64 && octets[1] <= 127));
    if (!privateIp && host != 'localhost' && !host.endsWith('.local') && !host.endsWith('.ts.net')) return null;
  }
  return uri.replace(path: '/');
}

String number(dynamic value, String unit, {int decimals = 0}) {
  if (value is! num || !value.isFinite) return '—';
  return '${value.toStringAsFixed(decimals).replaceAll('.', ',')} $unit';
}

Color? batteryFlowColor(Map current, String key, DateTime now, {bool connected = true}) {
  final power = current[key], stamp = current['battery_timestamp'];
  if (!connected || power is! num || !power.isFinite || power <= 0 || stamp is! num || (now.millisecondsSinceEpoch / 1000 - stamp).abs() > 90) return null;
  return key == 'battery_ac_discharge_w' ? dischargeRed : green;
}

const frenchMonths = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
String? monthYear(dynamic value) {
  final date = DateTime.tryParse('${value ?? ''}');
  return date == null ? null : '${frenchMonths[date.month - 1]} ${date.year}';
}
String? shortDate(dynamic value) {
  final date = DateTime.tryParse('${value ?? ''}');
  if (date == null) return null;
  return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
}

class SolarApp extends StatelessWidget {
  const SolarApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Mon solaire', debugShowCheckedModeBanner: false,
    theme: ThemeData.dark(useMaterial3: true).copyWith(
      scaffoldBackgroundColor: bg, colorScheme: ColorScheme.fromSeed(seedColor: green, brightness: Brightness.dark),
      cardTheme: const CardThemeData(color: panel, margin: EdgeInsets.symmetric(vertical: 6)),
    ), home: const Dashboard(),
  );
}

class SolarClient {
  SolarClient(this.base);
  final Uri base;
  Future<Json> get(String endpoint) async {
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 10);
    try {
      final request = await client.getUrl(base.resolve(endpoint));
      request.followRedirects = false;
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close().timeout(const Duration(seconds: 25));
      if (response.statusCode != 200) throw HttpException('Réponse ${response.statusCode}');
      final decoded = jsonDecode(await response.transform(utf8.decoder).join().timeout(const Duration(seconds: 25)));
      if (decoded is! Map<String, dynamic>) throw const FormatException('Données invalides');
      return decoded;
    } finally { client.close(force: true); }
  }
}

class Dashboard extends StatefulWidget {
  const Dashboard({super.key});
  @override State<Dashboard> createState() => _DashboardState();
}

class _DashboardState extends State<Dashboard> {
  static const pages = ['Direct', 'Bilan journalier', 'Budget mensuel', 'Annuel', 'Batterie', 'Panneaux', 'Équipements'];
  static const icons = [Icons.home_outlined, Icons.today, Icons.euro, Icons.calendar_month, Icons.battery_charging_full, Icons.solar_power, Icons.settings];
  Uri? address;
  bool demo = false, loading = false, requesting = false, statusReachable = false;
  String? error;
  int selected = 0, generation = 0;
  String period = 'today';
  String? selectedCycleDay;
  Json? status, report, battery, settings;
  DateTime? settingsUpdated;
  Timer? timer;

  @override void initState() { super.initState(); init(); }
  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('dashboard_url');
    if (!mounted) return;
    if (saved != null && validateAddress(saved) != null) {
      setState(() => address = validateAddress(saved));
      refresh();
    }
    timer = Timer.periodic(const Duration(seconds: 15), (_) { if (mounted && (address != null || demo)) refresh(silent: true); });
  }
  @override void dispose() { timer?.cancel(); super.dispose(); }

  Future<void> changeAddress() async {
    final controller = TextEditingController(text: address?.toString() ?? '');
    final result = await showDialog<String>(context: context, builder: (context) => AlertDialog(
      title: const Text('Adresse du Raspberry'),
      content: TextField(controller: controller, keyboardType: TextInputType.url, autocorrect: false,
        decoration: const InputDecoration(hintText: 'http://adresse-du-raspberry:8765', helperText: 'Wi-Fi local ou VPN privé')),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(onPressed: () => Navigator.pop(context, controller.text), child: const Text('Connecter'))],
    ));
    controller.dispose();
    if (!mounted || result == null) return;
    final uri = validateAddress(result);
    if (uri == null) { ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Adresse invalide. Utilisez une adresse locale ou Tailscale, ou une adresse HTTPS.'))); return; }
    final prefs = await SharedPreferences.getInstance(); await prefs.setString('dashboard_url', uri.toString());
    if (!mounted) return;
    setState(() { address = uri; demo = false; status = null; statusReachable = false; report = null; battery = null; settings = null; });
    refresh();
  }

  Future<void> refresh({bool silent = false}) async {
    if (silent && (loading || requesting)) return;
    if (demo) { ++generation; requesting = false; setState(() { status = demoStatus(); statusReachable = true; report = demoReport(); battery = demoBattery(); settings = demoSettings(); settingsUpdated = DateTime.now(); error = null; loading = false; }); return; }
    if (address == null) return;
    final ticket = ++generation, page = selected, selectedPeriod = period;
    requesting = true;
    if (!silent) setState(() { loading = true; error = null; });
    final client = SolarClient(address!);
    try {
      final live = await client.get('api/status');
      if (!mounted || ticket != generation) return;
      setState(() { status = live; statusReachable = true; error = null; });
      Json? other;
      try {
        if (page == 1) other = await client.get('api/report?period=$selectedPeriod');
        if (page == 2) other = await client.get('api/report?period=month');
        if (page == 3) other = await client.get('api/report?period=year');
        if (page == 4) other = await client.get('api/battery-full');
        if (page == 6) other = await client.get('api/settings');
      } catch (_) {
        if (!mounted || ticket != generation) return;
        setState(() { loading = false; error = page == 4 ? 'Mesures en direct reçues ; le bilan batterie est momentanément indisponible. Les anciens cycles restent affichés.' : 'Mesures en direct reçues ; les données de cette page sont momentanément indisponibles.'; });
        return;
      }
      if (!mounted || ticket != generation) return;
      setState(() { status = live; if (page >= 1 && page <= 3) report = other; if (page == 4) battery = other; if (page == 6) { settings = other; settingsUpdated = DateTime.now(); } loading = false; error = null; });
    } catch (_) {
      if (!mounted || ticket != generation) return;
      setState(() { loading = false; statusReachable = false; error = 'Connexion ou données indisponibles. Vérifiez le Wi-Fi ou Tailscale. Les anciennes valeurs restent affichées.'; });
    } finally { if (ticket == generation) requesting = false; }
  }

  void select(int index) { setState(() { selected = index; report = null; battery = null; settings = null; }); refresh(); }
  Json get current => status?['current'] is Map<String, dynamic> ? status!['current'] : {};
  String freshness() {
    final stamp = DateTime.tryParse('${current['timestamp'] ?? ''}');
    if (stamp == null) return 'En attente de mesure';
    final age = DateTime.now().difference(stamp).inSeconds;
    if (age > 90) return 'Mesure ancienne · ${stamp.toLocal().toString().substring(0, 19)}';
    return 'Mesure reçue · ${stamp.toLocal().toString().substring(11, 19)}';
  }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('☀ Mon solaire'), actions: [
      IconButton(tooltip: 'Actualiser', onPressed: () => refresh(), icon: const Icon(Icons.refresh)),
      PopupMenuButton<String>(onSelected: (v) { if (v == 'address') changeAddress(); if (v == 'demo') { setState(() => demo = true); refresh(); } }, itemBuilder: (_) => [
        const PopupMenuItem(value: 'address', child: Text('Adresse du Raspberry')),
        const PopupMenuItem(value: 'demo', child: Text('Mode démonstration')),
      ]),
    ]),
    body: Column(children: [
      if (demo) banner('Démonstration · données fictives', gold),
      if (loading) const LinearProgressIndicator(),
      if (loading) banner('Chargement des données…', blue),
      if (error != null) banner(error!, gold),
      Expanded(child: address == null && !demo ? welcome() : RefreshIndicator(onRefresh: refresh, child: ListView(key: ValueKey(selected), padding: const EdgeInsets.all(16), children: [
        Text(pages[selected], style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12),
        if (selected == 0) ...direct(),
        if (selected == 1) ...reportView(),
        if (selected == 2) ...budgetView(),
        if (selected == 3) ...annualView(),
        if (selected == 4) ...batteryView(),
        if (selected == 5) ...panelsView(),
        if (selected == 6) ...devicesView(),
      ]))),
      SafeArea(top: false, child: Wrap(alignment: WrapAlignment.center, children: List.generate(pages.length, (i) => SizedBox(width: MediaQuery.sizeOf(context).width / 4, child: TextButton(onPressed: () => select(i), style: TextButton.styleFrom(foregroundColor: selected == i ? green : Colors.blueGrey[200], padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 2)), child: Column(mainAxisSize: MainAxisSize.min, children: [Icon(icons[i], size: 19), Text(pages[i], maxLines: 2, textAlign: TextAlign.center, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11))])))))),
    ]),
  );
  Widget banner(String text, Color color) => Container(width: double.infinity, padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8), color: color.withValues(alpha: .14), child: Text(text, style: TextStyle(color: color)));
  Widget welcome() => Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.solar_power, size: 64, color: gold), const SizedBox(height: 20), const Text('Connectez votre Raspberry ou découvrez l’application en mode démonstration.', textAlign: TextAlign.center), const SizedBox(height: 18), FilledButton(onPressed: changeAddress, child: const Text('Adresse du Raspberry')), TextButton(onPressed: () { setState(() => demo = true); refresh(); }, child: const Text('Essayer la démonstration'))])));
  Widget box(String title, List<Widget> children) => Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)), const SizedBox(height: 8), ...children])));
  Widget row(String label, String value, {Color? color, Color? labelColor}) => Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Row(children: [Expanded(child: Text(label, style:TextStyle(color:labelColor))), const SizedBox(width: 8), Text(value, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17, color: color))]));
  List<Widget> batteryFlowRows(Map c) {
    final charging=batteryFlowColor(c,'battery_ac_charge_w',DateTime.now(),connected:statusReachable), discharging=batteryFlowColor(c,'battery_ac_discharge_w',DateTime.now(),connected:statusReachable);
    return [row('Niveau',number(c['battery_soc_pct'],'%')),row('Charge',number(c['battery_ac_charge_w'],'W'),color:charging,labelColor:charging),row('Décharge',number(c['battery_ac_discharge_w'],'W'),color:discharging,labelColor:discharging)];
  }
  Widget info(String text) => Padding(padding: const EdgeInsets.symmetric(vertical: 7), child: Text(text, style: TextStyle(color: Colors.blueGrey[200])));
  List<Widget> direct() { final c = current; return [
    info(freshness()),
    box('La maison en direct', [row('Production solaire', number(c['production_w'], 'W'), color: green), row('Maison', number(c['consumption_w'], 'W'), color: blue), row('Acheté au réseau', number(c['import_w'], 'W')), row('Envoyé au réseau', number(c['export_w'], 'W'), color: gold)]),
    if (c['battery_enabled'] == true) box('Batterie', batteryFlowRows(c)),
    box('Raspberry Pi', [row('Température', number(status?['raspberry_temperature_c'], '°C', decimals: 1))]),
    if (status?['history'] is List) box('Évolution des mesures', [EnergyChart(history:status!['history'] as List)]),
  ]; }
  List<Widget> reportView() { final d = report ?? {}; return [DropdownButton<String>(value: period, isExpanded: true, items: const [DropdownMenuItem(value: 'today', child: Text('Aujourd’hui')), DropdownMenuItem(value: 'yesterday', child: Text('Hier')), DropdownMenuItem(value: 'week', child: Text('7 jours')), DropdownMenuItem(value: 'month', child: Text('Ce mois'))], onChanged: (v) { if (v != null) { setState(() { period = v; report = null; }); refresh(); } }), box('Énergie mesurée', [row('Production', number(d['production_kwh'], 'kWh', decimals: 2)), row('Consommation maison', number(d['consumption_kwh'], 'kWh', decimals: 2)), row('Injection', number(d['export_kwh'], 'kWh', decimals: 2)), row('Charge batterie', number(d['battery_charge_kwh'], 'kWh', decimals: 2)), row('Décharge batterie', number(d['battery_discharge_kwh'], 'kWh', decimals: 2))])]; }
  List<Widget> budgetView() { final d=report??{}, b=d['billing'] is Map ? d['billing'] as Map : {}, month=monthYear(d['from_time']), start=shortDate(d['from_time']), end=shortDate(d['to_time']); return [if(start != null && end != null) info('Période : du $start au $end'), box(month == null ? 'Budget du mois' : 'Budget de $month', [row('Consommation maison', number(d['consumption_kwh'], 'kWh', decimals: 2)), row('Achat heures pleines', number(b['hp_kwh'], 'kWh', decimals: 2)), row('Achat heures creuses', number(b['hc_kwh'], 'kWh', decimals: 2)), row('Abonnement', number(d['subscription'], '€', decimals: 2)), row('Total', number(d['total_cost'], '€', decimals: 2))]), box('Solaire et batterie', [row('Production', number(d['production_kwh'], 'kWh', decimals: 2)), row('Injection', number(d['export_kwh'], 'kWh', decimals: 2)), row('Énergie locale', number(d['local_energy_kwh'], 'kWh', decimals: 2)), row('Charge batterie', number(d['battery_charge_kwh'], 'kWh', decimals: 2)), row('Décharge batterie', number(d['battery_discharge_kwh'], 'kWh', decimals: 2))])]; }
  List<Widget> annualView() {
    final d=report??{}, r=d['annual_real_readings'] is Map ? d['annual_real_readings'] as Map : {}, start=shortDate(r['start']), end=shortDate(r['as_of']) ?? shortDate(d['to_time']);
    final summary=calculateAnnualSummary(d,now:DateTime.now());
    final refStart=summary.referenceStart, refEnd=summary.referenceEnd;
    final referencePeriod=refStart != null && refEnd != null ? '${shortDate(refStart.toIso8601String())} au ${shortDate(refEnd.toIso8601String())}' : null;
    final batteryStart=shortDate(r['battery_start']), batteryEnd=shortDate(r['battery_end']);
    return [
      info(start != null ? 'Relevés cumulés depuis le $start${end != null ? ' jusqu’au $end' : ''}.' : 'Période des relevés annuels non renseignée.'),
      box('EDF · achats et coût', [row('Achat EDF total · HP + HC',number(summary.importKwh,'kWh',decimals:2),color:gold),row('Achat heures pleines',number(r['hp_kwh'],'kWh',decimals:2)),row('Achat heures creuses',number(r['hc_kwh'],'kWh',decimals:2)),row('Coût énergie · hors abonnement',number(summary.energyCost,'€',decimals:2)),row('Abonnement sur la période',number(summary.subscription,'€',decimals:2)),row('Coût EDF global · abonnement inclus',number(summary.totalCost,'€',decimals:2),color:gold)]),
      box('Solaire · production et économies', [row('Production solaire',number(r['production_kwh'],'kWh',decimals:2)),row('Injection EDF',number(r['export_kwh'],'kWh',decimals:2)),row('Charge batterie',number(r['battery_charge_kwh'],'kWh',decimals:2)),row('Décharge batterie',number(r['battery_discharge_kwh'],'kWh',decimals:2)),row('Économie batterie · 0,20 €/kWh',number(summary.batterySaving,'€',decimals:2)),row('Économie solaire + batterie',number(summary.solarSaving,'€',decimals:2),color:green)]),
      if(batteryStart != null && batteryEnd != null) info('Relevés batterie : du $batteryStart au $batteryEnd.'),
      info(summary.solarSaving == null ? 'Économie indisponible : les relevés de référence, les tarifs ou les mesures nécessaires manquent.' : 'Calcul du tableau : coût de référence${referencePeriod != null ? ' ($referencePeriod)' : ''} moins coût EDF actuel, plus batterie restituée valorisée à 0,20 €/kWh. Les périodes peuvent être différentes.'),
    ];
  }
  List<Widget> batteryView() {
    final days = battery?['days'] is List ? (battery!['days'] as List).whereType<Map>().where((d) => d['date'] is String).toList() : <Map>[];
    final matching = days.where((day) => day['date'] == selectedCycleDay).toList();
    final chosen = matching.isNotEmpty ? matching.first : days.isNotEmpty ? days.first : null;
    final cycle = chosen == null ? null : summarizeCycle(chosen, current, DateTime.now());
    return [
      box('Batterie en direct', batteryFlowRows(current)),
      box('Du plein au lendemain', [
        if (cycle == null) info(loading ? 'Chargement du bilan batterie…' : 'Aucun cycle disponible.') else ...[
          DropdownButton<String>(isExpanded:true, value:cycle.day, items:days.map((d)=>DropdownMenuItem<String>(value:d['date'] as String, child:Text('${d['date']}${d['ongoing'] == true ? ' · en cours' : ''}'))).toList(), onChanged:(value)=>setState(()=>selectedCycleDay=value)),
          info(cycle.status), if (cycle.explanation.isNotEmpty) info(cycle.explanation),
          row('Batterie pleine', cycle.full), row('Fin solaire (< 10 W)', cycle.solarEnd), row('Batterie prend le relais', cycle.dischargeStart), row('Fin de décharge batterie', cycle.dischargeEnd), row('Recharge au prochain ensoleillement', cycle.recharge), row(cycle.durationLabel, cycle.dischargeDuration),
          info('Fin solaire confirmée après 30 min ; arrêt de décharge confirmé après 2 min. Pauses et trous exclus de la durée.'),
          row('Surplus après plein', cycle.surplus),
        ],
        if (days.isNotEmpty) ExpansionTile(tilePadding:EdgeInsets.zero, title:const Text('Historique des cycles',style:TextStyle(fontSize:14)), children:[for(final day in days.take(14)) ListTile(dense:true,title:Text('${day['date']}'),trailing:const Icon(Icons.chevron_right),onTap:()=>setState(()=>selectedCycleDay=day['date'] as String))]),
      ]),
    ];
  }
  List<Widget> panelsView() {
    final readings = solarPanelReadings(current,DateTime.now(),connectionOk:error == null);
    Widget grid(Iterable<SolarPanelReading> panels) => GridView.count(crossAxisCount:2, mainAxisSpacing:10, crossAxisSpacing:10, mainAxisExtent:160, shrinkWrap:true, physics:const NeverScrollableScrollPhysics(), children:[for(final panel in panels) SolarPanelTile(reading:panel)]);
    return [box('Panneaux solaires', [info('Maison · 4 panneaux'),grid(readings.where((p)=>p.group=='Maison')),info('Cabanon · 2 panneaux'),grid(readings.where((p)=>p.group=='Cabanon')),info('La puissance affichée est la production. Un tiret signifie que la mesure est indisponible. Si seule la production totale du cabanon est connue, sa répartition est indiquée comme estimée.')])];
  }
  List<Widget> devicesView() {
    if (settings == null) return [info(loading ? 'Chargement des équipements…' : 'État des équipements indisponible.')];
    final timestamp = DateTime.tryParse('${current['timestamp'] ?? ''}');
    final fresh = error == null && timestamp != null && DateTime.now().difference(timestamp).inSeconds.abs() <= 90 && settingsUpdated != null && DateTime.now().difference(settingsUpdated!).inSeconds <= 60;
    final devices = equipmentList(settings!, current, fresh: fresh, now: DateTime.now());
    const groups = ['Installation maison', 'Installation cabanon', 'Équipement commun'];
    Color statusColor(EquipmentHealth health) => switch (health) { EquipmentHealth.online => green, EquipmentHealth.offline => const Color(0xffff8797), EquipmentHealth.warning || EquipmentHealth.waiting => gold, EquipmentHealth.disabled => Colors.blueGrey };
    return [info(fresh ? 'État actualisé automatiquement' : 'Les états ne sont pas à jour.'), for (final group in groups) box(group, [for (final device in devices.where((d) => d.group == group)) Padding(padding: const EdgeInsets.symmetric(vertical: 9), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(Icons.circle, size: 10, color: statusColor(device.health)), const SizedBox(width: 10), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(device.name, style: const TextStyle(fontWeight: FontWeight.w600)), if (device.detail.isNotEmpty) Text(device.detail, style: TextStyle(color: Colors.blueGrey[200], fontSize: 12)), Text(device.status, style: TextStyle(color: statusColor(device.health)))]))]))]), info('Les réglages, la régulation et le redémarrage ne sont pas encore disponibles dans cette application de test.')];
  }
}

class SolarPanelTile extends StatelessWidget {
  const SolarPanelTile({super.key,required this.reading});
  final SolarPanelReading reading;
  @override Widget build(BuildContext context) {
    final available=reading.power != null;
    final details=reading.estimated?'Répartition estimée':!available?'Mesure en attente':reading.voltage != null && reading.current != null?'${reading.voltage!.toStringAsFixed(1).replaceAll('.', ',')} V · ${reading.current!.toStringAsFixed(2).replaceAll('.', ',')} A':'Mesure reçue';
    return Container(key:ValueKey('panneau-${reading.group}-${reading.number}'),decoration:BoxDecoration(borderRadius:BorderRadius.circular(13),border:Border.all(color:available?blue:const Color(0xff2a3c51)),gradient:LinearGradient(begin:Alignment.topLeft,end:Alignment.bottomRight,colors:available?[const Color(0xff245bac),const Color(0xff0d3476)]:[const Color(0xff213248),const Color(0xff152437)])),child:ClipRRect(borderRadius:BorderRadius.circular(12),child:CustomPaint(painter:_PanelGridPainter(),child:Padding(padding:const EdgeInsets.all(12),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('Panneau ${reading.number}',style:const TextStyle(fontWeight:FontWeight.w600)),const Spacer(),Text(number(reading.power,'W'),style:const TextStyle(fontSize:23,fontWeight:FontWeight.bold)),const SizedBox(height:4),Text(details,maxLines:2,overflow:TextOverflow.ellipsis,style:const TextStyle(fontSize:11,color:Color(0xffd8e9ff)))])))));
  }
}
class _PanelGridPainter extends CustomPainter {
  @override void paint(Canvas canvas,Size size){final paint=Paint()..color=Colors.white.withValues(alpha:.12)..strokeWidth=1;for(var i=1;i<4;i++){canvas.drawLine(Offset(size.width*i/4,0),Offset(size.width*i/4,size.height),paint);canvas.drawLine(Offset(0,size.height*i/4),Offset(size.width,size.height*i/4),paint);}}
  @override bool shouldRepaint(covariant _PanelGridPainter oldDelegate)=>false;
}

Json demoStatus()=>{'raspberry_temperature_c':42.1,'current':{'timestamp':DateTime.now().toIso8601String(),'production_w':1050,'consumption_w':420,'import_w':0,'export_w':30,'battery_enabled':true,'battery_soc_pct':63,'battery_timestamp':DateTime.now().millisecondsSinceEpoch/1000,'battery_ac_charge_w':600,'battery_ac_discharge_w':0,'pv2_w':200,'dtu_state':'online','linky_state':'online','shelly_state':'online','tp_link_state':'online','tongou_state':'online','surplus_simulation':{'dtu':{'state':'online','timestamp':DateTime.now().millisecondsSinceEpoch/1000,'panels':[for(var i=1;i<=4;i++){'port':i,'power_w':200+i*10}]}},'hoymiles_proxy':{'state':'online','timestamp':DateTime.now().millisecondsSinceEpoch/1000,'panels':[{'port':1,'power_w':95},{'port':2,'power_w':105}]}},'history':List.generate(24,(i)=>{'timestamp':DateTime.now().subtract(Duration(minutes:(23-i)*15)).toIso8601String(),'production_w':i*45,'consumption_w':300+i*5,'import_w':i<6?100:0,'export_w':i>18?25:0,'battery_charge_w':i>6?200:0,'battery_discharge_w':i<=6?80:0})};
Json demoReport()=>{'from_time':DateTime(DateTime.now().year,DateTime.now().month,1).toIso8601String(),'to_time':DateTime.now().toIso8601String(),'production_kwh':8.2,'consumption_kwh':6.1,'export_kwh':1.2,'battery_charge_kwh':2.3,'battery_discharge_kwh':1.1,'total_cost':1.48,'subscription':0.5,'local_energy_kwh':4.9,'billing':{'hp_kwh':2.1,'hc_kwh':1.0},'tariffs':{'hp_eur_kwh':0.25,'hc_eur_kwh':0.20,'abonnement_journalier_eur':0.5},'annual_real_readings':{'start':'2026-01-01','hp_kwh':350,'hc_kwh':120,'production_kwh':780,'export_kwh':120,'battery_charge_kwh':200,'battery_discharge_kwh':170,'reference_2025':{'hp_kwh':1200,'hc_kwh':400,'hp_eur_kwh':0.25,'hc_eur_kwh':0.20,'subscription_start':'2025-01-01','end':'2025-12-31','subscription_monthly_eur':12}}};
Json demoBattery()=>{'days':[{'date':DateTime.now().toIso8601String().substring(0,10),'ongoing':true,'display':['Exemple','—','—','19:30','19:32','3 h 20','—']}]};
Json demoSettings()=>{for(final key in ['tp_link','tongou_relay','linky','shelly','shelly2','battery']) key:{'enabled':true},'wireless_interfaces':[{'interface':'wlan1','name':'Alfa · Wi-Fi DTU','connected':true},{'interface':'wlan2','name':'Alfa · Wi-Fi cabanon','connected':true}],'esp_devices':[{'id':'proxy','name':'ESP32 · proxy Bluetooth','enabled':true,'connected':true,'checked_at':DateTime.now().millisecondsSinceEpoch/1000},{'id':'router','name':'ESP32 · routeur cabanon','enabled':true,'connected':true,'checked_at':DateTime.now().millisecondsSinceEpoch/1000}]};
