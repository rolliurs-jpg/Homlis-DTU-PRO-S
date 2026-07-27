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


def main() -> int:
    parser = argparse.ArgumentParser(description="Prototype DDSU DTU-Pro-S, lecture Modbus uniquement")
    parser.add_argument("--host", required=True, help="IP du DTU sur le réseau local")
    parser.add_argument("--port", type=int, default=502, help="Port Modbus TCP (défaut : 502)")
    parser.add_argument("--unit-id", type=int, default=1, help="Identifiant Modbus (défaut : 1)")
    parser.add_argument(
        "--scan", action="store_true",
        help="Balaye lentement les registres 0x0000 à 0x3FFF, en lecture seule",
    )
    args = parser.parse_args()

    client = ModbusTcpClient(args.host, port=args.port, timeout=3)
    if not client.connect():
        raise SystemExit("DTU inaccessible : vérifiez l'IP, Ethernet et Modbus TCP (port 502).")

    try:
        report = {
            "prototype": "dtu_ddsu_probe",
            "mode": "lecture_seule",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "blocks": {
                name: read_block(client, address, count, args.unit_id)
                for address, count, name in DEFAULT_BLOCKS
            },
        }
        if args.scan:
            report["scan_lecture_seule"] = sparse_scan(client, 0x0000, 0x3FFF, args.unit_id)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
