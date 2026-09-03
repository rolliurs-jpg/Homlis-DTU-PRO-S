import unittest
from datetime import datetime, timedelta

from energy_analysis import analyse_period, simulate_batteries


class EnergyAnalysisTests(unittest.TestCase):
    def test_energy_and_sources(self):
        start = datetime(2026, 9, 1)
        times = [start + timedelta(minutes=index) for index in range(61)]
        dtu = [1000.0] * 61
        dtu[20:25] = [float("nan")] * 5
        shelly_pv = [1000.0] * 61
        shelly_grid = [-500.0] * 30 + [500.0] * 31
        result = analyse_period(times, dtu, shelly_pv, shelly_grid, start, times[-1])
        self.assertAlmostEqual(result["production_kwh"], 1.0, places=3)
        self.assertAlmostEqual(result["export_kwh"], 0.25, places=3)
        self.assertAlmostEqual(result["import_kwh"], 0.25, places=3)
        self.assertEqual(result["dtu_outages"], 1)
        self.assertGreater(result["backup_pct"], 0)

    def test_battery_never_creates_energy(self):
        start = datetime(2026, 9, 1)
        times = [start + timedelta(minutes=index) for index in range(121)]
        dtu = shelly_pv = [1000.0] * 121
        shelly_grid = [-500.0] * 60 + [500.0] * 61
        result = analyse_period(times, dtu, shelly_pv, shelly_grid, start, times[-1])
        battery = simulate_batteries(result, capacities=(2.0,))[0]
        self.assertLessEqual(battery["avoided_import_kwh"], result["import_kwh"])
        self.assertLessEqual(battery["captured_kwh"], result["export_kwh"])

    def test_long_gap_reduces_quality_coverage(self):
        start = datetime(2026, 9, 1)
        times = [start, start + timedelta(minutes=1), start + timedelta(minutes=11)]
        values = [500.0, 500.0, 500.0]
        result = analyse_period(times, values, values, [0.0] * 3, start, times[-1])
        self.assertGreater(result["missing_seconds"], 0)
        self.assertLess(result["coverage_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
