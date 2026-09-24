"""Fusionne un historique Windows dans l'installation Mac, avec sauvegarde."""
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


FILES = {
    "hoymiles_log.csv": "date_heure",
    "linky_index_log.csv": "date_heure",
    "shelly_injection_log.csv": "date_heure",
    "batterie_production2.csv": "timestamp",
}


def sortable(value, numeric):
    try:
        return float(value) if numeric else str(value).strip()
    except (TypeError, ValueError):
        return None


def read_rows(path, key):
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader if sortable(row.get(key), key == "timestamp") is not None]
    return fields, rows


def merge_file(mac_path, windows_path, backup_dir, key):
    win_fields, win_rows = read_rows(windows_path, key)
    if not win_rows:
        return 0, 0
    mac_fields, mac_rows = read_rows(mac_path, key)
    if mac_path.exists():
        shutil.copy2(mac_path, backup_dir / mac_path.name)
    numeric = key == "timestamp"
    cutoff = max(sortable(row[key], numeric) for row in win_rows)
    # Windows est la référence jusqu'à sa dernière mesure. Les éventuelles
    # mesures Mac plus récentes sont conservées, ce qui évite tout doublon.
    merged = {}
    for row in win_rows:
        merged[sortable(row[key], numeric)] = row
    kept_mac = 0
    for row in mac_rows:
        stamp = sortable(row.get(key), numeric)
        if stamp is not None and stamp > cutoff:
            merged[stamp] = row
            kept_mac += 1
    fields = list(win_fields)
    for field in mac_fields:
        if field not in fields:
            fields.append(field)
    ordered = [merged[stamp] for stamp in sorted(merged)]
    temporary = mac_path.with_suffix(mac_path.suffix + ".import.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered)
    temporary.replace(mac_path)
    return len(win_rows), kept_mac


def import_history(base, source):
    base, source = Path(base), Path(source)
    base.mkdir(parents=True, exist_ok=True)
    backup = base / ("sauvegarde_avant_import_windows_" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    backup.mkdir(parents=True, exist_ok=False)
    results = {}
    for name, key in FILES.items():
        results[name] = merge_file(base / name, source / name, backup, key)
    tariffs_path = source / "tarifs_windows.json"
    config_path = base / "config_v5.json"
    if tariffs_path.exists() and config_path.exists():
        shutil.copy2(config_path, backup / config_path.name)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        tariffs = json.loads(tariffs_path.read_text(encoding="utf-8"))
        # Même contrat EDF pour les deux ordinateurs ; ne reprendre que les
        # tarifs, jamais les adresses ni les réglages matériels de Windows.
        config["tarifs_edf"] = tariffs
        temporary = config_path.with_suffix(".json.import.tmp")
        temporary.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(config_path)
    return backup, results


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Utilisation : importer_historique_windows.py DOSSIER_MAC DOSSIER_WINDOWS")
    backup_path, imported = import_history(sys.argv[1], sys.argv[2])
    for filename, (windows_count, mac_count) in imported.items():
        print(f"{filename}: {windows_count} mesures Windows, {mac_count} mesures Mac récentes conservées")
    print(f"Sauvegarde Mac : {backup_path}")
