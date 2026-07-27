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
import time
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


def decoded_meter(payload: Any) -> dict[str, Any]:
    """Extrait les valeurs DDSU avec les échelles vérifiées sur l'installation."""
    meters = payload.get("meterData", []) if isinstance(payload, dict) else []
    if not meters or not isinstance(meters[0], dict):
        return {"error": "Aucune donnée compteur (meterData) dans la réponse Wi-Fi."}
    meter = meters[0]
    network_power_raw = meter.get("phaseTotalPower")
    phase_power_raw = meter.get("phaseAPower")
    voltage_raw = meter.get("voltagePhaseA")
    current_raw = meter.get("currentPhaseA")
    power_factor_raw = meter.get("powerFactorTotal")

    def scaled(value: Any, factor: float) -> float | int | None:
        return value * factor if isinstance(value, (int, float)) else None

    return {
        "puissance_reseau_brute": network_power_raw,
        "puissance_reseau_w": scaled(network_power_raw, 10),
        "puissance_phase_a_brute": phase_power_raw,
        "puissance_phase_a_w": scaled(phase_power_raw, 10),
        "tension_phase_a_brute": voltage_raw,
        "tension_phase_a_v": scaled(voltage_raw, 0.01),
        "courant_phase_a_brut": current_raw,
        "courant_phase_a_a": scaled(current_raw, 0.01),
        "facteur_puissance_brut": power_factor_raw,
        "facteur_puissance": scaled(power_factor_raw, 0.001),
        "code_etat_compteur": meter.get("faultCode"),
    }


def read_wifi_data(cli: Path, host: str, local_addr: str, timeout: int) -> Any:
    """Effectue une seule lecture get-real-data-new, sans option de commande."""
    command = [
        str(cli), "--host", host, "--local_addr", local_addr,
        "--timeout", str(max(1, timeout)), "--as-json", "--disable-interactive",
        "get-real-data-new",
    ]
    result = subprocess.run(
        command, text=True, capture_output=True, timeout=max(10, timeout + 5)
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "réponse inconnue").strip()
        raise RuntimeError(detail)
    return extract_json(result.stdout)


def watch_meter(
    cli: Path,
    host: str,
    local_addr: str,
    timeout: int,
    seconds: int,
    interval: float,
    first_payload: Any,
) -> list[dict[str, Any]]:
    """Répète les lectures DDSU et conserve les erreurs transitoires du DTU."""
    samples = [{
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ddsu": decoded_meter(first_payload),
    }]
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(max(1.0, interval), remaining))
        if time.monotonic() >= deadline:
            break
        timestamp = datetime.now().isoformat(timespec="seconds")
        try:
            payload = read_wifi_data(cli, host, local_addr, timeout)
            samples.append({"timestamp": timestamp, "ddsu": decoded_meter(payload)})
        except (RuntimeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            samples.append({"timestamp": timestamp, "erreur_lecture": str(exc)})
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prototype DDSU DTU-Pro-S Wi-Fi : lecture seule uniquement"
    )
    parser.add_argument(
        "--host", default=DEFAULT_DTU_WIFI_HOST, help="Passerelle du Wi-Fi DTU"
    )
    parser.add_argument(
        "--timeout", type=int, default=15, help="Délai de réponse en secondes"
    )
    parser.add_argument(
        "--watch", type=int, default=0,
        help="Durée d'un relevé DDSU répété (par exemple : 60)",
    )
    parser.add_argument("--interval", type=float, default=15.0, help="Intervalle entre les relevés")
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

    try:
        payload = read_wifi_data(args.cli, args.host, local_addr, args.timeout)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(
            "DTU Wi-Fi inaccessible. Vérifiez que le Mac est connecté au réseau "
            f"DTUP-… puis relancez. Détail : {exc}"
        ) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Réponse Wi-Fi illisible : {exc}") from exc

    report = {
        "prototype": "dtu_wifi_ddsu_probe",
        "mode": "lecture_seule_get-real-data-new",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "dtu_wifi_host": args.host,
        "local_interface": local_addr,
        "mesure_ddsu": decoded_meter(payload),
        "champs_compteur_reseau_puissance": meter_related_fields(payload),
        "cles_principales_reponse": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }
    if args.watch:
        report["essai_variation_ddsu"] = watch_meter(
            args.cli,
            args.host,
            local_addr,
            args.timeout,
            max(1, args.watch),
            args.interval,
            payload,
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
