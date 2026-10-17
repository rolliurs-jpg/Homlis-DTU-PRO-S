import unittest

from smart_regulation import SmartRegulation


class SmartRegulationTests(unittest.TestCase):
    def sample(self, timestamp=1000, grid_w=-900, production_w=2000, **battery):
        values = dict(soc_pct=99, ac_charge_w=65, ac_discharge_w=0, charge_w=65)
        values.update(battery)
        return dict(timestamp=timestamp, grid_w=grid_w, production_w=production_w, battery=values)

    def confirmed(self, regulation):
        for timestamp in range(1000, 1181, 15):
            result = regulation.decide(self.sample(timestamp), timestamp)
        return result

    def test_prioritizes_battery_before_full_confirmation(self):
        regulation = SmartRegulation(3000)
        self.assertEqual(regulation.decide(self.sample(), 1000).limit_pct, 100)
        self.assertFalse(regulation.decide(self.sample(1179), 1179).battery_full_confirmed)

    def test_limits_only_after_bms_stops_accepting_charge(self):
        regulation = SmartRegulation(3000)
        result = self.confirmed(regulation)
        self.assertTrue(result.battery_full_confirmed)
        self.assertEqual(result.limit_pct, 38)

    def test_charge_or_discharge_immediately_restores_full_production(self):
        for battery in (dict(ac_charge_w=101), dict(charge_w=101), dict(ac_discharge_w=21), dict(soc_pct=98)):
            regulation = SmartRegulation(3000)
            self.confirmed(regulation)
            result = regulation.decide(self.sample(1195, **battery), 1195)
            self.assertEqual(result.limit_pct, 100)
            self.assertFalse(result.battery_full_confirmed)

    def test_missing_or_stale_measurements_fail_open(self):
        regulation = SmartRegulation(3000)
        self.confirmed(regulation)
        self.assertEqual(regulation.decide({}, 1200).limit_pct, 100)
        self.assertEqual(regulation.decide(self.sample(1000), 1200).limit_pct, 100)

    def test_keeps_small_export_buffer_and_never_stops_panels(self):
        regulation = SmartRegulation(3000)
        self.confirmed(regulation)
        result = regulation.decide(self.sample(1195, grid_w=-2500, production_w=2000), 1195)
        self.assertEqual(result.limit_pct, 2)


if __name__ == "__main__":
    unittest.main()
