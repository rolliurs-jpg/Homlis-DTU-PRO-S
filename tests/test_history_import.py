import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'macOS-AppleSilicon' / 'importer_historique_windows.py'
SPEC = importlib.util.spec_from_file_location('history_importer', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
import_history = MODULE.import_history


class HistoryImportTests(unittest.TestCase):
    def test_windows_is_reference_and_newer_mac_rows_are_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            mac, source = root/'mac', root/'windows'
            mac.mkdir(); source.mkdir()
            name = 'batterie_production2.csv'
            header = 'timestamp,soc_pct\n'
            (source/name).write_text(header+'100,90\n200,80\n', encoding='utf-8')
            (mac/name).write_text(header+'150,75\n250,70\n', encoding='utf-8')
            (mac/'config_v5.json').write_text(
                json.dumps({'battery': {'host': '192.168.1.39'},
                            'tarifs_edf': {'hp_eur_kwh': 0.1}}), encoding='utf-8')
            (source/'tarifs_windows.json').write_text(
                json.dumps({'hp_eur_kwh': 0.2142, 'hc_eur_kwh': 0.1589}), encoding='utf-8')
            backup, result = import_history(mac, source)
            with (mac/name).open(encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([(r['timestamp'], r['soc_pct']) for r in rows],
                             [('100', '90'), ('200', '80'), ('250', '70')])
            self.assertTrue((backup/name).exists())
            config = json.loads((mac/'config_v5.json').read_text(encoding='utf-8'))
            self.assertEqual(config['battery']['host'], '192.168.1.39')
            self.assertEqual(config['tarifs_edf']['hp_eur_kwh'], 0.2142)
            self.assertTrue((backup/'config_v5.json').exists())
            self.assertEqual(result[name], (2, 1))


if __name__ == '__main__':
    unittest.main()
