"""Configuration-specific UI and billing, without contacting real hardware."""
import ast
import calendar
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock

SOURCE = (Path(__file__).resolve().parents[1] / 'boite_noire_hoymiles.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)


def functions(namespace, *names):
    nodes = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<equipment>', 'exec'), namespace)


class EquipmentTests(TestCase):
    def namespace(self, linky, shelly):
        ns = {'CONFIG': {'linky': {'enabled': linky}, 'shelly': {'enabled': shelly},
                         'tarifs_edf': {'plages_hc': ''}}, 'math': math,
              'datetime': datetime, 'timedelta': timedelta, 'calendar': calendar}
        functions(ns, 'equipment_enabled', 'equipment_status', 'finite_mobile_value',
                  'automatic_energy_series', 'mobile_point', 'save_config')
        return ns

    def test_three_modes_filter_legend_and_tooltip_without_connection_dependency(self):
        for linky, shelly in ((True, False), (False, True), (True, True), (False, False)):
            with self.subTest(linky=linky, shelly=shelly):
                ns = self.namespace(linky, shelly)
                names = ('line_limit', 'line_grid', 'line_ac', 'line_linky', 'line_shelly_a', 'line_shelly_b')
                ns.update({name: name for name in names})
                assignment = next(n for n in TREE.body if isinstance(n, ast.Assign)
                                  and any(isinstance(t, ast.Name) and t.id == 'equipment_lines' for t in n.targets))
                exec(compile(ast.Module(body=[assignment], type_ignores=[]), '<legend>', 'exec'), ns)
                visible = [name for name, enabled in ns['equipment_lines'] if enabled]
                self.assertEqual('line_linky' in visible, linky)
                self.assertEqual('line_shelly_a' in visible, shelly)
                call = next(n.value for n in TREE.body if isinstance(n, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == 'cursor_content' for t in n.targets))
                expression = next(k.value for k in call.keywords if k.arg == 'children')
                for n in ast.walk(expression):
                    if isinstance(n, ast.Name) and n.id.startswith('cursor_'):
                        ns[n.id] = n.id
                children = eval(compile(ast.Expression(expression), '<tooltip>', 'eval'), ns)
                self.assertEqual('cursor_dinky_text' in children, linky)
                self.assertEqual('cursor_shelly_grid_text' in children, shelly)
                self.assertEqual('cursor_note_text' in children, linky and shelly)
                status = ns['equipment_status']('hors ligne', 'absent', 'hors ligne')
                self.assertEqual('Linky' in status, linky)
                self.assertEqual('Shelly' in status, shelly)
                if linky or shelly:
                    self.assertIn('hors ligne', status)

    def test_shelly_billing_ignores_export_and_excessive_gap(self):
        ns = self.namespace(False, True)
        start = datetime(2026, 9, 12, 1)
        ns.update(times=[start, start + timedelta(minutes=1), start + timedelta(minutes=2)],
                  ac_power=[100, 100, 100], shelly_b_power=[1000, -2000, 1000],
                  parse_hc_ranges=lambda _: [], is_hc=lambda when, ranges: False,
                  read_dinky_history=Mock(side_effect=AssertionError('Dinky must not be read')))
        result = ns['automatic_energy_series']('24h', start + timedelta(minutes=20))
        self.assertAlmostEqual(sum(result[2]), 1000 * 240 / 3_600_000)
        self.assertIn('Estimation Shelly', result[6])
        ns['CONFIG']['shelly']['grid_export_positive'] = True
        result = ns['automatic_energy_series']('24h', start + timedelta(minutes=20))
        self.assertAlmostEqual(sum(result[2]), 2000 * 60 / 3_600_000)

    def test_both_devices_keep_linky_indexes_as_billing_source(self):
        ns = self.namespace(True, True)
        t = datetime(2026, 9, 12, 0)
        u = datetime(2026, 9, 12, 12)
        ns.update(times=[], ac_power=[],
                  linky_hc_index=[(t, 100), (u, 100)],
                  linky_hp_index=[(t, 200), (u, 200.025)],
                  read_dinky_history=Mock(return_value=([1] * 24, [2] * 24)))
        result = ns['automatic_energy_series']('24h', u)
        self.assertAlmostEqual(sum(result[2]), 0.025)
        ns['read_dinky_history'].assert_not_called()
        self.assertIn('Index Linky', result[6])
        ns['linky_hp_index'] = [(t, 200), (u, 200)]
        result = ns['automatic_energy_series']('24h', u)
        self.assertEqual(sum(result[2]), 0)

    def test_disabled_shelly_does_not_supply_mobile_backup_from_old_history(self):
        ns = self.namespace(True, False)
        ns.update(times=[datetime(2026, 9, 12)], ac_power=[float('nan')],
                  shelly_a_power=[1000], shelly_b_power=[-500], linky_power=[0])
        point = ns['mobile_point'](0)
        self.assertIsNone(point['production_w'])
        self.assertIsNone(point['export_w'])
        self.assertEqual(point['linky_w'], 0)

    def test_other_settings_save_preserves_pending_equipment_choice(self):
        ns = self.namespace(True, True)
        with TemporaryDirectory() as directory:
            ns.update(json=json, CONFIG_FILE=Path(directory)/'config.json',
                      pending_equipment={'shelly': {'enabled': False, 'host': 'test.local'}})
            ns['save_config']()
            saved = json.loads(ns['CONFIG_FILE'].read_text())
            self.assertFalse(saved['shelly']['enabled'])
            self.assertTrue(ns['CONFIG']['shelly']['enabled'])
