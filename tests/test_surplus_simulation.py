import unittest
from datetime import datetime
from surplus_simulation import SurplusSimulation
class ClockSimulation(SurplusSimulation):
 def evaluate(self,s,now):return super().evaluate(s,now+1700000000)

class SimulationTests(unittest.TestCase):
 def sample(self,t=1000,**kw):
  s=dict(timestamp=datetime.fromtimestamp(t+1700000000).isoformat(),battery_timestamp=t+1700000000,battery_enabled=True,production_complete=True,battery_soc_pct=100,battery_ac_charge_w=0,battery_ac_discharge_w=0,pv2_w=600,import_w=0,export_w=300);s.update(kw);return s
 def full(self,e):
  for t in range(1000,1121,15):r=e.evaluate(self.sample(t),t)
  return r
 def test_dwell(self):
  e=ClockSimulation();self.assertEqual(e.evaluate(self.sample(),1000)['hms1000_limit_pct'],100)
  r=self.full(e);self.assertTrue(r['battery_full_confirmed']);self.assertEqual(r['hms1000_limit_pct'],27)
 def test_charge_priority(self):
  e=ClockSimulation();self.full(e)
  r=e.evaluate(self.sample(1135,battery_ac_charge_w=100),1135);self.assertEqual(r['hms1000_limit_pct'],100)
 def test_discharge_release(self):
  e=ClockSimulation();self.full(e)
  self.assertEqual(e.evaluate(self.sample(1135,battery_ac_discharge_w=100),1135)['hms1000_limit_pct'],100)
 def test_hysteresis(self):
  e=ClockSimulation();self.full(e)
  self.assertTrue(e.evaluate(self.sample(1135,battery_soc_pct=99),1135)['battery_full_confirmed'])
  self.assertFalse(e.evaluate(self.sample(1150,battery_soc_pct=97),1150)['battery_full_confirmed'])
 def test_invalid(self):
  for key,val in [('pv2_w',None),('export_w',float('nan')),('battery_timestamp',1700000800),('production_complete',False),('import_w',-10)]:
   e=ClockSimulation();self.full(e);r=e.evaluate(self.sample(1135,**{key:val}),1135);self.assertIsNone(r['hms1000_limit_pct']);self.assertFalse(e.full)
 def test_gap_resets(self):
  e=ClockSimulation();self.full(e);r=e.evaluate(self.sample(1500),1500);self.assertFalse(r['battery_full_confirmed'])
 def test_uncontrollable(self):
  e=ClockSimulation();self.full(e);r=e.evaluate(self.sample(1135,export_w=1000),1135);self.assertEqual(r['uncontrolled_surplus_w'],500);self.assertEqual(r['hms1000_limit_pct'],10)
 def test_duplicate_does_not_confirm(self):
  e=ClockSimulation()
  for _ in range(20):r=e.evaluate(self.sample(),1000)
  self.assertFalse(r['battery_full_confirmed'])
 def test_minute_cadence_can_confirm_full(self):
  e=ClockSimulation()
  for t in (1000,1060,1120):r=e.evaluate(self.sample(t),t)
  self.assertTrue(r['battery_full_confirmed'])
 def test_old_battery_blocks_even_when_grid_is_recent(self):
  e=ClockSimulation()
  r=e.evaluate(self.sample(1000,battery_timestamp=1700000950),1000)
  self.assertIsNone(r['hms1000_limit_pct'])
 def test_no_commands(self):
  self.assertFalse(self.full(ClockSimulation())['commands_enabled'])
if __name__=='__main__':unittest.main()
