import json
import unittest
from unittest.mock import patch

from opendtu_trial import OpenDtuReadOnly


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class OpenDtuTrialTests(unittest.TestCase):
    def test_disabled_never_opens_a_network_connection(self):
        with patch("opendtu_trial.urlopen") as request:
            result = OpenDtuReadOnly({"enabled": False}).snapshot()
        self.assertEqual(result["state"], "disabled")
        request.assert_not_called()

    def test_reads_common_open_dtu_live_data_without_command(self):
        data = {"inverters": [{"serial": "one", "AC": {"Power": {"v": 321.5}}}, {"serial": "two", "power": 128.5}]}
        with patch("opendtu_trial.urlopen", return_value=Response(data)) as request:
            result = OpenDtuReadOnly({"enabled": True, "host": "192.168.1.250"}).snapshot()
        self.assertEqual(result["state"], "online")
        self.assertEqual(result["inverter_count"], 2)
        self.assertEqual(result["power_w"], 450.0)
        self.assertTrue(result["read_only"])
        self.assertEqual(request.call_args.args[0].get_method(), "GET")
