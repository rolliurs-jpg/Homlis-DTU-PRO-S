"""Surveille passivement la production des quatre panneaux pilotés par le DTU.

Cette sonde ne contacte aucun appareil et ne commande rien. Elle réutilise les
mesures déjà obtenues du DTU et la production du cabanon lue par le proxy ESP32.
"""

from __future__ import annotations

import math
import time


class DtuGenerationWatchdog:
    """Détecte une absence durable de production maison, sans agir sur le DTU."""

    EXPECTED_PANELS = 4
    DAYLIGHT_PROXY_MIN_W = 50.0
    PANEL_VOLTAGE_MIN_V = 20.0
    LOW_OUTPUT_MAX_W = 10.0
    ALERT_AFTER_S = 15 * 60
    MAX_SAMPLE_AGE_S = 12 * 60

    def __init__(self) -> None:
        self._low_since = None
        self._state = "checking"
        self._message = "Surveillance DTU en attente d'une mesure détaillée."

    @staticmethod
    def _finite(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    def observe(self, panels_state: dict | None, cabanon_power_w=None, now=None) -> dict:
        """Analyse les données déjà en mémoire, sans requête ni écriture."""
        now = time.time() if now is None else float(now)
        panels_state = panels_state or {}
        cabanon_power = self._finite(cabanon_power_w)
        sample_time = self._finite(panels_state.get("timestamp"))
        panels = panels_state.get("panels") or []

        if panels_state.get("state") != "online" or len(panels) != self.EXPECTED_PANELS:
            self._low_since = None
            self._state = "unknown"
            self._message = "Surveillance DTU indisponible : mesures détaillées des quatre panneaux absentes."
            return self.snapshot(now)
        if sample_time is None or now - sample_time > self.MAX_SAMPLE_AGE_S:
            self._low_since = None
            self._state = "unknown"
            self._message = "Surveillance DTU en attente d'une mesure récente des quatre panneaux."
            return self.snapshot(now)

        total_w = sum(self._finite(panel.get("power_w")) or 0.0 for panel in panels)
        voltages = [self._finite(panel.get("voltage_v")) or 0.0 for panel in panels]
        dc_present = all(voltage >= self.PANEL_VOLTAGE_MIN_V for voltage in voltages)
        daylight = cabanon_power is not None and cabanon_power >= self.DAYLIGHT_PROXY_MIN_W
        low_output = total_w <= self.LOW_OUTPUT_MAX_W

        if daylight and dc_present and low_output:
            if self._low_since is None:
                self._low_since = now
            elapsed = now - self._low_since
            if elapsed >= self.ALERT_AFTER_S:
                self._state = "alert"
                self._message = (
                    "ALERTE DTU : les 4 panneaux maison restent à "
                    f"{total_w:.0f} W depuis {int(elapsed // 60)} min, alors que le cabanon produit "
                    f"{cabanon_power:.0f} W. Le DTU peut les brider ou le micro-onduleur peut être arrêté ; "
                    "vérifiez l'état S-Miles."
                )
            else:
                self._state = "checking"
                self._message = (
                    "Surveillance DTU : faible production des quatre panneaux maison malgré la production du cabanon ; "
                    "validation en cours."
                )
        else:
            self._low_since = None
            self._state = "online"
            self._message = "DTU : production maison cohérente avec les mesures disponibles."
        return self.snapshot(now)

    def snapshot(self, now=None) -> dict:
        now = time.time() if now is None else float(now)
        low_age = None if self._low_since is None else max(0, int(now - self._low_since))
        return {"state": self._state, "message": self._message,
                "low_output_age_s": low_age, "alert_after_s": self.ALERT_AFTER_S}
