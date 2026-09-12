from pathlib import Path
import plistlib
import unittest
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class MacPackageTests(unittest.TestCase):
    def test_installer_runs_resource_check_when_moved_alone(self):
        bash = shutil.which('bash')
        if not bash and Path('C:/Program Files/Git/bin/bash.exe').is_file():
            bash = 'C:/Program Files/Git/bin/bash.exe'
        if not bash:
            self.skipTest('Bash unavailable')
        with tempfile.TemporaryDirectory(prefix='hoymiles-isolated-') as folder:
            isolated = Path(folder)/'Installer sur Mac.app'
            shutil.copytree(ROOT/'Installer sur Mac.app', isolated)
            launcher = isolated/'Contents/MacOS/InstallerBoiteNoireHoymiles'
            result = subprocess.run([bash, launcher.as_posix(), '--check-resources'],
                                    cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Ressources internes', result.stdout)
            self.assertFalse((Path(folder)/'macOS-AppleSilicon').exists())

    def test_payload_matches_installation_sources(self):
        payload = ROOT/'Installer sur Mac.app/Contents/Resources/Payload'
        for path in payload.rglob('*'):
            if path.is_file():
                relative = path.relative_to(payload)
                with self.subTest(path=str(relative)):
                    self.assertEqual(path.read_bytes(), (ROOT/relative).read_bytes())

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
                self.assertEqual(info['CFBundleShortVersionString'], '7.0.50')
