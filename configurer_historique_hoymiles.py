#!/usr/bin/env python3
"""Enregistre des totaux mensuels S-Miles sans publier les données privées."""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def number(value, label):
    try:
        result = float(value.replace(',', '.'))
    except ValueError as exc:
        raise SystemExit(f"Valeur invalide : {label}") from exc
    if result < 0:
        raise SystemExit(f"Valeur négative refusée : {label}")
    return result


def main(args):
    if len(args) != 2:
        raise SystemExit('Utilisation : configurer_historique_hoymiles.py "mois|production|injection|achat|conso;…"')
    months = []
    for record in args[1].split(';'):
        parts = record.split('|')
        if len(parts) != 5:
            raise SystemExit('Format mensuel invalide.')
        month = parts[0]
        try:
            datetime.strptime(month, '%Y-%m')
        except ValueError as exc:
            raise SystemExit(f"Mois invalide : {month}") from exc
        months.append(dict(month=month, production_kwh=number(parts[1], month),
                           export_kwh=number(parts[2], month), import_kwh=number(parts[3], month),
                           consumption_kwh=number(parts[4], month)))
    if not months:
        raise SystemExit('Aucun mois fourni.')
    months.sort(key=lambda row: row['month'])
    base = Path.home() / 'AppData' / 'Local' / 'BoiteNoireHoymiles'
    path = base / 'config_v5.json'
    if not path.exists():
        raise SystemExit(f"Configuration introuvable : {path}")
    backup = path.with_name('config_v5.json.avant-historique-s-miles-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(path, backup)
    config = json.loads(path.read_text(encoding='utf-8'))
    config['historique_hoymiles'] = dict(source='Rapport S-Miles Cloud importé le 08/11/2026', months=months)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    print(f"Historique Hoymiles enregistré : {len(months)} mois. Sauvegarde : {backup}")


if __name__ == '__main__':
    main(sys.argv)
