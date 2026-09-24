from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import package_platforms


class PlatformPackageTests(unittest.TestCase):
    def test_mac_launcher_permissions_and_windows_separation(self):
        old = package_platforms.OUTPUTS
        try:
            with tempfile.TemporaryDirectory() as folder:
                package_platforms.OUTPUTS = Path(folder)
                mac = package_platforms.mac_archive()
                mac_full = package_platforms.mac_full_archive()
                mac_zip = package_platforms.mac_full_zip()
                windows = package_platforms.windows_archive()
                with tarfile.open(mac, "r:gz") as archive:
                    names = {m.name for m in archive.getmembers()}
                    launchers = [m for m in archive.getmembers()
                                 if "/MacOS/" in m.name and m.isfile()]
                    self.assertTrue(launchers)
                    self.assertTrue(all(m.mode & 0o111 for m in launchers))
                    self.assertTrue(all("\\" not in m.name for m in archive.getmembers()))
                    self.assertIn(
                        "Hoymiles-7.0.54-Mac/INSTALLER HOYMILES MAC 7.0.54.app/Contents/Resources/Payload/macOS-AppleSilicon/installer_mac.sh",
                        names,
                    )
                with tarfile.open(mac_full, "r:gz") as archive:
                    names = {m.name for m in archive.getmembers()}
                    prefix = "Homlis-DTU-PRO-S-7.0.54-Mac/"
                    self.assertIn(prefix + "battery_monitor.py", names)
                    self.assertIn(prefix + "dashboard_ui.html", names)
                    self.assertIn(
                        prefix + "macOS-AppleSilicon/Installer Boîte noire Hoymiles.app/Contents/MacOS/InstallerBoiteNoireHoymiles",
                        names,
                    )
                with zipfile.ZipFile(windows) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertFalse(any("Mac.app" in n or "macOS-" in n
                                         for n in archive.namelist()))
                with zipfile.ZipFile(mac_zip) as archive:
                    launchers = [i for i in archive.infolist() if "/MacOS/" in i.filename]
                    self.assertTrue(launchers)
                    self.assertTrue(all((i.external_attr >> 16) & 0o111 for i in launchers))
                    self.assertTrue(all(b"\r\n" not in archive.read(i) for i in launchers))
        finally:
            package_platforms.OUTPUTS = old


if __name__ == "__main__":
    unittest.main()
