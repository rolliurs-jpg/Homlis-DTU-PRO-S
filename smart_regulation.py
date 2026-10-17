"""Décision de régulation photovoltaïque, sans accès matériel.

Ce module est volontairement séparé des commandes Hoymiles.  Il transforme
des mesures déjà lues localement en une consigne commune en pourcentage.  Une
autre couche devra explicitement choisir de l'appliquer : les tests et le
mode observation ne peuvent donc jamais brider un onduleur.
"""

from dataclasses import dataclass
import math


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


@dataclass(frozen=True)
class RegulationDecision:
    limit_pct: int
    battery_full_confirmed: bool
    reason: str


class SmartRegulation:
    """Politique prudente pour une installation avec batterie AC.

    ``grid_w`` est positif quand la maison importe et négatif quand elle
    injecte.  La baisse est autorisée seulement après trois minutes avec une
    batterie à 99 % ou plus qui ne prend pratiquement plus de puissance.
    """

    def __init__(self, rated_w, export_buffer_w=30, confirm_seconds=180):
        if not _number(rated_w) or rated_w <= 0:
            raise ValueError("Puissance nominale invalide")
        self.rated_w = float(rated_w)
        self.export_buffer_w = float(export_buffer_w)
        self.confirm_seconds = float(confirm_seconds)
        self._full_since = None
        self._full = False
        self._last_timestamp = None

    def reset(self):
        self._full_since = None
        self._full = False
        self._last_timestamp = None

    def decide(self, sample, now):
        """Retourne une consigne sans jamais communiquer avec un appareil."""
        try:
            grid_w = sample["grid_w"]
            production_w = sample["production_w"]
            battery = sample["battery"]
            stamp = sample["timestamp"]
            soc = battery["soc_pct"]
            ac_charge = battery["ac_charge_w"]
            ac_discharge = battery["ac_discharge_w"]
            pack_charge = battery["charge_w"]
            values = (grid_w, production_w, stamp, soc, ac_charge, ac_discharge, pack_charge, now)
            if not all(_number(value) for value in values):
                raise ValueError
            if not (0 <= now - stamp <= 45 and 0 <= soc <= 100 and production_w >= 0):
                raise ValueError
            if min(ac_charge, ac_discharge, pack_charge) < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            self.reset()
            return RegulationDecision(100, False, "Mesure absente ou ancienne : production maximale demandée.")

        if self._last_timestamp is not None and not 0 < stamp - self._last_timestamp <= 45:
            self._full_since = None
            self._full = False
        self._last_timestamp = stamp

        # A 99 %, le BMS peut déjà refuser la charge.  On demande donc une
        # confirmation durable de puissance de charge très faible plutôt que
        # d'attendre un hypothétique 100 % affiché.
        resting_full = soc >= 99 and ac_charge <= 100 and pack_charge <= 100 and ac_discharge <= 20
        if not resting_full:
            self._full_since = None
            self._full = False
            return RegulationDecision(100, False, "Priorité à la recharge de la batterie.")

        if not self._full:
            if self._full_since is None:
                self._full_since = stamp
            if stamp - self._full_since < self.confirm_seconds:
                remaining = max(0, round(self.confirm_seconds - (stamp - self._full_since)))
                return RegulationDecision(100, False, f"Batterie presque pleine : confirmation dans {remaining} s.")
            self._full = True

        # Une petite injection évite les oscillations import/export.  La
        # consigne ne prédit pas le soleil : elle ajuste le plafond à partir de
        # la production instantanée effectivement mesurée.
        desired_w = production_w + grid_w + self.export_buffer_w
        limit = round(max(2, min(100, desired_w / self.rated_w * 100)))
        return RegulationDecision(limit, True, "Batterie pleine confirmée : limitation progressive du surplus.")
