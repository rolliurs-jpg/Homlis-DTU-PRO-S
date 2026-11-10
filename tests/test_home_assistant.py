import unittest

from mobile_dashboard import home_assistant_payload


class HomeAssistantPayloadTests(unittest.TestCase):
    def test_exposes_only_read_only_measurements(self):
        payload = home_assistant_payload({
            'timestamp': '2026-11-07T15:30:00', 'quality': 'complete',
            'production_w': 1200, 'consumption_w': 340, 'import_w': 0,
            'export_w': 860, 'battery_soc_pct': 98,
            'battery_ac_charge_w': 120, 'battery_ac_discharge_w': 0,
            'dtu_state': 'online', 'linky_state': 'online', 'shelly_state': 'online',
            'surplus_simulation': {'commands_enabled': True},
        })
        self.assertTrue(payload['available'])
        self.assertEqual(payload['power']['solar_w'], 1200.0)
        self.assertEqual(payload['power']['grid_export_w'], 860.0)
        self.assertEqual(payload['battery']['soc_pct'], 98.0)
        self.assertEqual(payload['devices']['dtu'], 'online')
        self.assertNotIn('surplus_simulation', payload)

    def test_marks_missing_measurements_unavailable(self):
        payload = home_assistant_payload({'timestamp': None, 'quality': 'missing'})
        self.assertFalse(payload['available'])
        self.assertIsNone(payload['power']['solar_w'])
        self.assertEqual(payload['devices']['dtu'], 'unknown')
