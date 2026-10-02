import json
import unittest
from urllib.request import urlopen
from mobile_dashboard import MobileDashboard

class LiveProxyStatusTests(unittest.TestCase):
    def test_proxy_updates_without_waiting_for_house_collection(self):
        server = MobileDashboard(host="127.0.0.1")
        server.port = 0
        sample = {"state": "online", "power_w": 42, "timestamp": 100}
        server.proxy_snapshot = lambda: dict(sample)
        battery={"battery_soc_pct":80,"battery_ac_charge_w":640}
        server.battery_snapshot = lambda:dict(battery)
        server.update({"timestamp": "2026-10-01T18:00:00"}, [])
        self.assertTrue(server.start())
        try:
            url = f"http://127.0.0.1:{server._server.server_address[1]}/api/status"
            def read():
                with urlopen(url, timeout=3) as response:
                    return json.load(response)["current"]
            first = read()
            sample.update(power_w=33, timestamp=115)
            battery.update(battery_soc_pct=81,battery_ac_charge_w=620)
            second = read()
            self.assertEqual(first["hoymiles_proxy"]["power_w"], 42)
            self.assertEqual(second["hoymiles_proxy"]["power_w"], 33)
            self.assertEqual(second["timestamp"], first["timestamp"])
            self.assertEqual(first["battery_soc_pct"],80)
            self.assertEqual(second["battery_soc_pct"],81)
            self.assertEqual(second["battery_ac_charge_w"],620)
        finally:
            server.stop()
