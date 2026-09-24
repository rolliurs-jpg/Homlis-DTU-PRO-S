from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DashboardCursorTests(unittest.TestCase):
    def test_chart_has_inline_coloured_cursor_values(self):
        source = (ROOT / "dashboard_ui.html").read_text(encoding="utf-8")
        self.assertIn('id="chart-cursor"', source)
        self.assertIn("pointermove", source)
        self.assertIn("showChartCursor", source)
        self.assertIn("['Production',p.production_w,'var(--blue)']", source)
        self.assertIn("['Maison',p.consumption_w,'#fff']", source)
        self.assertIn("['Injection',p.export_w,'var(--gold)']", source)
        self.assertIn("battery<0?'var(--red)':'var(--green)'", source)
        self.assertNotIn('class="chart-tooltip"', source)


if __name__ == "__main__":
    unittest.main()
