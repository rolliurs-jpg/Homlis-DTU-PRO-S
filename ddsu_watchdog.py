"""Surveille la fraîcheur réelle des données DDSU publiées par un DTU.

Le DTU-Pro-S ne documente pas de façon stable le registre interne d'état du
compteur : une même valeur peut signifier des choses différentes selon le
micrologiciel. Cette sonde ne s'appuie donc pas sur ce code. Elle vérifie que
les registres de mesure changent encore, alors qu'une pince réseau locale
constate un flux significatif.
"""

from __future__ import annotations

import math
import time


class DdsuWatchdog:
    """Détecte une mesure DDSU figée sans envoyer de requête supplémentaire."""

    STALE_AFTER_S = 20 * 60
    REFERENCE_GRID_MIN_W = 80.0

    def __init__(self) -> None:
        self._signature = None
        self._first_seen_at = None
        self._last_change_at = None
        self._last_seen_at = None
        self._state = "checking"
        self._message = "Vérification DDSU en attente de la première mesure."

    @staticmethod
    def _finite(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    def observe(self, meter: dict | None, reference_grid_w=None, now=None) -> dict:
        """Ajoute le relevé Modbus déjà lu pendant le cycle courant.

        ``reference_grid_w`` vient du Shelly Pro EM, indépendant du DDSU. Il
        permet de ne conclure à une absence que lorsqu'il y a effectivement un
        flux réseau à mesurer.
        """
        now = time.monotonic() if now is None else float(now)
        reference = self._finite(reference_grid_w)
        meter = meter or {}
        raw = meter.get("meter_registers")

        if meter.get("error"):
            self._state = "unknown"
            self._message = "Vérification DDSU indisponible : lecture DTU impossible."
            return self.snapshot(now)
        if not raw:
            self._state = "offline"
            self._message = "ALERTE DDSU : aucun compteur n'est renvoyé par le DTU. Limitation d'injection à vérifier."
            return self.snapshot(now)

        # Les trois premiers registres sont le numéro de série et le dernier
        # est un indicateur non documenté : aucun des deux ne prouve que la
        # mesure réseau est fraîche. On suit uniquement les données utiles.
        signature = tuple(int(value) & 0xFFFF for value in raw[3:47])
        if not any(value not in (0, 0xFFFF) for value in signature):
            self._state = "offline"
            self._message = "ALERTE DDSU : le DTU ne publie aucune donnée de mesure. Limitation d'injection à vérifier."
            return self.snapshot(now)

        self._last_seen_at = now
        if self._signature is None:
            self._signature = signature
            self._first_seen_at = now
            self._last_change_at = now
            self._state = "checking"
            self._message = "DDSU détecté : validation de mesures fraîches en cours."
            return self.snapshot(now)

        if signature != self._signature:
            self._signature = signature
            self._last_change_at = now
            self._state = "online"
            self._message = "DDSU : mesures réseau fraîches confirmées."
            return self.snapshot(now)

        unchanged_for = now - (self._last_change_at if self._last_change_at is not None else now)
        if reference is not None and abs(reference) >= self.REFERENCE_GRID_MIN_W and unchanged_for >= self.STALE_AFTER_S:
            self._state = "offline"
            self._message = (
                "ALERTE DDSU : mesures figées depuis "
                f"{int(unchanged_for // 60)} min alors que le Shelly mesure "
                f"{abs(reference):.0f} W sur le réseau. Limitation d'injection à vérifier."
            )
        elif self._state != "online":
            self._state = "checking"
            self._message = "DDSU détecté : validation des mesures réseau en cours."
        return self.snapshot(now)

    def snapshot(self, now=None) -> dict:
        now = time.monotonic() if now is None else float(now)
        changed_age = None if self._last_change_at is None else max(0, int(now - self._last_change_at))
        return {
            "state": self._state,
            "message": self._message,
            "last_change_age_s": changed_age,
            "stale_after_s": self.STALE_AFTER_S,
        }
