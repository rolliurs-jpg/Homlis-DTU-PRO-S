import json
import tempfile
import unittest
from pathlib import Path
from monitoring import Monitoring, has_measure, valid_ping_url

URL = 'https://hc-ping.com/00000000-0000-0000-0000-000000000001'


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1000
        self.sent = []
        self.monitor = Monitoring(self.tmp.name, clock=lambda: self.now, sender=self.sent.append)

    def tearDown(self):
        self.tmp.cleanup()

    def test_night_zero_is_a_real_measure(self):
        self.monitor.configure(URL)
        self.monitor.record([0, None, float('nan')])
        self.monitor._dispatch()
        self.assertEqual(self.sent, [URL])
        self.assertEqual(self.monitor.snapshot()['last_measure'], 1000)

    def test_missing_values_do_not_send_healthy_signal(self):
        self.monitor.configure(URL)
        self.monitor.record([None, '', float('nan'), float('inf')])
        self.monitor._dispatch()
        self.now += 301
        self.assertTrue(self.monitor.snapshot()['active'])
        self.assertEqual(self.sent, [])

    def test_open_but_frozen_application_alarms(self):
        self.monitor.record([1])
        self.now += 299
        self.assertFalse(self.monitor.snapshot()['active'])
        self.now += 1
        self.assertTrue(self.monitor.snapshot()['active'])

    def test_restart_gap_and_recovery_are_recorded_once(self):
        self.monitor.seed(100)
        self.monitor.record([0])
        self.assertEqual(self.monitor.snapshot()['recovery']['seconds'], 900)
        self.now += 60
        self.monitor.record([2])
        events = [json.loads(row) for row in (Path(self.tmp.name)/'interruptions_suivi.jsonl').read_text().splitlines()]
        self.assertEqual([e['event'] for e in events], ['reprise'])

    def test_history_cannot_arm_remote_monitor(self):
        self.monitor.configure(URL)
        self.monitor.seed(990)
        self.monitor._dispatch()
        self.assertEqual(self.sent, [])

    def test_stale_queued_signal_is_discarded(self):
        self.monitor.configure(URL)
        self.monitor.record([0])
        self.now += 91
        self.monitor._dispatch()
        self.assertEqual(self.sent, [])

    def test_network_failure_does_not_break_collection_or_leak_key(self):
        def fail(url):
            raise OSError(url)
        self.monitor.sender = fail
        self.monitor.configure(URL)
        self.monitor.record([20])
        self.monitor._dispatch()
        state = self.monitor.snapshot()
        self.assertFalse(state['active'])
        self.assertIsNone(state['last_ping'])
        self.assertNotIn(URL, json.dumps(state))
        self.assertIn('impossible', state['remote'])

    def test_configuration_survives_restart(self):
        self.monitor.configure(URL)
        other = Monitoring(self.tmp.name)
        self.assertEqual(other.url, URL)
        self.assertIsNone(other.last_ping)

    def test_disable_cancels_pending_ping(self):
        self.monitor.configure(URL)
        self.monitor.record([10])
        self.monitor.configure('')
        self.monitor._dispatch()
        self.assertEqual(self.sent, [])

    def test_linky_only_counts_as_a_measure(self):
        self.assertTrue(has_measure([None, 30, None, None]))

    def test_reject_unsafe_urls(self):
        for url in ['http://hc-ping.com/x', URL+'/fail', URL+'?x=1',
                    'https://hc-ping.com@evil.test/x', 'https://127.0.0.1/x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                valid_ping_url(url)

    def test_copy_from_healthchecks_table_removes_visual_spacing(self):
        for separator in [' ', '\u00a0', '\u200b', '\n', '\t']:
            with self.subTest(separator=repr(separator)):
                copied = URL.replace('com/', 'com/' + separator)
                self.assertEqual(valid_ping_url(copied), URL)
                self.monitor.configure(copied)
                self.assertEqual(self.monitor.url, URL)


if __name__ == '__main__':
    unittest.main()
