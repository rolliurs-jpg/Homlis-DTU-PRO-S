import unittest
from unittest.mock import patch
from hoymiles_proxy import ProxyReader

class ProxyTests(unittest.TestCase):
    def test_disabled_reader_does_not_start(self):
        p=ProxyReader({})
        p.start()
        self.assertIsNone(p._thread)
        self.assertFalse(p.snapshot()["commands_enabled"])

    def test_stale_measurements_are_not_displayed_as_current(self):
        p=ProxyReader({})
        p._set(state="online", timestamp=100, power_w=600, limit_pct=10)
        with patch("hoymiles_proxy.time.time",return_value=146):
            s=p.snapshot()
        self.assertEqual(s["state"],"stale")
        self.assertNotIn("power_w",s)
        self.assertNotIn("limit_pct",s)

    def test_failed_connection_clears_previous_reading(self):
        p=ProxyReader({})
        p._set(state="online", timestamp=100, power_w=600, limit_pct=10)
        p._set(state="offline", reason="timeout")
        self.assertNotIn("power_w",p.snapshot())

    def test_read_timeout_is_retried_without_requesting_pin(self):
        p = ProxyReader({"enabled": True})
        calls = []
        async def session():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("InverterDataUnavailable")
            p._set(state="online", power_w=500)
            p._stop.set()
        p.session = session
        with patch.object(p._stop, "wait", return_value=False):
            p._worker()
        self.assertEqual(len(calls), 2)
        self.assertEqual(p.snapshot()["state"], "online")

    def test_commands_reject_boolean_and_out_of_range(self):
        p = ProxyReader({"commands_enabled": True})
        for value in (True, False, 0, 101, 50.5):
            self.assertFalse(p.request_limit(value))
        self.assertTrue(p.request_limit(50))
