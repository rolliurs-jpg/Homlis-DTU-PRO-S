from pathlib import Path
import plistlib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MacPackageTests(unittest.TestCase):
    def test_mac_scripts_have_unix_newlines(self):
        scripts = [p for p in ROOT.rglob('*') if p.is_file() and
                   (p.suffix in ('.sh', '.command') or p.parent.name == 'MacOS')]
        self.assertGreaterEqual(len(scripts), 6)
        for path in scripts:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertTrue(path.read_bytes().startswith(b'#!/bin/bash\n'))
                self.assertNotIn(b'\r', path.read_bytes())

    def test_application_entry_points_exist(self):
        for path in ROOT.rglob('Info.plist'):
            with self.subTest(path=str(path.relative_to(ROOT))):
                info = plistlib.loads(path.read_bytes())
                self.assertTrue((path.parent/'MacOS'/info['CFBundleExecutable']).is_file())
                self.assertEqual(info['CFBundleShortVersionString'], '7.0.46')
