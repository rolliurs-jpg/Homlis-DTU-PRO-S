from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InterfaceChooserTests(unittest.TestCase):
    def test_windows_shortcut_uses_interface_chooser(self):
        installer = (ROOT / "INSTALLER_WINDOWS.vbs").read_text(encoding="utf-8-sig")
        chooser = (ROOT / "CHOISIR_INTERFACE.vbs").read_text(encoding="utf-8-sig")
        self.assertIn('CHOISIR_INTERFACE.vbs', installer)
        self.assertIn('Nouvelle interface web', chooser)
        self.assertIn('Ancien logiciel avec sa fenetre', chooser)
        self.assertIn('StopInvisibleProgram', chooser)
        self.assertIn('--web-only', chooser)


if __name__ == "__main__":
    unittest.main()
