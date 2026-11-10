"""Enregistre les tarifs EDF dans la configuration locale du collecteur.

Usage : python3 configurer_tarifs_edf.py HP HC ABONNEMENT_MOIS ABONNEMENT_JOUR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def amount(value: str, label: str) -> float:
    try:
        result = float(value.replace(',', '.'))
    except (AttributeError, ValueError) as exc:
        raise SystemExit(f"{label} doit être un nombre.") from exc
    if not 0 <= result <= 100:
        raise SystemExit(f"{label} est hors limite.")
    return result


def main(arguments: list[str]) -> None:
    if len(arguments) != 4:
        raise SystemExit(__doc__.strip())
    hp = amount(arguments[0], "Tarif HP")
    hc = amount(arguments[1], "Tarif HC")
    monthly = amount(arguments[2], "Abonnement mensuel")
    daily = amount(arguments[3], "Abonnement journalier")
    path = Path.home() / "AppData" / "Local" / "BoiteNoireHoymiles" / "config_v5.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Configuration introuvable : {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit("Configuration illisible : aucune modification effectuée.") from exc
    tariffs = config.setdefault("tarifs_edf", {})
    tariffs.update(
        hp_eur_kwh=hp,
        hc_eur_kwh=hc,
        abonnement_mensuel_eur=monthly,
        abonnement_journalier_eur=daily,
    )
    temporary = path.with_suffix(".json.new")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(f"Tarifs enregistrés : HP {hp:.4f} €/kWh · HC {hc:.4f} €/kWh · abonnement {monthly:.2f} €/mois.")


if __name__ == "__main__":
    main(sys.argv[1:])
