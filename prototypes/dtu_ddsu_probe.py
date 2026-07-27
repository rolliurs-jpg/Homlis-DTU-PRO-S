#!/usr/bin/env python3
"""Prototype de recherche DDSU pour DTU-Pro-S en Ethernet.

Ce programme ne fait que des lectures Modbus (fonctions 0x03 et 0x04).
Il n'écrit jamais dans le DTU et ne modifie ni sa limite de puissance ni ses
réglages réseau. Il ne fait pas partie de l'application publiée.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen

from pymodbus.client import ModbusTcpClient


# Blocs de lecture non sensibles : informations générales, mesures connues des
# micro-onduleurs, numéro DTU et réglage réseau. Les adresses de commande ne
# sont volontairement jamais interrogées par le balayage automatique.
DEFAULT_BLOCKS = (
    (0x0000, 16, "dtu_general"),
    (0x0100, 16, "dtu_extended"),
    (0x1000, 20, "micro_onduleur_port_1"),
    (0x1028, 20, "micro_onduleur_port_2"),
    (0x2000, 6, "identification_dtu"),
    (0x2500, 5, "configuration_ethernet"),
    (0x3000, 16, "zone_non_documentee"),
)


def registers_as_values(registers: list[int]) -> list[dict[str, int]]:
    """Expose chaque registre en non-signé et signé, pour l'analyse locale."""
    return [
        {"u16": value, "i16": value if value < 0x8000 else value - 0x10000}
        for value in registers
    ]


def read_block(client: ModbusTcpClient, address: int, count: int, unit_id: int) -> dict:
    """Lit les registres holding et input sans aucune écriture."""
    result = {"address_hex": f"0x{address:04X}", "count": count}
    for kind, reader in (
        ("holding", client.read_holding_registers),
        ("input", client.read_input_registers),
    ):
        try:
            response = reader(address, count=count, device_id=unit_id)
            if response.isError():
                result[kind] = {"error": str(response)}
            else:
                result[kind] = registers_as_values(response.registers)
        except Exception as exc:
            result[kind] = {"error": str(exc)}
    return result


def sparse_scan(client: ModbusTcpClient, start: int, end: int, unit_id: int) -> list[dict]:
    """Balayage lent, en lecture seule, réservé aux essais explicites."""
    findings = []
    for address in range(start, end + 1, 16):
        block = read_block(client, address, 16, unit_id)
        # Conserve uniquement les plages qui répondent réellement.
        if "error" not in block.get("holding", {}) or "error" not in block.get("input", {}):
            findings.append(block)
        time.sleep(0.15)
    return findings


def compact_ranges(blocks: list[dict], key: str) -> list[str]:
    """Regroupe les adresses qui répondent pour une sortie courte et partageable."""
    addresses = [int(block["address_hex"], 16) for block in blocks if "error" not in block.get(key, {})]
    if not addresses:
        return []
    ranges, start, previous = [], addresses[0], addresses[0]
    for address in addresses[1:]:
        if address != previous + 16:
            ranges.append(f"0x{start:04X}-0x{previous:04X}")
            start = address
        previous = address
    ranges.append(f"0x{start:04X}-0x{previous:04X}")
    return ranges


def read_dinky_power(host: str) -> float | None:
    """Lit la puissance Téléinfo du Dinky, uniquement pour comparer les variations."""
    url = f"http://{host}/cm?{urlencode({'cmnd': 'Status 8'})}"
    try:
        with urlopen(url, timeout=3) as response:  # nosec B310 - hôte local saisi par l'utilisateur
            payload = json.load(response)
        sns = payload.get("StatusSNS", {})
        energy = sns.get("ENERGY", {}) if isinstance(sns, dict) else {}
        value = energy.get("Power", sns.get("Power"))
        return float(value) if value is not None else None
    except Exception:
        return None


def watch_unknown_zone(
    client: ModbusTcpClient, seconds: int, interval: float, unit_id: int, dinky_host: str | None
) -> list[dict]:
    """Échantillonne les zones qui répondent, sans modifier le DTU."""
    samples = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        pv = read_block(client, 0x1000, 20, unit_id)
        unknown = read_block(client, 0x3000, 16, unit_id)
        samples.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "dinky_w": read_dinky_power(dinky_host) if dinky_host else None,
                "pv_port_1_holding": [item["u16"] for item in pv.get("holding", [])],
                "zone_3000_holding": [item["u16"] for item in unknown.get("holding", [])],
                "zone_3000_input": [item["u16"] for item in unknown.get("input", [])],
            }
        )
        time.sleep(interval)
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Prototype DDSU DTU-Pro-S, lecture Modbus uniquement")
    parser.add_argument("--host", required=True, help="IP du DTU sur le réseau local")
    parser.add_argument("--port", type=int, default=502, help="Port Modbus TCP (défaut : 502)")
    parser.add_argument("--unit-id", type=int, default=1, help="Identifiant Modbus (défaut : 1)")
    parser.add_argument(
        "--scan", action="store_true",
        help="Balaye lentement les registres 0x0000 à 0x3FFF, en lecture seule",
    )
    parser.add_argument("--scan-start", type=lambda value: int(value, 0), default=0x0000)
    parser.add_argument("--scan-end", type=lambda value: int(value, 0), default=0x3FFF)
    parser.add_argument("--scan-summary", action="store_true", help="N'affiche que les plages qui répondent")
    parser.add_argument(
        "--inspect", type=lambda value: int(value, 0), action="append",
        help="Affiche un bloc précis de 16 registres (exemple : --inspect 0x4000)",
    )
    parser.add_argument(
        "--watch", type=int, default=0,
        help="Durée en secondes d'un essai comparatif (par exemple : 60)",
    )
    parser.add_argument("--interval", type=float, default=3.0, help="Intervalle des relevés en secondes")
    parser.add_argument("--dinky-host", help="IP optionnelle du Dinky, pour comparer la puissance Téléinfo")
    args = parser.parse_args()

    client = ModbusTcpClient(args.host, port=args.port, timeout=3)
    if not client.connect():
        raise SystemExit("DTU inaccessible : vérifiez l'IP, Ethernet et Modbus TCP (port 502).")

    try:
        report = {
            "prototype": "dtu_ddsu_probe",
            "mode": "lecture_seule",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        if not args.scan_summary and not args.inspect:
            report["blocks"] = {
                name: read_block(client, address, count, args.unit_id)
                for address, count, name in DEFAULT_BLOCKS
            }
        if args.inspect:
            report["inspection"] = {
                f"0x{address:04X}": read_block(client, address, 16, args.unit_id)
                for address in args.inspect
            }
        if args.scan:
            start = max(0, min(args.scan_start, args.scan_end))
            end = min(0xBFFF, max(args.scan_start, args.scan_end))
            scan = sparse_scan(client, start, end, args.unit_id)
            if args.scan_summary:
                report["scan_lecture_seule"] = {
                    "holding_registers": compact_ranges(scan, "holding"),
                    "input_registers": compact_ranges(scan, "input"),
                }
            else:
                report["scan_lecture_seule"] = scan
        if args.watch:
            report["essai_comparatif"] = watch_unknown_zone(
                client, max(1, args.watch), max(1.0, args.interval), args.unit_id, args.dinky_host
            )
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
