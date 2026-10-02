import unittest
from surplus_controller import SurplusController

class ControllerTests(unittest.TestCase):
 def controller(self):return SurplusController(None,None,enabled=True)
 def sample(self,t=1000,**kwargs):
  s=dict(timestamp=t,grid_w=-40,battery=dict(timestamp=t,soc_pct=100,ac_charge_w=0,ac_discharge_w=0),proxy=dict(state='online',timestamp=t,power_w=90,limit_pct=100));s.update(kwargs);return s
 def full(self,c):
  for t in range(1000,1121,15):r=c.evaluate(self.sample(t),t)
  return r
 def test_confirm_full_and_cut_below_fifty_in_low_sun(self):
  c=self.controller();self.assertEqual(c.evaluate(self.sample(),1000)['hms1000_limit_pct'],100)
  r=self.full(c);self.assertTrue(r['battery_full_confirmed']);self.assertEqual(r['hms1000_limit_pct'],2)
 def test_duplicate_samples_do_not_confirm_full(self):
  c=self.controller()
  for _ in range(20):r=c.evaluate(self.sample(),1000)
  self.assertFalse(r['battery_full_confirmed'])
 def test_missing_and_stale_restore_full_production(self):
  c=self.controller();self.full(c)
  self.assertEqual(c.evaluate({},1135)['hms1000_limit_pct'],100)
  self.assertFalse(c.full)
  self.assertEqual(c.evaluate(self.sample(1000),1200)['hms1000_limit_pct'],100)
 def test_gap_does_not_confirm_full(self):
  c=self.controller();c.evaluate(self.sample(),1000)
  self.assertFalse(c.evaluate(self.sample(1200),1200)['battery_full_confirmed'])
 def test_discharge_and_soc_release(self):
  for field,value in [('soc_pct',97),('ac_discharge_w',50),('ac_charge_w',80)]:
   c=self.controller();self.full(c);s=self.sample(1135);s['battery'][field]=value
   self.assertEqual(c.evaluate(s,1135)['hms1000_limit_pct'],100)
 def test_recovery_increases_current_ceiling(self):
  c=self.controller();self.full(c);s=self.sample(1135,grid_w=230);s['proxy']['limit_pct']=2
  self.assertEqual(c.evaluate(s,1135)['hms1000_limit_pct'],22)
 def test_other_array_surplus_is_reported(self):
  c=self.controller();self.full(c)
  self.assertGreater(c.evaluate(self.sample(1135,grid_w=-300),1135)['uncontrolled_surplus_w'],30)
 def test_nan_and_future_measurements_do_not_command_reduction(self):
  for value in [float('nan'),float('inf')]:
   c=self.controller();self.assertEqual(c.evaluate(self.sample(grid_w=value),1000)['hms1000_limit_pct'],100)
  c=self.controller();self.assertEqual(c.evaluate(self.sample(1010),1000)['hms1000_limit_pct'],100)

 def test_pause_and_resume_request_full_production(self):
  class Proxy:
   config={}
   requested=[]
   def request_limit(self,n):self.requested.append(n)
  p=Proxy();c=SurplusController(p,None,enabled=True);self.full(c)
  c.set_enabled(False)
  self.assertFalse(c.enabled);self.assertFalse(c.full)
  self.assertEqual(c.snapshot()['mode'],'paused');self.assertEqual(p.requested,[100])
  self.assertTrue(p.config['commands_enabled'])
  c.set_enabled(True);self.assertTrue(c.enabled);self.assertEqual(p.requested,[100,100])
  with self.assertRaises(ValueError):c.set_enabled('yes')

 def combined(self):
  class Dtu: rated_w=2000
  return SurplusController(None,None,enabled=True,dtu=Dtu())
 def combined_sample(self,t=1000,grid=-300):
  s=self.sample(t,grid_w=grid);s['proxy']['power_w']=300
  s['dtu']=dict(state='online',timestamp=t,power_w=600,limit_pct=100,port_limits_pct=[100]*4)
  return s
 def test_six_panels_share_reduction(self):
  c=self.combined()
  for t in range(1000,1121,15):r=c.evaluate(self.combined_sample(t),t)
  self.assertEqual(r['controlled_panels'],6)
  self.assertEqual(r['hms1000_limit_pct'],19);self.assertEqual(r['dtu_limit_pct'],19)
 def test_dtu_missing_or_mixed_limits_restore_both(self):
  c=self.combined();s=self.combined_sample();s['dtu']['port_limits_pct']=[90,100,100,100]
  r=c.evaluate(s,1000)
  self.assertEqual(r['hms1000_limit_pct'],100);self.assertEqual(r['dtu_limit_pct'],100)
 def test_six_panels_import_recovery(self):
  c=self.combined()
  for t in range(1000,1121,15):c.evaluate(self.combined_sample(t),t)
  s=self.combined_sample(1135,330);s['proxy']['limit_pct']=20;s['dtu']['limit_pct']=20;s['dtu']['port_limits_pct']=[20]*4
  r=c.evaluate(s,1135);self.assertEqual(r['hms1000_limit_pct'],30);self.assertEqual(r['dtu_limit_pct'],30)
