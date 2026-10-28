"""Regression checks for the no-matplotlib world matchup matrix."""
import ast
import math
import pathlib
import unittest

from matrix_style import matrix_cell_css

ROOT = pathlib.Path(__file__).resolve().parents[1]


class MatrixStyleTests(unittest.TestCase):
    def test_color_endpoints_and_missing_values(self):
        self.assertIn("background-color: #f9ccca", matrix_cell_css(0))
        self.assertIn("background-color: #fff6c2", matrix_cell_css(50))
        self.assertIn("background-color: #bee9cd", matrix_cell_css(100))
        self.assertEqual(matrix_cell_css(-15), matrix_cell_css(0))
        self.assertEqual(matrix_cell_css(150), matrix_cell_css(100))
        for bad in (None, "", "—", float("nan"), math.inf, -math.inf):
            with self.subTest(bad=bad):
                self.assertEqual(matrix_cell_css(bad), "")

    def test_color_scale_is_monotonic_and_css_only(self):
        for win_rate in (0, 12.4, 25, 40, 50, 60, 75, 99.9, 100):
            with self.subTest(win_rate=win_rate):
                css = matrix_cell_css(win_rate)
                self.assertTrue(css.startswith("background-color: #"))
                self.assertIn("color: #222222;", css)
                self.assertNotIn("rgb(", css)

    def test_app_no_longer_uses_optional_gradient(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn(".map(matrix_cell_css)", source)
        self.assertIn("from matrix_style import matrix_cell_css", source)
        # It is safe to mention the removed method in explanatory comments.
        self.assertNotIn(".background_gradient(", source)
        self.assertIn("file_name='matchup_matrix.csv'", source)


if __name__ == "__main__":
    unittest.main()
