const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../mobile_dashboard.py'),'utf8');
const script=source.split('<script>')[1].split('</script>')[0];
const nodes=new Map();
function element(id){if(!nodes.has(id))nodes.set(id,{setAttribute:function(k,v){this[k]=v},style:{},textContent:'',innerHTML:'',className:'',clientWidth:360,clientHeight:210,closest:()=>element(id+'Article'),
 querySelector:()=>({textContent:''}),getContext:()=>new Proxy({},{get:()=>()=>{}})});return nodes.get(id)}
const ctx=vm.createContext({document:{getElementById:element},window:{devicePixelRatio:1},Date,Math,Infinity,
 setInterval:()=>{},addEventListener:()=>{},AbortSignal,
 fetch:async()=>({ok:true,json:async()=>({current:{},history:[],monitoring:{age_seconds:0,last_measure:100,remote:'Non configurée'}})})});
vm.runInContext(script,ctx);
setImmediate(async()=>{
 for(const [linky,shelly] of [[true,false],[false,true],[true,true]]){
  ctx.fetch=async()=>({ok:true,json:async()=>({current:{equipment:{linky,shelly},dtu_state:'online',timestamp:new Date().toISOString()},history:[],monitoring:{age_seconds:0,last_measure:100}})});
  await vm.runInContext('refresh()',ctx);
  assert.notEqual(element('liveText').textContent,'Serveur inaccessible');
  assert.equal(element('linkyArticle').hidden,!linky);
  assert.equal(element('homeArticle').hidden,!shelly);
  assert.equal(element('linkyState').hidden,!linky);
  assert.equal(element('shellyState').hidden,!shelly);
 }
 vm.runInContext("lastMonitor={age_seconds:301,last_measure:100,remote:'Non configurée'};lastReceived=Date.now();showMonitoring()",ctx);
 assert.match(element('monitorAlarm').textContent,/SUIVI INTERROMPU/);
 vm.runInContext("lastMonitor={age_seconds:0,last_measure:100,remote:'Non configurée'};showMonitoring()",ctx);
 assert.match(element('monitorAlarm').textContent,/normalement/);
 vm.runInContext("failedSince=Date.now()-301000;lastReceived=failedSince;showMonitoring()",ctx);
 assert.match(element('monitorAlarm').textContent,/SUIVI INACCESSIBLE/);
 vm.runInContext("failedSince=null;lastMonitor=null;showMonitoring()",ctx);
 assert.match(element('monitorAlarm').textContent,/mise à jour/);
 vm.runInContext("lastMonitor={age_seconds:0,last_measure:100,computer:'Mac',last_ping:Date.now()/1000,remote_configured:true,recovery:{from:100,to:640,seconds:540}};lastReceived=Date.now();showMonitoring()",ctx);
 assert.match(element('monitorAlarm').textContent,/Interruption passée/);
 assert.match(element('monitorAlarm').textContent,/SUIVI EN COURS — Mac/);
 assert.doesNotMatch(element('monitorAlarm').textContent,/notifications à vérifier/);
 vm.runInContext("renderFullBattery({days:[{display:['2026-09-22','14:05','0.000 kWh (provisoire)','Non confirmée','19:00','2 h 00 min','23/09 à 08:00','—'],date:'2026-09-22',ongoing:true,full_time:'14:05:00',already_full:false,end_time:null,export_kwh:0,coverage_s:60,period_s:120},{display:['2026-09-21','Non observée','Indisponible','Non confirmée','Non observée','—','Non observée','—'],date:'2026-09-21',ongoing:false,full_time:null,export_kwh:null,period_s:0,coverage_s:0}]})",ctx);
 assert.match(element('fullBatteryToday').textContent,/0.000 kWh/);
 assert.match(element('fullBatteryToday').textContent,/provisoire/);
 assert.match(element('fullBatteryHistory').textContent,/Surplus après plein : Indisponible/);
 assert.doesNotMatch(element('fullBatteryHistory').textContent,/0.000 kWh/);
 assert.match(element('fullBatteryToday').textContent,/Recharge dès : 23\/09 à 08:00/);
 assert.doesNotMatch(element('fullBatteryToday').textContent,/Couverture/);
 vm.runInContext("drawBattery({battery_soc_pct:68,battery_charge_w:900,battery_discharge_w:0})",ctx);
 assert.equal(element('batteryPercent').textContent,'68 %');
 assert.equal(element('batteryFill').fill,'#22c55e');
 vm.runInContext("drawBattery({battery_soc_pct:42,battery_charge_w:0,battery_discharge_w:500})",ctx);
 assert.equal(element('batteryFill').fill,'#ef4444');
 assert.match(element('batteryValues').textContent,/En décharge/);
 vm.runInContext("drawBattery({},false)",ctx);
 assert.equal(element('batteryPercent').textContent,'—');
 console.log('Mobile battery cycle and graphic rendering passed');
 console.log('5 mobile alarm scenarios and 3 equipment configurations passed');
});
