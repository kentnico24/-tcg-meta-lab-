"""Guard against locking the domestic date picker to first collected match."""
import pathlib
import unittest


class DomesticCalendarTests(unittest.TestCase):
    def test_calendar_accepts_september_even_if_no_results_yet(self):
        app = (pathlib.Path(__file__).resolve().parents[1] / 'app.py').read_text(
            encoding='utf-8')
        self.assertIn("min_value=datetime(2026,9,1).date()", app)
        self.assertIn("まだ確認済みの国内大会結果がありません", app)
        self.assertNotIn("min_value=start_date,max_value=end_date,key='city_period'", app)


if __name__ == '__main__':
    unittest.main()
