import tempfile
import unittest
from pathlib import Path
from battery_monitor import parse_zendure, household, energy_totals, BatteryMonitor


class BatteryTests(unittest.TestCase):
    def test_windows_installer_has_no_utf8_bom(self):
        root = Path(__file__).resolve().parents[1]
        data = (root / 'INSTALLER_WINDOWS.vbs').read_bytes()
        self.assertTrue(data.startswith(b'Option Explicit'))
        self.assertTrue(data.isascii())
        self.assertIn(b'battery_monitor.py', data)

    def payload(self):
        return {'product': 'solarFlow2400AC', 'properties': {
            'ts': 1000, 'dataReady': 1, 'electricLevel': 73, 'outputPackPower': 816,
            'packInputPower': 0, 'gridInputPower': 816, 'outputHomePower': 0, 'packNum': 2}}

    def test_observed_charge_fields_not_reversed(self):
        row = parse_zendure(self.payload(), 1001)
        self.assertEqual(row['charge_w'], 816)
        self.assertEqual(row['discharge_w'], 0)

    def test_stale_missing_wrong_device(self):
        with self.assertRaises(ValueError):
            parse_zendure(self.payload(), 1300)
        data = self.payload()
        del data['properties']['gridInputPower']
        with self.assertRaises(ValueError):
            parse_zendure(data, 1000)
        data = self.payload(); data['product'] = 'smartMeter'
        with self.assertRaises(ValueError):
            parse_zendure(data, 1000)

    def test_home_excludes_battery_charge_and_includes_discharge(self):
        self.assertEqual(household(1600, 800, -114, {'ac_charge_w': 900, 'ac_discharge_w': 0}, True), 1386)
        self.assertEqual(household(0, 0, 50, {'ac_charge_w': 0, 'ac_discharge_w': 500}, True), 550)
        self.assertIsNone(household(1600, None, -1712, {'ac_charge_w': 0, 'ac_discharge_w': 0}, False))
        self.assertIsNone(household(1600, 800, 50, None, True))

    def test_energy_gaps_and_missing_are_not_zero_or_extrapolated(self):
        def row(ts):
            return dict(timestamp=ts, soc_pct=70, charge_w=1000, discharge_w=0, ac_charge_w=1100, ac_discharge_w=0, pv2_w=500)
        result = energy_totals([row(0), row(30), row(600), row(630)], 0, 1000)
        self.assertAlmostEqual(result['charge_kwh'], 1/60)
        self.assertEqual(result['battery_seconds'], 60)
        bad = row(45); bad['charge_w'] = None
        self.assertEqual(energy_totals([row(30), bad], 0, 100)['battery_seconds'], 0)

    def test_restart_history_and_never_use_future_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'batterie_production2.csv').write_text('timestamp,soc_pct\n100,73\n', encoding='utf-8')
            monitor = BatteryMonitor(tmp, {})
            self.assertEqual(monitor.at(110)['soc_pct'], 73)
            self.assertEqual(monitor.at(99), {})
            self.assertEqual(monitor.at(146), {})


if __name__ == '__main__':
    unittest.main()
