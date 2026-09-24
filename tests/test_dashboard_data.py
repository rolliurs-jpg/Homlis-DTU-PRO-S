import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from dashboard_data import DashboardData, period_bounds


class FakeBattery:
    def __init__(self):
        import threading
        self.lock = threading.Lock()
        self.rows = []

    def totals(self, _start, _end):
        return {"charge_kwh": 0.0, "discharge_kwh": 0.0,
                "battery_seconds": 0.0}


class DashboardDataTests(unittest.TestCase):
    def test_period_boundaries(self):
        now = datetime(2026, 9, 23, 12, 30)
        start, end = period_bounds("today", now)
        self.assertEqual(start, datetime(2026, 9, 23))
        self.assertEqual(end, now)
        with self.assertRaises(ValueError):
            period_bounds("invalid", now)

    def test_classic_installation_keeps_house_consumption(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            root.joinpath("hoymiles_log.csv").write_text(
                "date_heure,production_ac_w,shelly_a_w,shelly_b_w\n"
                "2026-09-23 12:00:00,800,1000,-300\n"
                "2026-09-23 12:01:00,900,1100,-400\n",
                encoding="utf-8",
            )
            config = {
                "shelly": {"enabled": True, "grid_export_positive": False},
                "linky": {"enabled": False}, "battery": {"enabled": False},
                "shelly2": {"enabled": False}, "production_complete": False,
                "tarifs_edf": {},
            }
            service = DashboardData(root, config, FakeBattery())
            report = service._report("today", datetime(2026, 9, 23, 12, 2))
            self.assertEqual(report["history"][0]["production_w"], 800)
            self.assertEqual(report["history"][0]["consumption_w"], 700)
            self.assertFalse(report["production_complete"])

    def test_partial_solar_production_is_shown_without_inventing_house_use(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            root.joinpath("hoymiles_log.csv").write_text(
                "date_heure,production_ac_w,shelly_a_w,shelly_b_w\n"
                "2026-09-23 12:00:00,800,1000,-300\n"
                "2026-09-23 12:01:00,900,1100,-400\n",
                encoding="utf-8",
            )
            battery = FakeBattery()
            battery.rows = [
                {"timestamp": datetime(2026, 9, 23, 12, 0).timestamp(),
                 "ac_charge_w": 0, "ac_discharge_w": 0},
                {"timestamp": datetime(2026, 9, 23, 12, 1).timestamp(),
                 "ac_charge_w": 0, "ac_discharge_w": 0},
            ]
            config = {
                "shelly": {"enabled": True, "grid_export_positive": False},
                "linky": {"enabled": False}, "battery": {"enabled": True},
                "shelly2": {"enabled": False}, "production_complete": False,
                "tarifs_edf": {},
            }
            report = DashboardData(root, config, battery)._report(
                "today", datetime(2026, 9, 23, 12, 2))
            self.assertEqual(report["history"][0]["production_w"], 1000)
            self.assertIsNone(report["history"][0]["consumption_w"])
            self.assertGreater(report["production_kwh"], 0)


if __name__ == "__main__":
    unittest.main()
