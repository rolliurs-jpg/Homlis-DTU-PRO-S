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
        self.assertIn('WScript.Arguments(0)) = "/classic"', chooser)

    def test_web_dashboard_opens_the_real_classic_program(self):
        html = (ROOT / "dashboard_ui.html").read_text(encoding="utf-8")
        source = (ROOT / "boite_noire_hoymiles.py").read_text(encoding="utf-8")
        self.assertNotIn('href="/classic-mobile"', html)
        self.assertIn("action:'classic'", html)
        self.assertIn('Ouvrir le logiciel classique', html)
        self.assertIn("Number.isFinite(live.pv2_w)?'Mesure reçue':null", html)
        self.assertIn('mobile_dashboard.ui_action = dashboard_ui_action', source)


if __name__ == "__main__":
    unittest.main()
