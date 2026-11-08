#!/usr/bin/env python3
"""Importe un rapport mensuel S-Miles dans la configuration locale du Raspberry."""
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


FIELDS = {
    'Production (kWh)': 'production_kwh',
    'Vers le réseau (kWh)': 'export_kwh',
    'Depuis le réseau (kWh)': 'import_kwh',
    'Consommation (kWh)': 'consumption_kwh',
}


def number(value, label):
    try:
        result = float(str(value).replace(',', '.'))
    except ValueError as exc:
        raise SystemExit(f"Valeur invalide pour {label}.") from exc
    if result < 0:
        raise SystemExit(f"Valeur négative refusée pour {label}.")
    return result


def read_report(path):
    path = Path(path)
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or 'Heure' not in reader.fieldnames or any(name not in reader.fieldnames for name in FIELDS):
            raise SystemExit('Ce fichier ne ressemble pas à un rapport mensuel S-Miles « station_eq ».')
        months = []
        for row in reader:
            month = str(row.get('Heure') or '').strip()
            try:
                datetime.strptime(month, '%Y-%m')
            except ValueError:
                continue
            months.append(dict(month=month, **{key: number(row[name], name) for name, key in FIELDS.items()}))
    if not months:
        raise SystemExit('Aucune ligne mensuelle valide dans ce rapport.')
    return sorted({row['month']: row for row in months}.values(), key=lambda row: row['month'])


def main(args):
    if len(args) != 2:
        raise SystemExit('Utilisation : importer_rapport_hoymiles.py RAPPORT_STATION_EQ.csv')
    report = Path(args[1]).expanduser()
    if not report.is_file():
        raise SystemExit(f"Rapport introuvable : {report}")
    months = read_report(report)
    base = Path.home() / 'AppData' / 'Local' / 'BoiteNoireHoymiles'
    path = base / 'config_v5.json'
    if not path.exists():
        raise SystemExit(f"Configuration introuvable : {path}")
    backup = path.with_name('config_v5.json.avant-import-s-miles-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(path, backup)
    config = json.loads(path.read_text(encoding='utf-8'))
    config['historique_hoymiles'] = dict(source='Rapport S-Miles Cloud importé', months=months)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    print(f"{len(months)} mois S-Miles enregistrés ({months[0]['month']} à {months[-1]['month']}).")
    print(f"Sauvegarde : {backup}")


if __name__ == '__main__':
    main(sys.argv)
