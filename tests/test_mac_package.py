from pathlib import Path
import plistlib
import unittest
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class MacPackageTests(unittest.TestCase):
    def test_invisible_service_never_renders_desktop_chart(self):
        source = (ROOT/'boite_noire_hoymiles.py').read_text(encoding='utf-8')
        redraw = source[source.index('def redraw():'):source.index('def update_end_labels():')]
        self.assertIn('if WEB_ONLY:', redraw)
        self.assertRegex(redraw, r'if WEB_ONLY:\s+return')

    def test_installer_backs_up_all_mac_data_before_update(self):
        source = (ROOT/'macOS-AppleSilicon/installer_mac.sh').read_text(encoding='utf-8')
        self.assertIn('Sauvegardes/avant_mise_a_jour_', source)
        self.assertIn('"$BASE"/*.csv', source)
        self.assertIn('"$BASE"/*.json', source)
        self.assertIn('"$BASE"/*.jsonl', source)
        self.assertIn('"$BASE"/*.log', source)
        self.assertLess(source.index('Sauvegardes/avant_mise_a_jour_'),
                        source.index('CONFIG_FILE="$BASE/config_v5.json"'))

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

    def test_download_folder_installer_is_also_self_contained(self):
        bash = shutil.which('bash')
        if not bash and Path('C:/Program Files/Git/bin/bash.exe').is_file():
            bash = 'C:/Program Files/Git/bin/bash.exe'
        if not bash:
            self.skipTest('Bash unavailable')
        source = ROOT/'macOS-AppleSilicon/Installer Boîte noire Hoymiles.app'
        self.assertTrue((source/'Contents/Resources/Payload/battery_monitor.py').is_file())
        with tempfile.TemporaryDirectory(prefix='hoymiles-mac-isolated-') as folder:
            isolated = Path(folder)/'Installer Boîte noire Hoymiles.app'
            shutil.copytree(source, isolated)
            launcher = isolated/'Contents/MacOS/InstallerBoiteNoireHoymiles'
            result = subprocess.run([bash, launcher.as_posix(), '--check-resources'],
                                    cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Ressources internes', result.stdout)
            self.assertFalse((Path(folder)/'boite_noire_hoymiles.py').exists())

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
            if 'outputs' in path.relative_to(ROOT).parts:
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                info = plistlib.loads(path.read_bytes())
                self.assertTrue((path.parent/'MacOS'/info['CFBundleExecutable']).is_file())
                self.assertEqual(info['CFBundleShortVersionString'], '7.0.57')

    def test_main_mac_app_offers_both_interfaces(self):
        launcher = (ROOT/'macOS-AppleSilicon/Boîte noire Hoymiles.app/Contents/MacOS/BoiteNoireHoymiles').read_text(encoding='utf-8')
        self.assertIn('Nouvelle interface web', launcher)
        self.assertIn('Ancien logiciel', launcher)
        self.assertIn('launchctl bootout', launcher)
        self.assertIn('launchctl kickstart', launcher)
