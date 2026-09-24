import plistlib
import tempfile
import unittest
from pathlib import Path

from autostart import set_enabled, status


class AutostartTests(unittest.TestCase):
    def test_windows_can_be_enabled_and_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base, roaming = root / "program", root / "roaming"
            base.mkdir()
            launcher = base / "LANCER_INTERFACE_WEB.vbs"
            launcher.write_text("Option Explicit", encoding="utf-8")

            result = set_enabled(True, base, platform="win32", appdata=roaming)
            startup = roaming / "Microsoft/Windows/Start Menu/Programs/Startup/Boite noire Hoymiles.vbs"
            self.assertTrue(result["enabled"])
            self.assertEqual(result["computer"], "Windows")
            self.assertIn(str(launcher), startup.read_text(encoding="utf-16"))

            self.assertFalse(set_enabled(False, base, platform="win32", appdata=roaming)["enabled"])
            self.assertFalse(startup.exists())

    def test_mac_can_be_enabled_and_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base, home = root / "BoiteNoireHoymiles", root / "home"
            base.mkdir()
            launcher = base / "LANCER_INTERFACE_WEB.command"
            launcher.write_text("#!/bin/bash", encoding="utf-8")

            result = set_enabled(True, base, platform="darwin", home=home)
            plist = home / "Library/LaunchAgents/fr.boitenoirehoymiles.web.plist"
            with plist.open("rb") as handle:
                saved = plistlib.load(handle)
            self.assertEqual(result, {"enabled": True, "computer": "Mac", "applies_next_start": True})
            self.assertEqual(saved["ProgramArguments"], [str(launcher)])
            self.assertTrue(saved["RunAtLoad"])
            self.assertTrue(saved["KeepAlive"])

            set_enabled(False, base, platform="darwin", home=home)
            self.assertFalse(status(base, platform="darwin", home=home)["enabled"])
            self.assertFalse(plist.exists())

    def test_missing_launcher_is_not_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(OSError, "introuvable"):
                set_enabled(True, root / "missing", platform="darwin", home=root / "home")


if __name__ == "__main__":
    unittest.main()
