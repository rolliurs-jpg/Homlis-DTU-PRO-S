import 'package:flutter/material.dart';

enum EnergySeries { production, house, imported, exported, charge, discharge }

const seriesLabels = <EnergySeries, String>{EnergySeries.production:'Production', EnergySeries.house:'Maison', EnergySeries.imported:'Achat EDF', EnergySeries.exported:'Injection EDF', EnergySeries.charge:'Charge batterie', EnergySeries.discharge:'Décharge batterie'};
const seriesColors = <EnergySeries, Color>{EnergySeries.production:Color(0xff94baff), EnergySeries.house:Colors.white, EnergySeries.imported:Color(0xffb79aff), EnergySeries.exported:Color(0xffffd27a), EnergySeries.charge:Color(0xff4ee2a4), EnergySeries.discharge:Color(0xffff8797)};

double? energyValue(dynamic sample, EnergySeries series) {
  if (sample is! Map) return null;
  double? val(String key) { final v = sample[key]; return v is num && v.isFinite ? v.toDouble() : null; }
  switch (series) {
    case EnergySeries.production: return val('production_w');
    case EnergySeries.house: return val('consumption_w');
    case EnergySeries.imported: return val('import_w');
    case EnergySeries.exported: return val('export_w');
    case EnergySeries.charge:
    case EnergySeries.discharge:
      final charge = val('battery_charge_w'), discharge = val('battery_discharge_w');
      if (charge == null || discharge == null) return null;
      final net = charge - discharge;
      if (series == EnergySeries.charge) return net >= 0 ? net : null;
      return net <= 0 ? net : null;
  }
}

String? historyTime(dynamic row) {
  if (row is! Map) return null;
  final date = DateTime.tryParse('${row['timestamp'] ?? ''}');
  if (date == null) return null;
  final local = date.toLocal();
  return '${local.hour.toString().padLeft(2,'0')}:${local.minute.toString().padLeft(2,'0')}';
}

class EnergyChart extends StatefulWidget {
  const EnergyChart({super.key, required this.history});
  final List history;
  @override State<EnergyChart> createState() => _EnergyChartState();
}

class _EnergyChartState extends State<EnergyChart> {
  EnergySeries? selected;
  int? cursor;
  @override void didUpdateWidget(covariant EnergyChart oldWidget) { super.didUpdateWidget(oldWidget); if (cursor != null && cursor! >= widget.history.length) cursor = null; }
  @override Widget build(BuildContext context) {
    final history = widget.history, visible = selected == null ? EnergySeries.values : [selected!];
    final sample = cursor != null && cursor! < history.length ? history[cursor!] : null;
    final entries = [for (final s in visible) if (energyValue(sample,s) != null) '${seriesLabels[s]} : ${energyValue(sample,s)!.abs().round()} W'];
    return Column(crossAxisAlignment:CrossAxisAlignment.start, children:[
      Text('Touchez une légende pour isoler une courbe ; touchez le graphique pour lire les valeurs.', style:TextStyle(color:Colors.blueGrey[200],fontSize:12)),
      const SizedBox(height:8),
      Wrap(spacing:6,runSpacing:3,children:[for(final series in EnergySeries.values) FilterChip(label:Text(seriesLabels[series]!),selected:selected==series,showCheckmark:false,labelStyle:TextStyle(color:seriesColors[series],fontSize:12),onSelected:(_)=>setState((){selected=selected==series?null:series;cursor=null;})), if(selected!=null) TextButton(onPressed:()=>setState((){selected=null;cursor=null;}),child:const Text('Toutes les courbes'))]),
      if(history.length < 2) const Padding(padding:EdgeInsets.symmetric(vertical:24),child:Text('Pas assez de mesures pour tracer les courbes.')) else LayoutBuilder(builder:(context,constraints){
        void position(double x) { final width=constraints.maxWidth; if(width<=0)return; setState(()=>cursor=((x/width).clamp(0.0,1.0)*(history.length-1)).round()); }
        return Column(children:[GestureDetector(behavior:HitTestBehavior.opaque,onTapDown:(d)=>position(d.localPosition.dx),onHorizontalDragUpdate:(d)=>position(d.localPosition.dx),child:SizedBox(height:180,width:double.infinity,child:CustomPaint(painter:_EnergyPainter(history,visible,cursor)))),
          Row(mainAxisAlignment:MainAxisAlignment.spaceBetween,children:[Text(historyTime(history.first)??'—',style:const TextStyle(fontSize:11)),const Text('Puissance (W)',style:TextStyle(fontSize:11)),Text(historyTime(history.last)??'—',style:const TextStyle(fontSize:11))])]);
      }),
      if(sample != null) Padding(padding:const EdgeInsets.only(top:10), child:Text('${historyTime(sample) ?? 'Heure inconnue'} · ${entries.isEmpty ? 'Mesures indisponibles' : entries.join('  ·  ')}',style:const TextStyle(fontSize:12))),
    ]);
  }
}

class _EnergyPainter extends CustomPainter {
  _EnergyPainter(this.history,this.visible,this.cursor);
  final List history;
  final List<EnergySeries> visible;
  final int? cursor;
  @override void paint(Canvas canvas, Size size) {
    if(history.length<2)return;
    final values=[for(final s in visible) for(final p in history) if(energyValue(p,s)!=null) energyValue(p,s)!];
    var upper=100.0, lower=0.0;
    for(final value in values){ if(value>upper)upper=value; if(value<lower)lower=value; }
    upper*=1.1; if(lower<0)lower*=1.1;
    double y(double value)=>size.height-8-(value-lower)/(upper-lower)*(size.height-16);
    final grid=Paint()..color=const Color(0xff35506c)..strokeWidth=1;
    canvas.drawLine(Offset(0,y(0)),Offset(size.width,y(0)),grid);
    for(final series in visible){
      final path=Path(); var started=false;
      for(var i=0;i<history.length;i++){
        final value=energyValue(history[i],series);
        if(value==null){started=false;continue;}
        final x=i*size.width/(history.length-1);
        if(started){path.lineTo(x,y(value));}else{path.moveTo(x,y(value));started=true;}
      }
      canvas.drawPath(path,Paint()..color=seriesColors[series]!..strokeWidth=2..style=PaintingStyle.stroke..strokeCap=StrokeCap.round);
    }
    if(cursor != null && cursor! < history.length){final x=cursor!*size.width/(history.length-1); canvas.drawLine(Offset(x,0),Offset(x,size.height),Paint()..color=Colors.white54..strokeWidth=1);}
  }
  @override bool shouldRepaint(covariant _EnergyPainter oldDelegate)=>oldDelegate.history!=history||oldDelegate.visible!=visible||oldDelegate.cursor!=cursor;
}
