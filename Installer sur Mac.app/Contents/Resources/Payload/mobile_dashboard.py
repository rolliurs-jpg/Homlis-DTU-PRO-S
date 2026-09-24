"""Tableau de bord mobile local, compatible avec un accès privé Tailscale.

Le serveur est strictement en lecture seule. Il ne contacte jamais la DTU, le
Dinky ou le Shelly : les mesures lui sont transmises par l'application
principale après chaque cycle de collecte.
"""

from __future__ import annotations

import json
import csv
from battery_monitor import cycle_values, CYCLE_HEADINGS
import time
import secrets
from datetime import datetime
from io import StringIO
import ipaddress
import math
import os
import shutil
import socket
import subprocess
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    from PIL import Image
except ImportError:
    Image = None


MOBILE_HTML = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#071a33">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Solaire">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="apple-touch-icon" href="/icon-192.png">
  <title>Boîte noire Hoymiles</title>
  <style>
[hidden]{display:none!important}
    :root{color-scheme:dark;--bg:#061426;--panel:#0d223b;--line:#1d3b5c;--text:#f8fafc;--muted:#9db2c8;--blue:#3b82f6;--navy:#4f7cff;--green:#22c55e;--yellow:#ffd000;--red:#ef4444}
    *{box-sizing:border-box}body{margin:0;background:linear-gradient(160deg,#071a33,#04101f 70%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}
    main{max-width:780px;margin:auto;padding:calc(18px + env(safe-area-inset-top)) 16px calc(30px + env(safe-area-inset-bottom))}
    header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:18px}h1{font-size:23px;margin:0 0 5px}.sub{color:var(--muted);font-size:13px}.live{background:#123354;border:1px solid #2a5279;border-radius:999px;padding:7px 10px;font-size:12px;white-space:nowrap}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);margin-right:6px}.quality{color:var(--muted);font-size:12px;margin-top:5px}.quality strong{color:var(--text)}
    .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.card{background:rgba(13,34,59,.92);border:1px solid var(--line);border-radius:17px;padding:14px;min-height:112px;box-shadow:0 10px 25px rgba(0,0,0,.16)}.card.wide{grid-column:1/-1}.label{color:var(--muted);font-size:12px;margin-bottom:8px}.value{font-size:29px;font-weight:750;letter-spacing:-.7px}.unit{font-size:14px;font-weight:500;color:var(--muted);margin-left:3px}.hint{font-size:12px;color:var(--muted);margin-top:7px}.pv .value{color:#7fa2ff}.home .value{color:#fff}.linky .value{color:var(--green)}.gridflow.import .value{color:var(--green)}.gridflow.export .value{color:var(--yellow)}
    canvas{width:100%;height:210px;display:block;margin-top:8px}.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:11px}.key:before{content:"";display:inline-block;width:16px;height:3px;border-radius:3px;background:var(--c);vertical-align:middle;margin-right:5px}
    .states{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.state{border:1px solid var(--line);border-radius:12px;padding:10px 8px;text-align:center;color:var(--muted);font-size:11px}.state strong{display:block;color:var(--text);font-size:13px;margin-bottom:4px}.state.ok{border-color:#17683b}.state.warn{border-color:#8a5b08}.state.off{border-color:#8f2929}.foot{text-align:center;color:#6f89a4;font-size:11px;margin-top:18px}@media(min-width:650px){.grid{grid-template-columns:repeat(4,1fr)}.card.wide{grid-column:1/-1}.states{max-width:520px;margin:auto}}
  </style>
</head>
<body><main>
  <header><div><h1>Boîte noire Hoymiles</h1><div class="sub" id="updated">En attente de la première mesure…</div><div class="quality" id="quality">Qualité : en attente</div></div><div class="live"><span class="dot" id="liveDot"></span><span id="liveText">Connexion</span></div></header>
  <aside id="monitorAlarm" role="alert" style="padding:12px;margin-bottom:14px;border:1px solid #8a5b08;border-radius:12px">Surveillance en attente…</aside>
  <section class="grid">
    <article class="card pv"><div class="label">Production solaire</div><div class="value" id="pv">—</div><div class="hint" id="pvSource">DTU / Shelly</div></article>
    <article class="card home"><div class="label">Consommation maison</div><div class="value" id="home">—</div><div class="hint">Calculée avec les mesures disponibles ; — si incomplètes</div></article>
    <article class="card gridflow" id="flowCard"><div class="label" id="flowLabel">Réseau</div><div class="value" id="flow">—</div><div class="hint" id="flowHint">Linky / Shelly</div></article>
    <article class="card linky"><div class="label">Linky / Dinky</div><div class="value" id="linky">—</div><div class="hint">Téléinformation locale</div></article>
    <article class="card wide" id="batteryCard" hidden><div class="label">Batterie Zendure</div><svg viewBox="0 0 340 125" role="img" aria-label="Batterie" style="width:100%;max-width:340px;display:block;margin:auto">
<rect x="24" y="14" width="280" height="96" rx="12" fill="none" stroke="#64748b" stroke-width="4" id="batteryOutline"/>
<rect x="307" y="42" width="12" height="40" rx="3" fill="#64748b" id="batteryTip"/>
<rect x="31" y="21" width="266" height="82" rx="6" fill="#1d3b5c"/>
<rect x="31" y="21" width="0" height="82" rx="6" fill="#64748b" id="batteryFill"/>
<rect x="104" y="37" width="120" height="50" rx="8" fill="#0d223b"/>
<text x="164" y="73" text-anchor="middle" fill="white" font-size="32" font-weight="700" id="batteryPercent">—</text></svg>
<div id="batteryValues" style="text-align:center;font-weight:700;margin-top:8px">Mesure indisponible</div></article>
    <article class="card wide" id="fullBatteryCard" hidden>
      <div class="label">Cycle batterie : plein, surplus et décharge</div>
      <div id="fullBatteryStatus" class="hint" role="status">Chargement du bilan…</div>
      <details><summary style="padding:12px 0">Voir le cycle d’aujourd’hui</summary><div id="fullBatteryToday"></div></details>
      <details style="margin-top:12px"><summary>Historique des jours enregistrés</summary><div id="fullBatteryHistory"></div></details>
      <a href="/battery-full.csv" download="surplus_apres_batterie_pleine.csv" style="display:inline-block;color:#93c5fd;padding:12px 0">Exporter le bilan CSV</a>
      <div class="hint">Injection nette mesurée par Shelly après le premier 100 %. Les trous de mesure sont exclus.
      Fin solaire estimée après 30 min à 10 W ou moins sur toutes les lignes mesurées ; sinon cumul provisoire jusqu’aux relevés disponibles, limité à minuit.
      Une restitution batterie peut aussi contribuer au surplus. Le temps en décharge exclut les pauses et les trous de mesure. Décharge et recharge sont confirmées après 2 minutes au-dessus de 20 W nets ; une recharge le lendemain reste sur la ligne du plein de la veille.</div>
    </article>
    <article class="card wide"><div class="label">Dernières heures</div><div class="legend"><span class="key" style="--c:#4f7cff">Production</span><span class="key" style="--c:#fff">Consommation</span><span class="key" style="--c:#22c55e">Soutirage</span><span class="key" style="--c:#ffd000">Injection</span></div><canvas id="chart"></canvas></article>
    <article class="card wide"><div class="label">État des appareils</div><div class="states"><div class="state" id="dtuState"><strong>DTU</strong><span>—</span></div><div class="state" id="linkyState"><strong>Dinky</strong><span>—</span></div><div class="state" id="shellyState"><strong>Shelly</strong><span>—</span></div></div></article>
  </section>
  <div class="foot">Lecture seule · données fournies par l’ordinateur de la maison · aucune commande envoyée aux appareils</div>
</main>
<script>
const $=id=>document.getElementById(id), fmt=v=>v==null?'—':`${Math.round(v)}<span class="unit">W</span>`;
function state(id,value){const el=$(id),txt=el.querySelector('span');el.className='state '+(value==='online'?'ok':value==='offline'?'off':'warn');txt.textContent=value==='online'?'Connecté':value==='offline'?'Hors ligne':'En attente'}
function ageLabel(seconds){if(seconds<2)return 'à l’instant';if(seconds<60)return`il y a ${Math.round(seconds)} s`;return`il y a ${Math.floor(seconds/60)} min`}
function freshness(timestamp){if(!timestamp)return{age:Infinity,label:'Aucune mesure',color:'#ef4444'};let age=Math.max(0,(Date.now()-new Date(timestamp).getTime())/1000);if(age<=90)return{age,label:'En direct',color:'#22c55e'};if(age<=180)return{age,label:'Retard',color:'#f59e0b'};return{age,label:'Données anciennes',color:'#ef4444'}}
function draw(history){const c=$('chart'),dpr=window.devicePixelRatio||1,w=c.clientWidth,h=c.clientHeight;c.width=w*dpr;c.height=h*dpr;const x=c.getContext('2d');x.scale(dpr,dpr);x.clearRect(0,0,w,h);x.strokeStyle='#1d3b5c';x.lineWidth=1;for(let i=0;i<4;i++){let y=15+i*(h-30)/3;x.beginPath();x.moveTo(0,y);x.lineTo(w,y);x.stroke()}if(!history||history.length<2)return;let vals=[];history.forEach(p=>['production_w','consumption_w','import_w','export_w'].forEach(k=>{if(p[k]!=null)vals.push(p[k])}));let max=Math.max(100,...vals)*1.12;[['production_w','#4f7cff'],['consumption_w','#ffffff'],['import_w','#22c55e'],['export_w','#ffd000']].forEach(([k,col])=>{x.strokeStyle=col;x.lineWidth=k==='production_w'?2.6:2;x.beginPath();let started=false;history.forEach((p,i)=>{if(p[k]==null){started=false;return}let px=i*w/(history.length-1),py=h-12-(p[k]/max)*(h-26);if(!started){x.moveTo(px,py);started=true}else x.lineTo(px,py)});x.stroke()})}
let lastReceived=null, lastMonitor=null, failedSince=null;
function showMonitoring(){
 const el=$('monitorAlarm'), now=Date.now(), computer=(lastMonitor&&lastMonitor.computer)||'ordinateur';
 el.style.whiteSpace='pre-line';
 if(failedSince!==null){
   const age=(now-(lastReceived||failedSince))/1000;
   el.textContent=(age>=300?'SUIVI INACCESSIBLE':'CONNEXION INTERROMPUE')+` — ${computer} ne répond plus depuis ${Math.floor(age/60)} min. Les valeurs affichées ne sont plus actualisées.\n`+
      'À vérifier : ordinateur allumé, logiciel ouvert, connexion Internet et Tailscale si vous êtes à distance. La cause exacte est inconnue ; les panneaux peuvent continuer à produire.';
   el.style.borderColor='#ef4444'; return;
 }
 const m=lastMonitor;
 if(!m){el.textContent='État de surveillance indisponible. Actualisez l’appli après la mise à jour du logiciel PC/Mac.';return;}
 const age=(m.age_seconds||0)+(lastReceived?(now-lastReceived)/1000:0), active=m.active||age>=(m.threshold_seconds||300);
 el.style.borderColor=active?'#ef4444':'#17683b';
 el.textContent=active?`SUIVI INTERROMPU — ${computer} : aucune mesure enregistrée depuis ${Math.floor(age/60)} min.\n`+
   'Vérifiez la collecte dans le logiciel et l’état DTU, Dinky et Shelly. La cause exacte n’est pas identifiée ; cela ne prouve pas un arrêt des panneaux.':
   m.last_measure?`SUIVI EN COURS — ${computer} : les mesures sont enregistrées normalement.`:'DÉMARRAGE — en attente de la première mesure.';
 if(m.last_ping){
   const pingAge=(now-m.last_ping*1000)/1000;
   el.textContent+=pingAge<300?'\nSurveillance extérieure : signal reçu par Healthchecks.':
      '\nSurveillance extérieure : dernier signal reçu '+new Date(m.last_ping*1000).toLocaleString('fr-FR')+'. Vérifiez la connexion Internet de l’ordinateur.';
 }else if(m.remote_configured){
   el.textContent+='\nSurveillance extérieure : '+m.remote+'.';
 }else{
   el.textContent+='\nNotifications par mail non configurées sur cet ordinateur (bouton Alarmes).';
 }
 if(m.recovery){
   const f=new Date(m.recovery.from*1000).toLocaleString('fr-FR'), t=new Date(m.recovery.to*1000).toLocaleString('fr-FR');
   el.textContent+=`\nInterruption passée de l’enregistrement : du ${f} au ${t} (${Math.floor(m.recovery.seconds/60)} min). Suivi rétabli à cette heure.`;
 }
}
setInterval(showMonitoring,1000);
function drawBattery(s,fresh=true){
 const valid=fresh&&Number.isFinite(s.battery_soc_pct)&&Number.isFinite(s.battery_charge_w)&&Number.isFinite(s.battery_discharge_w);
 const soc=fresh&&Number.isFinite(s.battery_soc_pct)?Math.max(0,Math.min(100,s.battery_soc_pct)):null;
 const net=valid?s.battery_charge_w-s.battery_discharge_w:0;
 const color=valid&&net>20?'#22c55e':valid&&net< -20?'#ef4444':'#94a3b8';
 $('batteryFill').setAttribute('width',soc==null?0:266*soc/100);
 $('batteryFill').setAttribute('fill',color);$('batteryOutline').setAttribute('stroke',color);$('batteryTip').setAttribute('fill',color);
 $('batteryPercent').textContent=soc==null?'—':Math.round(soc)+' %';
 $('batteryValues').textContent=!valid?'Mesure indisponible ou ancienne':net>20?`En charge · ${Math.round(net)} W`:net< -20?`En décharge · ${Math.round(-net)} W`:soc>=100?'Pleine · au repos':'Au repos';
 $('batteryValues').style.color=color;
}
let fullBatteryReceived=0;
function fullBatteryText(r){
 const d=r.display;
 if(!d)return 'Cycle indisponible — actualisez le logiciel sur l’ordinateur.';
 return `${d[0]} · Batterie pleine à ${d[1]}\nSurplus après plein : ${d[2]}\nFin solaire : ${d[3]}\nDécharge dès : ${d[4]}\nTemps en décharge : ${d[5]}\nRecharge dès : ${d[6]}`+(d[7]&&d[7]!=='—'?`\n${d[7]}`:'');
}

function renderFullBattery(d){
 const days=d.days||[],today=days.find(r=>r.ongoing);
 $('fullBatteryToday').style.whiteSpace='pre-line';
 $('fullBatteryToday').style.marginTop='10px';
 $('fullBatteryToday').textContent=today?fullBatteryText(today):'Aucun relevé batterie pour aujourd’hui.';
 $('fullBatteryHistory').style.whiteSpace='pre-line';
 $('fullBatteryHistory').textContent=days.filter(r=>!r.ongoing).map(fullBatteryText).join('\n\n')||'Pas encore de journée précédente enregistrée.';
 $('fullBatteryStatus').textContent=d.updated_at?'Bilan actualisé le '+new Date(d.updated_at).toLocaleString('fr-FR'):'';
}
async function refreshFullBattery(){
 if($('fullBatteryCard').hidden||Date.now()-fullBatteryReceived<30000)return;
 try{
  const r=await fetch('/api/battery-full',{cache:'no-store',signal:AbortSignal.timeout(10000)});
  if(!r.ok)throw Error();
  renderFullBattery(await r.json());fullBatteryReceived=Date.now();
 }catch(e){$('fullBatteryStatus').textContent='Bilan non actualisé — connexion ou historique indisponible. Les valeurs précédentes sont conservées.'}
}
async function refresh(){try{const r=await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)throw Error();const d=await r.json(),s=d.current||{},fresh=freshness(s.timestamp);$('batteryCard').hidden=!s.battery_enabled;$('fullBatteryCard').hidden=!s.battery_enabled;refreshFullBattery();drawBattery(s,fresh.age<=90);$('pv').innerHTML=fmt(s.production_w);$('pvSource').textContent=s.production_source||'DTU / Shelly';$('home').innerHTML=fmt(s.consumption_w);$('linky').innerHTML=fmt(s.linky_w);let exp=s.export_w||0,imp=s.import_w||0,exporting=exp>1;$('flowCard').className='card gridflow '+(exporting?'export':'import');$('flowLabel').textContent=exporting?'Injection vers le réseau':'Soutirage du réseau';$('flow').innerHTML=fmt(exporting?exp:imp);$('flowHint').textContent=(s.grid_source||'Mesure réseau locale')+(exporting?' · injection':' · soutirage');$('updated').textContent=s.timestamp?`Dernière mesure ${ageLabel(fresh.age)} · ${new Date(s.timestamp).toLocaleString('fr-FR')}`:'En attente de la première mesure…';const equipment=s.equipment||{linky:true,shelly:true};$('linky').closest('article').hidden=!equipment.linky;$('home').closest('article').hidden=!equipment.shelly;$('flowCard').hidden=!equipment.shelly;$('linkyState').hidden=!equipment.linky;$('shellyState').hidden=!equipment.shelly;const labels={complete:'<strong>Mesures disponibles</strong>',backup:'<strong>Mesure de secours</strong> · DTU absente, Shelly utilisé',partial:'<strong>Données partielles</strong>',missing:'<strong>Données absentes</strong>'};$('quality').innerHTML=(!equipment.shelly&&s.dtu_state==='online')?'Mesures DTU disponibles':labels[s.quality]||'Qualité : en attente';state('dtuState',s.dtu_state);state('linkyState',s.linky_state);state('shellyState',s.shelly_state);$('liveText').textContent=fresh.label;$('liveDot').style.background=fresh.color;draw(d.history);lastReceived=Date.now();lastMonitor=d.monitoring;failedSince=null;showMonitoring()}catch(e){if(failedSince===null)failedSince=Date.now();showMonitoring();drawBattery({},false);$('liveText').textContent='Serveur inaccessible';$('liveDot').style.background='#ef4444'}}
refresh();setInterval(refresh,5000);addEventListener('resize',refresh);
</script></body></html>"""

MOBILE_MANIFEST = {
    "name": "Boîte noire Hoymiles — Solaire",
    "short_name": "Solaire",
    "description": "Lecture à distance de la production et de la consommation solaire.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#061426",
    "theme_color": "#071a33",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    ],
}

_ICON_CACHE = {}


def _mobile_icon(size):
    """Convertit le logo ICO existant en PNG pour Android et iOS."""
    if size in _ICON_CACHE:
        return _ICON_CACHE[size]
    if Image is None:
        return None
    icon_path = Path(__file__).with_name("icone_panneau_solaire.ico")
    try:
        with Image.open(icon_path) as source:
            icon = source.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
            output = BytesIO()
            icon.save(output, format="PNG", optimize=True)
            _ICON_CACHE[size] = output.getvalue()
            return _ICON_CACHE[size]
    except (OSError, ValueError):
        return None


def _clean_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_this_computer(address):
    """True lorsque le navigateur tourne sur le même ordinateur que le suivi."""
    local = {'127.0.0.1', '::1'}
    try:
        local.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 80))
            local.add(sock.getsockname()[0])
    except OSError:
        pass
    return address in local


class MobileDashboard:
    def __init__(self, host="0.0.0.0", port=8765, max_history=360):
        self.host = str(host or "0.0.0.0")
        self.port = int(port or 8765)
        self.max_history = max(30, int(max_history))
        self._lock = threading.Lock()
        self._payload = {"current": {}, "history": []}
        self._server = None
        self._thread = None
        self.error = ""
        self.monitoring = None
        self.battery_report = None
        self.data_service = None
        self.ui_action = None
        self.csrf = secrets.token_urlsafe(32)
        self._battery_lock = threading.Lock()
        self._battery_cache = None
        self._battery_cache_time = 0

    def start(self):
        dashboard = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlparse(self.path).path
                if path in ("/", "/index.html"):
                    source = Path(__file__).with_name('dashboard_ui.html')
                    html = source.read_text(encoding='utf-8') if source.exists() else MOBILE_HTML
                    self._send(html.replace('__ACTION_TOKEN__',dashboard.csrf).encode("utf-8"), "text/html; charset=utf-8")
                    return
                if path == '/classic-mobile':
                    self._send(MOBILE_HTML.encode('utf-8'), 'text/html; charset=utf-8')
                    return
                if path in ('/api/report','/report.csv','/api/settings'):
                    if dashboard.data_service is None:
                        self.send_error(503, 'Reports are starting')
                        return
                    try:
                        if path == '/api/settings':
                            report = dashboard.data_service.settings()
                            report['desktop_actions'] = _is_this_computer(self.client_address[0])
                        else:
                            period = parse_qs(urlparse(self.path).query).get('period',['today'])[0]
                            report = dashboard.data_service.report(period)
                        if path == '/report.csv':
                            out=StringIO();writer=csv.writer(out,delimiter=';')
                            writer.writerow(['Date','Production mesurée W','Maison W','Achat W','Injection W','Charge batterie W','Décharge batterie W'])
                            for r in report['history']:
                                writer.writerow([r.get(k) for k in ('timestamp','production_w','consumption_w','import_w','export_w','battery_charge_w','battery_discharge_w')])
                            self._send(('\ufeff'+out.getvalue()).encode('utf-8'),'text/csv; charset=utf-8')
                        else:
                            self._send(json.dumps(report,ensure_ascii=False,allow_nan=False).encode('utf-8'),'application/json; charset=utf-8')
                    except ValueError:
                        self.send_error(400, 'Invalid period or data')
                    except (OSError, csv.Error):
                        self.send_error(503, 'History temporarily unavailable')
                    return
                if path in ("/api/battery-full", "/battery-full.csv"):
                    try:
                        report = dashboard.get_battery_report()
                    except (OSError, ValueError, csv.Error):
                        self.send_error(503, "Battery history temporarily unavailable")
                        return
                    if path.endswith('.csv'):
                        out = StringIO()
                        writer = csv.writer(out, delimiter=';')
                        writer.writerow(CYCLE_HEADINGS)
                        for row in report['days']:
                            writer.writerow(cycle_values(row))
                        self._send(('\ufeff'+out.getvalue()).encode('utf-8'), 'text/csv; charset=utf-8')
                    else:
                        self._send(json.dumps(report, ensure_ascii=False, allow_nan=False).encode('utf-8'), 'application/json; charset=utf-8')
                    return
                if path == "/api/status":
                    with dashboard._lock:
                        payload = deepcopy(dashboard._payload)
                    if dashboard.monitoring is not None:
                        payload["monitoring"] = dashboard.monitoring()
                    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    self._send(body, "application/json; charset=utf-8")
                    return
                if path == "/manifest.webmanifest":
                    body = json.dumps(MOBILE_MANIFEST, ensure_ascii=False).encode("utf-8")
                    self._send(body, "application/manifest+json; charset=utf-8")
                    return
                if path in ("/icon-192.png", "/icon-512.png"):
                    size = 192 if "192" in path else 512
                    body = _mobile_icon(size)
                    if body is not None:
                        self._send(body, "image/png")
                        return
                    self.send_error(404)
                    return
                if path == "/favicon.ico":
                    try:
                        body = Path(__file__).with_name("icone_panneau_solaire.ico").read_bytes()
                    except OSError:
                        self.send_error(404)
                        return
                    self._send(body, "image/x-icon")
                    return
                if path == "/health":
                    self._send(b'{"status":"ok"}', "application/json")
                    return
                self.send_error(404)

            def do_POST(self):
                if urlparse(self.path).path != '/api/action':
                    self.send_error(404); return
                if not secrets.compare_digest(self.headers.get('X-Action-Token',''),dashboard.csrf):
                    self.send_error(403); return
                origin = self.headers.get('Origin')
                if origin and urlparse(origin).netloc != self.headers.get('Host'):
                    self.send_error(403); return
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0 < length <= 16384:
                        self.send_error(413); return
                    data=json.loads(self.rfile.read(length))
                    if not isinstance(data,dict):
                        raise ValueError('Objet attendu')
                    action=data.get('action')
                    allowed={'settings','tariffs','pause','classic','diagnostic','capture','alarm','manual_edf','export','autostart'}
                    if action not in allowed:
                        raise ValueError('Action inconnue')
                    if action == 'autostart':
                        if not _is_this_computer(self.client_address[0]):
                            self.send_error(403,'Open this page on the computer to change automatic startup');return
                        if dashboard.data_service is None:
                            self.send_error(503);return
                        response=dashboard.data_service.set_autostart(data.get('values',{}).get('enabled'))
                        self._send(json.dumps(response,ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8')
                        return
                    if action not in {'settings','tariffs','pause'} and self.client_address[0] not in ('127.0.0.1','::1'):
                        self.send_error(403,'This action opens a window on the home computer');return
                    if dashboard.ui_action is None:
                        self.send_error(503);return
                    response=dashboard.ui_action(action,data.get('values',{}))
                    self._send(json.dumps(response,ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8')
                except (ValueError,TypeError,KeyError) as exc:
                    self._send(json.dumps({'error':str(exc)},ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8')

            def _send(self, body, content_type):
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *_args):
                return

        try:
            self._server = ThreadingHTTPServer((self.host, self.port), Handler)
            self._server.daemon_threads = True
            self._thread = threading.Thread(target=self._server.serve_forever, name="mobile-dashboard", daemon=True)
            self._thread.start()
            return True
        except OSError as exc:
            self.error = str(exc)
            return False

    def get_battery_report(self):
        with self._battery_lock:
            if self._battery_cache is not None and time.monotonic()-self._battery_cache_time < 30:
                return deepcopy(self._battery_cache)
            rows = self.battery_report() if self.battery_report else []
            for row in rows:
                for source, target in [('full_at', 'full_time'), ('end_at', 'end_time')]:
                    row[target] = datetime.fromtimestamp(row[source]).strftime('%H:%M:%S') if row[source] is not None else None
            self._battery_cache = {'days': rows, 'updated_at': datetime.now().isoformat(timespec='seconds')}
            self._battery_cache_time = time.monotonic()
            return deepcopy(self._battery_cache)

    def update(self, current, history):
        safe_current = {key: (_clean_number(value) if key.endswith("_w") else value) for key, value in current.items()}
        safe_history = []
        for point in history[-self.max_history:]:
            safe_history.append({
                key: (_clean_number(value) if key.endswith("_w") else value)
                for key, value in point.items()
            })
        with self._lock:
            self._payload = {"current": safe_current, "history": safe_history}

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

    def urls(self):
        addresses = ["127.0.0.1"]
        try:
            addresses.extend(socket.gethostbyname_ex(socket.gethostname())[2])
        except OSError:
            pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("192.0.2.1", 80))
                addresses.append(sock.getsockname()[0])
        except OSError:
            pass
        tailscale_commands = [shutil.which("tailscale")]
        if os.name == "nt":
            tailscale_commands.append(r"C:\Program Files\Tailscale\tailscale.exe")
        else:
            tailscale_commands.extend([
                "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
                "/usr/local/bin/tailscale",
                "/opt/homebrew/bin/tailscale",
            ])
        for command in tailscale_commands:
            if not command or not os.path.isfile(command):
                continue
            try:
                result = subprocess.run(
                    [command, "ip", "-4"], capture_output=True, text=True,
                    timeout=2, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode == 0:
                    addresses.extend(line.strip() for line in result.stdout.splitlines())
                    break
            except (OSError, subprocess.SubprocessError):
                continue
        unique = []
        for address in addresses:
            if address and address not in unique:
                unique.append(address)
        tailnet = ipaddress.ip_network("100.64.0.0/10")
        def address_order(value):
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                return 3
            return 2 if address in tailnet else 0 if address.is_loopback else 1
        unique.sort(key=address_order)
        return [f"http://{address}:{self.port}" for address in unique]
