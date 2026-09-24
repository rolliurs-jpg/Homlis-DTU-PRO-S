import unittest
from mobile_dashboard import MobileDashboard

class MobileBatteryTests(unittest.TestCase):
    def test_cached_report_retains_missing_and_zero_and_local_times(self):
        calls = []
        server = MobileDashboard()
        def report():
            calls.append(1)
            return [dict(date='2026-09-22', full_at=None, end_at=None, export_kwh=None),
                    dict(date='2026-09-21', full_at=1789987125, end_at=None, export_kwh=0)]
        server.battery_report = report
        first = server.get_battery_report()
        self.assertIsNone(first['days'][0]['full_time'])
        self.assertIsNone(first['days'][0]['export_kwh'])
        self.assertEqual(first['days'][1]['export_kwh'], 0)
        self.assertRegex(first['days'][1]['full_time'], r'^\d{2}:\d{2}:\d{2}$')
        first['days'].clear()
        self.assertEqual(len(server.get_battery_report()['days']), 2)
        self.assertEqual(len(calls), 1)

    def test_no_provider_and_failure_do_not_become_fake_values(self):
        server = MobileDashboard()
        self.assertEqual(server.get_battery_report()['days'], [])
        server._battery_cache = None
        def fail():
            raise OSError('unreadable')
        server.battery_report = fail
        with self.assertRaises(OSError):
            server.get_battery_report()
