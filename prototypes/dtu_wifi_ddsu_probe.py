#!/usr/bin/env python3
"""Sonde DDSU du DTU-Pro-S par Wi-Fi direct, strictement en lecture seule.

Le programme appelle exclusivement ``get-real-data-new`` du paquet
``hoymiles-wifi``. Il ne demande aucune commande de réglage au DTU et ne fait
pas partie de l'application publiée. Son but est de vérifier si le service
Wi-Fi direct expose des champs de compteur absents du Modbus Ethernet.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_DTU_WIFI_HOST = "10.10.100.254"
DEFAULT_CLI = (
    Path.home()
    / "Library"
    / "Application Support"
    / "BoiteNoireHoymiles"
    / "venv"
    / "bin"
    / "hoymiles-wifi"
)


def local_address_for(host: str) -> str:
    """Retourne l'adresse locale choisie par macOS pour atteindre le DTU."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((host, 10081))
        return str(probe.getsockname()[0])


def extract_json(text: str) -> Any:
    """Extrait le JSON même si l'outil affiche une ligne d'information avant."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("La réponse Wi-Fi ne contient pas de JSON exploitable.")
    return json.loads(text[start : end + 1])


def meter_related_fields(value: Any, path: str = "") -> dict[str, Any]:
    """Garde les champs qui évoquent compteur, réseau ou puissance."""
    found: dict[str, Any] = {}
    keywords = ("meter", "dssu", "grid", "phase", "power", "energy", "sgs")
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}" if path else key
            if any(word in key.lower() for word in keywords):
                found[item_path] = item
            found.update(meter_related_fields(item, item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.update(meter_related_fields(item, f"{path}[{index}]"))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prototype DDSU DTU-Pro-S Wi-Fi : lecture seule uniquement"
    )
    parser.add_argument(
        "--host", default=DEFAULT_DTU_WIFI_HOST, help="Passerelle du Wi-Fi DTU"
    )
    parser.add_argument(
        "--timeout", type=int, default=8, help="Délai de réponse en secondes"
    )
    parser.add_argument("--cli", type=Path, default=DEFAULT_CLI, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not args.cli.is_file():
        raise SystemExit(
            "Le module Wi-Fi de la Boîte noire Hoymiles est introuvable. "
            "Installez d'abord le logiciel."
        )

    try:
        local_addr = local_address_for(args.host)
    except OSError as exc:
        raise SystemExit(f"Impossible de déterminer l'interface Wi-Fi du DTU : {exc}") from exc

    command = [
        str(args.cli), "--host", args.host, "--local_addr", local_addr,
        "--timeout", str(max(1, args.timeout)), "--as-json", "--disable-interactive",
        "get-real-data-new",
    ]
    result = subprocess.run(command, text=True, capture_output=True, timeout=max(10, args.timeout + 5))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "réponse inconnue").strip()
        raise SystemExit(
            "DTU Wi-Fi inaccessible. Vérifiez que le Mac est connecté au réseau "
            f"DTUP-… puis relancez. Détail : {detail}"
        )

    try:
        payload = extract_json(result.stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Réponse Wi-Fi illisible : {exc}") from exc

    report = {
        "prototype": "dtu_wifi_ddsu_probe",
        "mode": "lecture_seule_get-real-data-new",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "dtu_wifi_host": args.host,
        "local_interface": local_addr,
        "champs_compteur_reseau_puissance": meter_related_fields(payload),
        "cles_principales_reponse": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        print("Le DTU Wi-Fi ne répond pas dans le délai imparti.", file=sys.stderr)
        raise SystemExit(1)
