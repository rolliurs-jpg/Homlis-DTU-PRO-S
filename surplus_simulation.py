"""Simulation de limitation : aucune connexion ni commande aux appareils."""
import math
from datetime import datetime

def finite(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

class SurplusSimulation:
    def __init__(self):
        self.full_since=None
        self.full=False
        self.last_stamp=None

    def evaluate(self, s, now):
        out={'mode':'simulation','commands_enabled':False,'reason':'Mesures indisponibles','hms1000_limit_pct':None,'uncontrolled_surplus_w':None}
        try:
            stamp=datetime.fromisoformat(s['timestamp']).timestamp()
            battery_stamp=s['battery_timestamp']
            if not finite(battery_stamp) or not (0<=now-stamp<=90 and 0<=now-battery_stamp<=45):raise ValueError()
            keys=('battery_soc_pct','battery_ac_charge_w','battery_ac_discharge_w','pv2_w','import_w','export_w')
            if not all(finite(s.get(k)) for k in keys):raise ValueError()
            if not s.get('battery_enabled') or not s.get('production_complete'):raise ValueError()
            soc=s['battery_soc_pct'];charge=s['battery_ac_charge_w'];discharge=s['battery_ac_discharge_w']
            pv=s['pv2_w'];grid=s['import_w']-s['export_w']
            if not (0<=soc<=100 and 0<=pv<=1500 and 0<=charge<=10000 and 0<=discharge<=10000):raise ValueError()
            if s['import_w']<0 or s['export_w']<0 or (s['import_w']>1 and s['export_w']>1):raise ValueError()
        except (KeyError,ValueError,TypeError,OverflowError,OSError):
            self.full_since=None;self.full=False;self.last_stamp=None
            out['reason']='Simulation suspendue : mesures absentes, anciennes ou production incomplète.'
            return out
        if self.last_stamp is not None and (stamp<self.last_stamp or stamp-self.last_stamp>90):
            self.full_since=None;self.full=False
        self.last_stamp=stamp
        if soc<=97 or charge>50 or discharge>20:
            self.full=False;self.full_since=None
        elif not self.full:
            if soc>=100 and charge<=30 and discharge<=20:
                if self.full_since is None:self.full_since=stamp
                if stamp-self.full_since>=120:self.full=True
            else:self.full_since=None
        out['battery_full_confirmed']=self.full
        out['grid_w']=grid
        if not self.full:
            out['hms1000_limit_pct']=100
            out['reason']='Laisser produire pour la maison et la charge batterie.' if self.full_since is None else 'Plein détecté : confirmation pendant 2 minutes avant réduction.'
            return out
        # Indicative ceiling only, based on the measured contribution of the two panels.
        # +30 W grid import margin. Do not treat this as a production forecast.
        desired=max(100,min(1000,pv+grid-30))
        out['hms1000_limit_pct']=round(desired/10,1)
        out['uncontrolled_surplus_w']=round(max(0,-grid-max(0,pv-100)),1)
        out['reason']='Batterie pleine confirmée : plafond indicatif pour les deux panneaux.'
        if out['uncontrolled_surplus_w']>30:
            out['reason']+=' Les quatre autres panneaux doivent aussi être limités.'
        out['note']='Estimation seule : aucune commande. Le plafond ne prédit pas la production réelle.'
        return out
