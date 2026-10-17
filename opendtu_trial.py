#!/usr/bin/env python3
"""Essai OpenDTU strictement en lecture seule.

Ce programme sert à valider une OpenDTU sur le réseau local avant de la
brancher à la régulation solaire.  Il ne contient volontairement aucune
requête POST : il ne peut ni modifier une limite, ni écrire dans un
micro-onduleur, ni toucher à la configuration Hoymiles/Zendure existante.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_CONFIG = {
    "enabled": False,
    "host": "",
    "port": 80,
    "username": "",
    "password": "",
    "timeout_s": 5,
}


class OpenDtuReadOnly:
    """Client de découverte OpenDTU, sans aucune capacité de commande."""

    STATUS_PATH = "/api/livedata/status"

    def __init__(self, config: dict[str, Any]):
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    def _url(self) -> str:
        host = str(self.config["host"]).strip()
        if not host:
            raise ValueError("Adresse OpenDTU absente")
        port = int(self.config["port"])
        if not 1 <= port <= 65535:
            raise ValueError("Port OpenDTU invalide")
        return f"http://{host}:{port}{self.STATUS_PATH}"

    def _request(self) -> dict[str, Any]:
        request = Request(self._url(), headers={"Accept": "application/json"})
        username = str(self.config.get("username") or "")
        password = str(self.config.get("password") or "")
        if username or password:
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            request.add_header("Authorization", f"Basic {token}")
        timeout = float(self.config.get("timeout_s", 5))
        if not 0.5 <= timeout <= 30:
            raise ValueError("Délai OpenDTU invalide")
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Réponse OpenDTU invalide")
        return payload

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _find_power(cls, value: Any) -> float | None:
        """Lit les formes usuelles de l'API sans supposer un firmware précis."""
        if not isinstance(value, dict):
            return None
        for key in ("power", "Power", "ac_power", "acPower"):
            found = cls._number(value.get(key))
            if found is not None:
                return found
            nested = value.get(key)
            if isinstance(nested, dict):
                for nested_key in ("v", "value", "Value"):
                    found = cls._number(nested.get(nested_key))
                    if found is not None:
                        return found
        ac = value.get("AC") or value.get("ac")
        return cls._find_power(ac) if isinstance(ac, dict) else None

    @classmethod
    def _inverters(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        values = payload.get("inverters", payload.get("inverter", []))
        if isinstance(values, dict):
            values = list(values.values())
        if not isinstance(values, list):
            return []
        return [item for item in values if isinstance(item, dict)]

    def snapshot(self) -> dict[str, Any]:
        """Retourne seulement un résumé, sans exposer identifiants ou mot de passe."""
        if not self.config.get("enabled", False):
            return {"state": "disabled", "reason": "Essai OpenDTU désactivé"}
        try:
            payload = self._request()
            inverters = self._inverters(payload)
            powers = [self._find_power(item) for item in inverters]
            valid_powers = [power for power in powers if power is not None]
            return {
                "state": "online",
                "timestamp": time.time(),
                "inverter_count": len(inverters),
                "power_w": round(sum(valid_powers), 1) if valid_powers else None,
                "power_readings": len(valid_powers),
                "api": self.STATUS_PATH,
                "read_only": True,
            }
        except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            return {"state": "offline", "reason": type(exc).__name__, "read_only": True}


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Le fichier de configuration doit contenir un objet JSON")
    return {**DEFAULT_CONFIG, **data}


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie OpenDTU sans envoyer de commande")
    parser.add_argument("config", type=Path, help="fichier JSON d'essai OpenDTU")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Configuration non lue : {exc}", file=sys.stderr)
        return 2
    result = OpenDtuReadOnly(config).snapshot()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] in ("online", "disabled") else 1


if __name__ == "__main__":
    raise SystemExit(main())
