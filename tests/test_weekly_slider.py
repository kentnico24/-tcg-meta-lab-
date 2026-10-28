"""Check that the Streamlit slider genuinely drives the cached rankings.

This structural test avoids importing Streamlit in CI, which only installs
the lightweight dependencies needed by the repository's pure-Python tests.
"""
import ast
from pathlib import Path
import unittest

VIEW = Path(__file__).resolve().parents[1] / "weekly_view.py"


class MinimumMatchSliderTests(unittest.TestCase):
    def test_slider_has_expected_range_and_default(self):
        tree = ast.parse(VIEW.read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "slider"]
        self.assertEqual(len(calls), 1)
        kwargs = {kw.arg: kw.value for kw in calls[0].keywords}
        for name, expected in (("min_value", 10), ("max_value", 100),
                               ("value", 30), ("step", 10)):
            self.assertEqual(ast.literal_eval(kwargs[name]), expected)

    def test_slider_value_is_passed_to_cache_and_algorithm(self):
        tree = ast.parse(VIEW.read_text(encoding="utf-8"))
        functions = {node.name: node for node in tree.body
                     if isinstance(node, ast.FunctionDef)}
        calculation = functions["calculate_weekly"]
        self.assertIn("min_total_matches",
                      [arg.arg for arg in calculation.args.args])
        algorithm_calls = [n for n in ast.walk(calculation)
                           if isinstance(n, ast.Call)
                           and isinstance(n.func, ast.Name)
                           and n.func.id == "rank_recommendations"]
        self.assertEqual(len(algorithm_calls), 1)
        passed = {kw.arg: kw.value for kw in algorithm_calls[0].keywords}
        self.assertIsInstance(passed["min_total_matches"], ast.Name)
        self.assertEqual(passed["min_total_matches"].id, "min_total_matches")
        display = functions["render_weekly_recommendations"]
        cached_calls = [n for n in ast.walk(display)
                        if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Name)
                        and n.func.id == "calculate_weekly"]
        self.assertEqual(len(cached_calls), 1)
        self.assertEqual(cached_calls[0].args[-1].id, "minimum")


if __name__ == "__main__":
    unittest.main()
