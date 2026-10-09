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
                raspberry = package_platforms.raspberry_archive()
                release = package_platforms.version()
                with tarfile.open(mac, "r:gz") as archive:
                    names = {m.name for m in archive.getmembers()}
                    launchers = [m for m in archive.getmembers()
                                 if "/MacOS/" in m.name and m.isfile()]
                    self.assertTrue(launchers)
                    self.assertTrue(all(m.mode & 0o111 for m in launchers))
                    self.assertTrue(all("\\" not in m.name for m in archive.getmembers()))
                    self.assertIn(
                        f"Hoymiles-{release}-Mac/1 - INSTALLER BOITE NOIRE HOYMILES.app/Contents/Resources/Payload/macOS-AppleSilicon/installer_mac.sh",
                        names,
                    )
                    visible = {m.name.split("/", 2)[1] for m in archive.getmembers()
                               if m.name.startswith(f"Hoymiles-{release}-Mac/")}
                    self.assertEqual(visible, {
                        "1 - INSTALLER BOITE NOIRE HOYMILES.app",
                        "2 - SI LE MAC REFUSE - INSTALLER.command",
                        "3 - LIRE-MOI-MAC.txt",
                    })
                    repair = archive.extractfile(
                        f"Hoymiles-{release}-Mac/2 - SI LE MAC REFUSE - INSTALLER.command"
                    ).read()
                    self.assertTrue(repair.startswith(b"#!/bin/bash\n"))
                    self.assertNotIn(b"\r", repair)
                    self.assertIn(b"chmod +x", repair)
                    self.assertIn(b"xattr -dr com.apple.quarantine", repair)
                    self.assertIn(b"exec /bin/bash", repair)
                with tarfile.open(mac_full, "r:gz") as archive:
                    names = {m.name for m in archive.getmembers()}
                    prefix = f"Homlis-DTU-PRO-S-{release}-Mac/"
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
                    self.assertTrue(any(n.endswith('/CHOISIR_INTERFACE.vbs')
                                        for n in archive.namelist()))
                with zipfile.ZipFile(mac_zip) as archive:
                    launchers = [i for i in archive.infolist() if "/MacOS/" in i.filename]
                    self.assertTrue(launchers)
                    self.assertTrue(all((i.external_attr >> 16) & 0o111 for i in launchers))
                    self.assertTrue(all(b"\r\n" not in archive.read(i) for i in launchers))
                    root = f"Hoymiles-{release}-Mac/"
                    visible = {n.split("/", 2)[1] for n in archive.namelist()
                               if n.startswith(root)}
                    self.assertEqual(visible, {
                        "1 - INSTALLER BOITE NOIRE HOYMILES.app",
                        "2 - LIRE-MOI-MAC.txt",
                    })
                with tarfile.open(raspberry, "r:gz") as archive:
                    names = {m.name for m in archive.getmembers()}
                    installer = f"Hoymiles-{release}-Raspberry/raspberry-pi/INSTALLER_RASPBERRY.sh"
                    self.assertIn(installer, names)
                    self.assertTrue(archive.getmember(installer).mode & 0o111)
                    self.assertFalse(any("config_v5.json" in name or name.endswith(".csv") for name in names))
                    body = b"".join(archive.extractfile(m).read() for m in archive.getmembers() if m.isfile())
                    self.assertNotIn(b"192.168.1.205", body)
        finally:
            package_platforms.OUTPUTS = old


if __name__ == "__main__":
    unittest.main()
