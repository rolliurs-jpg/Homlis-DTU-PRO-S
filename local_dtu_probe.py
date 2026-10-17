#!/usr/bin/env python3
"""Diagnostic Hoymiles local, sans écriture ni modification de réglage.

Le programme utilise seulement ``is-encrypted`` et ``get-real-data-new`` du
client hoymiles-wifi. Il ne lance jamais une commande de limite, de redémarrage,
de mise à jour, d'appairage ou de configuration Wi-Fi.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import re
from pathlib import Path
from typing import Any


READ_COMMANDS = {"is-encrypted", "get-real-data-new"}


def safe_error(text: str) -> str:
    """Garde le diagnostic utile sans afficher une éventuelle clé locale."""
    text = str(text or "").strip() or "Le client Hoymiles a refusé la lecture"
    text = re.sub(r"(?i)(enc[_-]?rand|password|passphrase|secret|token)\s*[:=]\s*\S+", r"\1=[masqué]", text)
    return re.sub(r"\b[0-9a-fA-F]{32,}\b", "[valeur masquée]", text)[:500]


def local_address_for(host: str) -> str:
    """Détermine l'interface vers le DTU sans envoyer de paquet réseau."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((host, 9))
        return str(probe.getsockname()[0])


def cli_path(requested: str | None) -> str:
    if requested:
        return requested
    nearby = Path(__file__).resolve().parent / ".venv" / "bin" / "hoymiles-wifi"
    return str(nearby) if nearby.is_file() else "hoymiles-wifi"


def run_read(cli: str, host: str, local_addr: str, command: str, enc_rand: str | None = None) -> dict[str, Any]:
    if command not in READ_COMMANDS:
        raise ValueError("Commande de diagnostic refusée")
    args = [cli, "--host", host, "--local_addr", local_addr, "--timeout", "8", "--as-json", "--disable-interactive"]
    if enc_rand:
        args.extend(["--enc-rand", enc_rand])
    args.append(command)
    result = subprocess.run(args, text=True, capture_output=True, timeout=20, check=False)
    if result.returncode != 0:
        raise RuntimeError(safe_error(result.stderr))
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Réponse Hoymiles non JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Réponse Hoymiles invalide")
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    return payload


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summary(payload: dict[str, Any], host: str, local_addr: str, encrypted: bool) -> dict[str, Any]:
    rows = payload.get("sgsData")
    if not isinstance(rows, list):
        raise RuntimeError("Réponse incomplète : sgsData absent")
    inverters = []
    total = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_power = number(row.get("activePower"))
        power = raw_power / 10 if raw_power is not None else None
        if power is not None:
            total += power
        serial = str(row.get("serialNumber", "inconnu"))
        inverters.append({"serial": serial, "power_w": None if power is None else round(power, 1)})
    return {
        "state": "online",
        "read_only": True,
        "host": host,
        "local_address": local_addr,
        "encrypted_session": encrypted,
        "inverter_count": len(inverters),
        "total_power_w": round(total, 1),
        "inverters": inverters,
        "next_step": "Lecture locale validée : aucune commande de puissance n'a été envoyée.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Teste la lecture locale d'un DTU Hoymiles sans commande")
    parser.add_argument("--host", required=True, help="adresse IP du DTU, par exemple 192.168.1.206")
    parser.add_argument("--local-addr", help="IP du Raspberry vers le DTU ; détection automatique par défaut")
    parser.add_argument("--cli", help="chemin du programme hoymiles-wifi")
    args = parser.parse_args()
    try:
        local_addr = args.local_addr or local_address_for(args.host)
        cli = cli_path(args.cli)
        encryption_note = None
        try:
            encryption = run_read(cli, args.host, local_addr, "is-encrypted")
            encrypted = bool(encryption.get("is_encrypted"))
            enc_rand = str(encryption.get("enc_rand") or "") if encrypted else None
            if encrypted and len(enc_rand) != 32:
                raise RuntimeError("Le DTU exige une session chiffrée mais n'a pas fourni de clé de lecture")
        except RuntimeError as exc:
            # Certaines versions plus anciennes du client ne disposent pas de
            # cette lecture. La lecture instantanée, toujours sans écriture,
            # reste alors le test utile.
            encrypted = False
            enc_rand = None
            encryption_note = safe_error(str(exc))
        data = run_read(cli, args.host, local_addr, "get-real-data-new", enc_rand)
        report = summary(data, args.host, local_addr, encrypted)
        if encryption_note:
            report["encryption_probe"] = "non disponible : " + encryption_note
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({
            "state": "offline", "read_only": True, "error": type(exc).__name__, "detail": str(exc),
            "next_step": "Aucune commande n'a été envoyée. Vérifier seulement le chemin réseau Raspberry → DTU.",
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
