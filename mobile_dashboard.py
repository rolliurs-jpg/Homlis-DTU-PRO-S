"""Tableau de bord mobile local, compatible avec un accès privé Tailscale.

Le serveur est strictement en lecture seule. Il ne contacte jamais la DTU, le
Dinky ou le Shelly : les mesures lui sont transmises par l'application
principale après chaque cycle de collecte.
"""

from __future__ import annotations

import json
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
from urllib.parse import urlparse

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
    :root{color-scheme:dark;--bg:#061426;--panel:#0d223b;--line:#1d3b5c;--text:#f8fafc;--muted:#9db2c8;--blue:#3b82f6;--navy:#4f7cff;--green:#22c55e;--yellow:#ffd000;--red:#ef4444}
    *{box-sizing:border-box}body{margin:0;background:linear-gradient(160deg,#071a33,#04101f 70%);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}
    main{max-width:780px;margin:auto;padding:calc(18px + env(safe-area-inset-top)) 16px calc(30px + env(safe-area-inset-bottom))}
    header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:18px}h1{font-size:23px;margin:0 0 5px}.sub{color:var(--muted);font-size:13px}.live{background:#123354;border:1px solid #2a5279;border-radius:999px;padding:7px 10px;font-size:12px;white-space:nowrap}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);margin-right:6px}
    .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.card{background:rgba(13,34,59,.92);border:1px solid var(--line);border-radius:17px;padding:14px;min-height:112px;box-shadow:0 10px 25px rgba(0,0,0,.16)}.card.wide{grid-column:1/-1}.label{color:var(--muted);font-size:12px;margin-bottom:8px}.value{font-size:29px;font-weight:750;letter-spacing:-.7px}.unit{font-size:14px;font-weight:500;color:var(--muted);margin-left:3px}.hint{font-size:12px;color:var(--muted);margin-top:7px}.pv .value{color:#7fa2ff}.home .value{color:#fff}.gridflow.import .value{color:var(--green)}.gridflow.export .value{color:var(--yellow)}
    canvas{width:100%;height:210px;display:block;margin-top:8px}.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:11px}.key:before{content:"";display:inline-block;width:16px;height:3px;border-radius:3px;background:var(--c);vertical-align:middle;margin-right:5px}
    .states{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.state{border:1px solid var(--line);border-radius:12px;padding:10px 8px;text-align:center;color:var(--muted);font-size:11px}.state strong{display:block;color:var(--text);font-size:13px;margin-bottom:4px}.state.ok{border-color:#17683b}.state.warn{border-color:#8a5b08}.state.off{border-color:#8f2929}.foot{text-align:center;color:#6f89a4;font-size:11px;margin-top:18px}@media(min-width:650px){.grid{grid-template-columns:repeat(4,1fr)}.card.wide{grid-column:1/-1}.states{max-width:520px;margin:auto}}
  </style>
</head>
<body><main>
  <header><div><h1>Boîte noire Hoymiles</h1><div class="sub" id="updated">En attente de la première mesure…</div></div><div class="live"><span class="dot" id="liveDot"></span><span id="liveText">Connexion</span></div></header>
  <section class="grid">
    <article class="card pv"><div class="label">Production solaire</div><div class="value" id="pv">—</div><div class="hint" id="pvSource">DTU / Shelly</div></article>
    <article class="card home"><div class="label">Consommation maison</div><div class="value" id="home">—</div><div class="hint">Calculée avec le Shelly</div></article>
    <article class="card gridflow" id="flowCard"><div class="label" id="flowLabel">Réseau</div><div class="value" id="flow">—</div><div class="hint" id="flowHint">Linky / Shelly</div></article>
    <article class="card"><div class="label">Linky / Dinky</div><div class="value" id="linky">—</div><div class="hint">Téléinformation locale</div></article>
    <article class="card wide"><div class="label">Dernières heures</div><div class="legend"><span class="key" style="--c:#4f7cff">Production</span><span class="key" style="--c:#fff">Consommation</span><span class="key" style="--c:#22c55e">Soutirage</span><span class="key" style="--c:#ffd000">Injection</span></div><canvas id="chart"></canvas></article>
    <article class="card wide"><div class="label">État des appareils</div><div class="states"><div class="state" id="dtuState"><strong>DTU</strong><span>—</span></div><div class="state" id="linkyState"><strong>Dinky</strong><span>—</span></div><div class="state" id="shellyState"><strong>Shelly</strong><span>—</span></div></div></article>
  </section>
  <div class="foot">Lecture seule · données fournies par l’ordinateur de la maison · aucune commande envoyée aux appareils</div>
</main>
<script>
const $=id=>document.getElementById(id), fmt=v=>v==null?'—':`${Math.round(v)}<span class="unit">W</span>`;
function state(id,value){const el=$(id),txt=el.querySelector('span');el.className='state '+(value==='online'?'ok':value==='offline'?'off':'warn');txt.textContent=value==='online'?'Connecté':value==='offline'?'Hors ligne':'En attente'}
function draw(history){const c=$('chart'),dpr=window.devicePixelRatio||1,w=c.clientWidth,h=c.clientHeight;c.width=w*dpr;c.height=h*dpr;const x=c.getContext('2d');x.scale(dpr,dpr);x.clearRect(0,0,w,h);x.strokeStyle='#1d3b5c';x.lineWidth=1;for(let i=0;i<4;i++){let y=15+i*(h-30)/3;x.beginPath();x.moveTo(0,y);x.lineTo(w,y);x.stroke()}if(!history||history.length<2)return;let vals=[];history.forEach(p=>['production_w','consumption_w','import_w','export_w'].forEach(k=>{if(p[k]!=null)vals.push(p[k])}));let max=Math.max(100,...vals)*1.12;[['production_w','#4f7cff'],['consumption_w','#ffffff'],['import_w','#22c55e'],['export_w','#ffd000']].forEach(([k,col])=>{x.strokeStyle=col;x.lineWidth=k==='production_w'?2.6:2;x.beginPath();let started=false;history.forEach((p,i)=>{if(p[k]==null){started=false;return}let px=i*w/(history.length-1),py=h-12-(p[k]/max)*(h-26);if(!started){x.moveTo(px,py);started=true}else x.lineTo(px,py)});x.stroke()})}
async function refresh(){try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error();const d=await r.json(),s=d.current||{};$('pv').innerHTML=fmt(s.production_w);$('pvSource').textContent=s.production_source||'DTU / Shelly';$('home').innerHTML=fmt(s.consumption_w);$('linky').innerHTML=fmt(s.linky_w);let exp=s.export_w||0,imp=s.import_w||0,exporting=exp>1;$('flowCard').className='card gridflow '+(exporting?'export':'import');$('flowLabel').textContent=exporting?'Injection vers le réseau':'Soutirage du réseau';$('flow').innerHTML=fmt(exporting?exp:imp);$('flowHint').textContent=exporting?'Surplus mesuré par le Shelly':'Mesure réseau locale';$('updated').textContent=s.timestamp?`Dernière mesure : ${new Date(s.timestamp).toLocaleString('fr-FR')}`:'En attente de la première mesure…';state('dtuState',s.dtu_state);state('linkyState',s.linky_state);state('shellyState',s.shelly_state);$('liveText').textContent='En direct';$('liveDot').style.background='#22c55e';draw(d.history)}catch(e){$('liveText').textContent='Hors ligne';$('liveDot').style.background='#ef4444'}}
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

    def start(self):
        dashboard = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlparse(self.path).path
                if path in ("/", "/index.html"):
                    self._send(MOBILE_HTML.encode("utf-8"), "text/html; charset=utf-8")
                    return
                if path == "/api/status":
                    with dashboard._lock:
                        body = json.dumps(dashboard._payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
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
