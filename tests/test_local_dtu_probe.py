import json
import unittest
from unittest.mock import patch

from local_dtu_probe import run_read, safe_error, summary


class Result:
    def __init__(self, payload, returncode=0):
        self.stdout = json.dumps(payload)
        self.stderr = ""
        self.returncode = returncode


class LocalDtuProbeTests(unittest.TestCase):
    def test_only_accepts_read_commands(self):
        with self.assertRaises(ValueError):
            run_read("client", "192.168.1.206", "192.168.1.10", "set-power-limit")

    def test_read_call_has_no_power_limit_or_write_command(self):
        with patch("local_dtu_probe.subprocess.run", return_value=Result({"is_encrypted": False})) as execute:
            run_read("client", "192.168.1.206", "192.168.1.10", "is-encrypted")
        command = execute.call_args.args[0]
        self.assertEqual(command[-1], "is-encrypted")
        self.assertNotIn("set-power-limit", command)
        self.assertNotIn("restart-dtu", command)

    def test_summary_converts_protocol_tenths_of_watts(self):
        result = summary({"sgsData": [{"serialNumber": 1164, "activePower": 1337}]}, "192.168.1.206", "192.168.1.10", True)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["total_power_w"], 133.7)
        self.assertEqual(result["inverter_count"], 1)

    def test_errors_do_not_expose_a_local_secret(self):
        self.assertNotIn("00112233445566778899aabbccddeeff", safe_error("enc_rand=00112233445566778899aabbccddeeff"))
