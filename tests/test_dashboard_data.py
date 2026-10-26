import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

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
    def test_wireless_interfaces_describe_required_usb_ports(self):
        completed = type('Completed', (), {
            'returncode': 0,
            'stdout': 'wlan1:connected\nwlan2:connected\n',
        })()
        with patch('dashboard_data.subprocess.run', return_value=completed):
            links = DashboardData.wireless_interfaces()
        self.assertEqual([link['interface'] for link in links], ['wlan1', 'wlan2'])
        self.assertTrue(all(link['connected'] for link in links))
        self.assertIn('USB 2.0 obligatoire', links[0]['role'])
        self.assertIn('USB 3.0 obligatoire', links[1]['role'])
        self.assertIn('192.168.1.205', links[0]['references'][0])
        self.assertIn('aucune adresse Livebox propre', links[1]['references'][0])

    def test_wireless_interfaces_accepts_uppercase_driver_name(self):
        completed = type('Completed', (), {
            'returncode': 0,
            'stdout': 'WLAN2:connected\n',
        })()
        with patch('dashboard_data.subprocess.run', return_value=completed):
            links = DashboardData.wireless_interfaces()
        alfa = next(link for link in links if link['interface'] == 'wlan2')
        self.assertTrue(alfa['connected'])

    def test_router_is_probed_by_ping_not_port_80(self):
        config = {
            "hoymiles_proxy": {"enabled": False},
            "tp_link": {"enabled": False},
            "esp_router": {"enabled": True, "ap_host": "192.168.4.1"},
        }
        completed = type("Completed", (), {"returncode": 0})()
        with tempfile.TemporaryDirectory() as folder:
            with patch("dashboard_data.subprocess.run", return_value=completed) as run:
                devices = DashboardData(Path(folder), config, FakeBattery()).esp_devices()
        router = next(device for device in devices if device["id"] == "router")
        self.assertTrue(router["connected"])
        self.assertEqual(router["reachable_hosts"], ["192.168.4.1"])
        self.assertIn("192.168.4.1", run.call_args.args[0])

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

    def test_settings_remains_available_without_desktop_autostart(self):
        config = {
            "linky": {"enabled": False}, "shelly": {"enabled": False},
            "battery": {"enabled": False}, "shelly2": {"enabled": False},
            "tp_link": {"enabled": False}, "hoymiles_proxy": {"enabled": False}, "esp_router": {"enabled": False},
            "tarifs_edf": {},
        }
        with tempfile.TemporaryDirectory() as folder:
            with patch("dashboard_data.autostart_status", side_effect=OSError("unsupported")):
                settings = DashboardData(Path(folder), config, FakeBattery()).settings()
        self.assertEqual(settings["autostart"], {"enabled": False, "computer": "Raspberry Pi"})


if __name__ == "__main__":
    unittest.main()
