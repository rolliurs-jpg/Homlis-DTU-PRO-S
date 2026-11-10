#!/usr/bin/env python3
"""Enregistre un relevé EDF déclaré, séparé des index locaux du Raspberry."""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def amount(value, label):
    try:
        result = float(str(value).replace(',', '.'))
    except ValueError as exc:
        raise SystemExit(f"{label} doit être un nombre.") from exc
    if result < 0:
        raise SystemExit(f"{label} ne peut pas être négatif.")
    return result


def main(args):
    if len(args) != 5:
        raise SystemExit("Utilisation : configurer_historique_edf.py DATE_DEBUT DATE_RELEVE HC_KWH HP_KWH")
    start_date, as_of_date, hc, hp = args[1:]
    for value, label in ((start_date, 'DATE_DEBUT'), (as_of_date, 'DATE_RELEVE')):
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError as exc:
            raise SystemExit(f"{label} doit être au format AAAA-MM-JJ.") from exc
    base = Path.home() / 'AppData' / 'Local' / 'BoiteNoireHoymiles'
    path = base / 'config_v5.json'
    if not path.exists():
        raise SystemExit(f"Configuration introuvable : {path}")
    backup = path.with_name('config_v5.json.avant-historique-edf-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(path, backup)
    config = json.loads(path.read_text(encoding='utf-8'))
    config['historique_edf'] = dict(start_date=start_date, as_of_date=as_of_date,
                                    hc_kwh=amount(hc, 'HC_KWH'), hp_kwh=amount(hp, 'HP_KWH'))
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    print(f"Historique EDF enregistré. Sauvegarde : {backup}")


if __name__ == '__main__':
    main(sys.argv)
