"""Exerce le callback réel sans démarrer l'application ni interroger les appareils."""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class AlarmUITests(TestCase):
    def test_timer_never_opens_configuration_and_rings_once_per_outage(self):
        source=(Path(__file__).resolve().parents[1]/'boite_noire_hoymiles.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        callback=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='refresh_alarm')
        state={'active':False,'last_ping':None,'last_measure':100,'recovery':None}
        parent=SimpleNamespace(bell=Mock())
        opened=Mock()
        button=SimpleNamespace(ax=SimpleNamespace(set_facecolor=Mock()),label=SimpleNamespace(set_text=Mock()))
        namespace={'monitor':SimpleNamespace(snapshot=lambda:state),'datetime':datetime,
                   'alarm_button':button,'alarm_notice':[None],'open_settings':opened,
                   'dialog_parent':lambda:parent,'fig':SimpleNamespace(canvas=SimpleNamespace(draw_idle=Mock()))}
        exec(compile(ast.Module(body=[callback],type_ignores=[]),'<alarm-callback>','exec'),namespace)
        refresh=namespace['refresh_alarm']
        refresh()
        state['recovery']={'to':500}
        refresh()
        refresh()
        parent.bell.assert_not_called()
        state['active']=True
        for _ in range(20):refresh()
        self.assertEqual(parent.bell.call_count,1)
        button.label.set_text.assert_called_with('ALARME')
        state['active']=False
        state['last_measure']=700
        state['recovery']={'to':700}
        for _ in range(20):refresh()
        self.assertEqual(parent.bell.call_count,1)
        button.label.set_text.assert_called_with('Alarmes')
        state['active']=True
        refresh()
        self.assertEqual(parent.bell.call_count,2)
        opened.assert_not_called()
