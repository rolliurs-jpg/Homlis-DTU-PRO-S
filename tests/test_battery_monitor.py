import tempfile
import unittest
from pathlib import Path
from battery_monitor import parse_zendure, household, energy_totals, BatteryMonitor, full_charge_days, battery_cycle, cycle_values


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


class FullChargeTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime
        self.t = datetime(2026, 9, 22, 14).timestamp()

    def test_first_full_clips_interval_and_does_not_reset_at_second_full(self):
        t = self.t
        battery = [dict(timestamp=t-15, soc_pct=99), dict(timestamp=t, soc_pct=100),
                   dict(timestamp=t+15, soc_pct=99), dict(timestamp=t+30, soc_pct=100)]
        grid = [dict(timestamp=t-15, injection_w=0), dict(timestamp=t+15, injection_w=1200)]
        r = full_charge_days(battery, grid, [], t+60)[0]
        self.assertEqual(r['full_at'], t)
        self.assertFalse(r['already_full'])
        self.assertAlmostEqual(r['export_kwh'], 900*15/3600000)
        self.assertEqual(r['coverage_s'], 15)
        self.assertIsNone(r['end_at'])

    def test_missing_is_not_zero_and_gaps_not_bridged(self):
        t = self.t
        battery = [dict(timestamp=t, soc_pct=100)]
        grid = [dict(timestamp=t, injection_w=1000), dict(timestamp=t+600, injection_w=1000)]
        r = full_charge_days(battery, grid, [], t+600)[0]
        self.assertTrue(r['already_full'])
        self.assertIsNone(r['export_kwh'])
        self.assertEqual(r['coverage_s'], 0)
        r = full_charge_days(battery, [dict(timestamp=t, injection_w=0),
                             dict(timestamp=t+30, injection_w=0)], [], t+30)[0]
        self.assertEqual(r['export_kwh'], 0)

    def test_end_requires_all_pv_low_for_30_minutes_and_reopens(self):
        t = self.t
        battery = [dict(timestamp=t, soc_pct=100)]
        pv = [dict(timestamp=t, pv_w=100)] + [dict(timestamp=t+i, pv_w=0) for i in range(60, 1921, 60)]
        r = full_charge_days(battery, [], pv, t+1920)[0]
        self.assertEqual(r['end_at'], t+60)
        pv.append(dict(timestamp=t+1980, pv_w=100))
        self.assertIsNone(full_charge_days(battery, [], pv, t+1980)[0]['end_at'])

    def test_never_full_and_midnight_boundary(self):
        from datetime import datetime
        t = datetime(2026, 9, 22, 23, 59, 45).timestamp()
        battery = [dict(timestamp=t, soc_pct=100), dict(timestamp=t+30, soc_pct=99)]
        grid = [dict(timestamp=t, injection_w=1000), dict(timestamp=t+30, injection_w=1000)]
        results = full_charge_days(battery, grid, [], t+60)
        self.assertIsNone(results[0]['full_at'])
        self.assertAlmostEqual(results[1]['export_kwh'], 1000*15/3600000)


class BatteryCycleTests(unittest.TestCase):
    def test_discharge_is_reported_even_when_full_was_before_monitoring(self):
        from datetime import datetime
        t = datetime(2026, 9, 23, 18).timestamp()
        rows = [dict(timestamp=t+i, soc_pct=94, charge_w=0,
                     discharge_w=300, ac_discharge_w=300)
                for i in range(0, 721, 15)]
        report = full_charge_days(rows, [], [], t+720)[0]
        self.assertIsNone(report['full_at'])
        self.assertEqual(report['discharge_at'], t)
        self.assertEqual(report['discharge_seconds'], 720)

    def test_overnight_cycle_pauses_and_first_sustained_recharge(self):
        from datetime import datetime
        t = datetime(2026,9,22,23,50).timestamp()
        rows = []
        for offset in range(0, 1501, 15):
            discharge = 500 if 120 <= offset < 600 or 720 <= offset < 1200 else 0
            charge = 600 if offset >= 1200 else 0
            rows.append(dict(timestamp=t+offset,
                             soc_pct=100-min(offset,1200)/120,
                             charge_w=charge, discharge_w=discharge,
                             ac_discharge_w=discharge))
        r = battery_cycle(rows, t, t+1500)
        self.assertEqual(r['discharge_at'], t+120)
        self.assertEqual(r['recharge_at'], t+1200)
        self.assertEqual(r['discharge_seconds'], 930)
        self.assertFalse(r['cycle_incomplete'])
        report = full_charge_days(rows, [], [], t+1500)
        yesterday = next(x for x in report if x['date']=='2026-09-22')
        self.assertIn('23/09', cycle_values(yesterday)[6])

    def test_ongoing_discharge_is_not_restarted_at_midnight(self):
        from datetime import datetime
        full = datetime(2026, 9, 23, 12, 36).timestamp()
        discharge = datetime(2026, 9, 23, 18, 2).timestamp()
        now = datetime(2026, 9, 24, 7, 50).timestamp()
        rows = [dict(timestamp=full, soc_pct=100, charge_w=0,
                     discharge_w=0, ac_discharge_w=0)]
        # Keep a continuous measurement series across midnight. The SOC drop
        # confirms the real discharge without waiting ten minutes.
        for stamp in range(int(discharge), int(now) + 1, 30):
            elapsed = stamp - discharge
            rows.append(dict(timestamp=stamp,
                             soc_pct=max(35, 99-elapsed/600),
                             charge_w=0, discharge_w=100,
                             ac_discharge_w=100))
        report = full_charge_days(rows, [], [], now)
        previous = next(x for x in report if x['date'] == '2026-09-23')
        current = next(x for x in report if x['date'] == '2026-09-24')
        self.assertTrue(previous['ongoing'])
        self.assertEqual(previous['discharge_at'], discharge)
        self.assertAlmostEqual(previous['discharge_seconds'], now-discharge)
        self.assertFalse(current['ongoing'])
        self.assertIsNone(current['discharge_at'])
        self.assertIsNone(current['discharge_seconds'])

    def test_brief_discharge_not_an_event_and_missing_not_duration(self):
        t=1000
        short=[dict(timestamp=t+i,charge_w=0,discharge_w=200 if i<60 else 0,
                    ac_discharge_w=200 if i<60 else 0) for i in range(0,181,15)]
        self.assertIsNone(battery_cycle(short,t,t+180)['discharge_at'])
        rows=[dict(timestamp=t+i,soc_pct=100-i/180,charge_w=0,discharge_w=200,
                   ac_discharge_w=200) for i in range(0,181,15)]
        rows += [dict(timestamp=t+i,soc_pct=96-i/180,charge_w=0,discharge_w=200,
                      ac_discharge_w=200) for i in range(600,781,15)]
        result=battery_cycle(rows,t,t+780)
        self.assertTrue(result['cycle_incomplete'])
        self.assertEqual(result['discharge_seconds'],360)
        self.assertTrue(result['cycle_pending'])

    def test_missing_power_does_not_confirm_event_across_gap(self):
        rows=[dict(timestamp=i,soc_pct=100-i/150,charge_w=0,
                   discharge_w=100 if i!=60 else None, ac_discharge_w=100)
              for i in range(0,151,15)]
        r=battery_cycle(rows,0,150)
        self.assertIsNone(r['discharge_at'])
        self.assertTrue(r['cycle_incomplete'])

    def test_scheduled_power_at_full_is_not_a_confirmed_discharge(self):
        rows=[dict(timestamp=i,soc_pct=99,charge_w=0,discharge_w=250)
              for i in range(0,301,15)]
        r=battery_cycle(rows,0,300)
        self.assertIsNone(r['discharge_at'])
        self.assertIsNone(r['discharge_seconds'])

    def test_real_ac_discharge_is_confirmed_after_ten_minutes_at_99(self):
        rows=[dict(timestamp=i,soc_pct=99,charge_w=0,discharge_w=80,
                   ac_discharge_w=80) for i in range(0,721,15)]
        r=battery_cycle(rows,0,720)
        self.assertEqual(r['discharge_at'],0)
        self.assertEqual(r['discharge_seconds'],720)


if __name__ == '__main__':
    unittest.main()
