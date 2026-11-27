/* Produit une démo autonome depuis l'interface réelle, sans accès réseau. */
const fs=require('fs');
const dashboard=fs.readFileSync('dashboard_ui.html','utf8');
const simulation=fs.readFileSync('scripts/demo-simulation.js','utf8');
const banner='<div style="position:sticky;top:0;z-index:1000;background:#ffd27a;color:#152236;text-align:center;padding:8px;font-weight:700">MODE DÉMONSTRATION · données fictives · aucune commande réelle</div>';
const csp='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; img-src data:; connect-src \'none\'; form-action \'none\'; base-uri \'none\'">';
let output=dashboard.replace('<head>','<head>'+csp).replace('<body>','<body>'+banner).replace('<script>','<script>'+simulation+'\n</script><script>');
output=output.replace(/<link rel="(?:manifest|icon|apple-touch-icon)"[^>]*>/g,'');
fs.writeFileSync('docs/demo.html',output);
