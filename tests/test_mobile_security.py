import unittest

from mobile_dashboard import _trusted_client


class MobileSecurityTests(unittest.TestCase):
    def test_dashboard_accepts_only_private_networks_and_tailnet(self):
        for address in ("127.0.0.1", "192.168.1.52", "10.0.0.5", "100.64.0.10", "fd7a:115c:a1e0::1"):
            with self.subTest(address=address):
                self.assertTrue(_trusted_client(address))
        for address in ("8.8.8.8", "203.0.113.10", "2001:4860:4860::8888", "not-an-ip"):
            with self.subTest(address=address):
                self.assertFalse(_trusted_client(address))
