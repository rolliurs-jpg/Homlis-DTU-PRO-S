/* Données purement fictives : aucun appel réseau ni commande réelle. */
(() => {
  const stamp = () => new Date().toISOString();
  const history = Array.from({length: 48}, (_, i) => {
    const pv = Math.max(0, Math.round(1800 * Math.sin(Math.PI * i / 47)));
    const home = 420 + Math.round(60 * Math.sin(i / 3));
    const charge = Math.max(0, Math.round((pv - home) * .8));
    return {timestamp: new Date(Date.now() - (47-i)*300000).toISOString(), production_w:pv, consumption_w:home, export_w:Math.max(0,pv-home-charge), import_w:Math.max(0,home-pv), battery_charge_w:charge, battery_discharge_w:Math.max(0,home-pv)};
  });
  const now=Date.now()/1000, today=new Date().toISOString().slice(0,10);
  const panels=[1,2,3,4].map(port=>({port,power_w:240,voltage_v:38,current_a:6.3}));
  const status={raspberry_temperature_c:40, current:{timestamp:stamp(),battery_timestamp:now,production_w:1240,consumption_w:410,export_w:30,import_w:0,battery_enabled:true,battery_soc_pct:65,battery_charge_w:800,battery_discharge_w:0,battery_ac_charge_w:800,battery_ac_discharge_w:0,pv2_w:280,production_source:'Données fictives',grid_source:'Mesure simulée',quality:'complete',dtu_state:'online',linky_state:'online',shelly_state:'online',tp_link_state:'online',tongou_state:'online',hoymiles_proxy:{state:'online',timestamp:now,power_w:280,limit_pct:100,reason:'Lecture locale simulée via ESP32'},surplus_simulation:{commands_enabled:true,managed_panels:6,controlled_panels:6,hms1000_limit_pct:100,dtu_limit_pct:100,reason:'Priorité à la maison et à la charge batterie.',dtu:{state:'online',timestamp:now,port_limits_pct:[100,100,100,100],panels}},equipment:{linky:true,shelly:true}},history};
  const devices=['linky','shelly','shelly2','battery','tp_link','tongou_relay','hoymiles_proxy','esp_router'];
  const settings={desktop_actions:false,raspberry_service_enabled:true,settings_password_enabled:false,production_complete:true,wireless_interfaces:[],esp_devices:[],dtu_host:'Adresse fictive',...Object.fromEntries(devices.map(name=>[name,{enabled:true,host:'Adresse fictive'}]))};
  const report={from_time:new Date(Date.now()-86400000).toISOString(),to_time:stamp(),production_kwh:18.4,export_kwh:1.2,consumption_kwh:11.4,battery_charge_kwh:5.2,battery_discharge_kwh:3.1,battery_soc_pct:65,battery_available_kwh:3.74,battery_loss_kwh:.3,solar_after_export_kwh:17.2,local_energy_kwh:10.2,avoided_cost_eur:2.1,energy_cost:1.2,subscription:.6,total_cost:1.8,production_complete:true,billing:{import_kwh:5,hp_kwh:3,hc_kwh:2},tariffs:{hp_eur_kwh:.25,hc_eur_kwh:.20,abonnement_journalier_eur:.60},annual_real_readings:{start:'2026-01-01',as_of:today,hp_kwh:1128,hc_kwh:625,production_kwh:2120,export_kwh:223,battery_charge_kwh:400,battery_discharge_kwh:350},history};
  const cycles={days:[{date:today,ongoing:true,display:[today,'—','—','En attente','—','—','—','Données fictives'],full_at:null,discharge_at:null,recharge_at:null}]};
  window.fetch = async (url, options={}) => {
    const path=String(url);
    if (options.method && options.method.toUpperCase() !== 'GET') return new Response(JSON.stringify({error:'Démonstration : aucune commande réelle n’est envoyée.'}),{status:403,headers:{'Content-Type':'application/json'}});
    let data=path.startsWith('/api/status')?status:path.startsWith('/api/settings')?settings:path.startsWith('/api/report')?report:path.startsWith('/api/battery-full')?cycles:null;
    if(!data)return new Response('{}',{status:404});
    if(data===status){status.current.timestamp=stamp();status.current.battery_timestamp=Date.now()/1000;status.current.hoymiles_proxy.timestamp=Date.now()/1000;status.current.surplus_simulation.dtu.timestamp=Date.now()/1000;}
    return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});
  };
  document.addEventListener('click',event=>{const a=event.target.closest('a');if(a&&a.hasAttribute('download')){event.preventDefault();alert('Export non disponible en démonstration.')}},true);
})();
