"""Regression checks for friend-facing public read-only trial UI.

Structural checks deliberately avoid importing Streamlit in lightweight CI.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"


def streamlit_calls(nodes):
    return [
        node.func.attr
        for statement in nodes
        for node in ast.walk(statement)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "st"
    ]


class PublicBetaSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_data_management_controls_are_opt_in_only(self):
        sidebar = [
            node for node in ast.walk(self.tree)
            if isinstance(node, ast.With)
            and any(
                isinstance(item.context_expr, ast.Attribute)
                and isinstance(item.context_expr.value, ast.Name)
                and item.context_expr.value.id == "st"
                and item.context_expr.attr == "sidebar"
                for item in node.items
            )
        ]
        self.assertEqual(len(sidebar), 1)
        self.assertEqual(len(sidebar[0].body), 1)
        guard = sidebar[0].body[0]
        self.assertIsInstance(guard, ast.If)
        self.assertIsInstance(guard.test, ast.Name)
        self.assertEqual(guard.test.id, "WRITES_ENABLED")
        admin = streamlit_calls(guard.body)
        public = streamlit_calls(guard.orelse)
        self.assertIn("file_uploader", admin)
        self.assertIn("button", admin)
        self.assertNotIn("file_uploader", public)
        self.assertNotIn("button", public)
        self.assertIn("info", public)

    def test_public_guide_appears_before_early_view_stops(self):
        self.assertIn("はじめての方へ｜TCG Meta Lab の使い方", self.source)
        self.assertIn("試験公開中", self.source)
        self.assertLess(
            self.source.index("はじめての方へ｜TCG Meta Lab の使い方"),
            self.source.index("view=st.radio(")
        )
        self.assertIn("WRITES_ENABLED = os.environ.get('TCG_ALLOW_WRITES'", self.source)

    def test_all_existing_analysis_views_and_exports_remain(self):
        for feature in (
            "'対戦勝率・採用カード'",
            "'シティリーグ（国内大会）'",
            "'今週のおすすめ'",
            "render_weekly_recommendations(ROOT)",
            "classify_dragapult('Dragapult',normalize_list(value))",
            "matchup_matrix.csv",
            "matchups.csv",
            "card_comparison.csv",
        ):
            with self.subTest(feature=feature):
                self.assertIn(feature, self.source)

    def test_existing_snapshots_are_still_present(self):
        for filename in (
            "matches_snapshot.csv", "city_league_results.csv",
            "match_countries.csv", "sync_state.json",
        ):
            with self.subTest(filename=filename):
                self.assertTrue((ROOT / filename).is_file())


if __name__ == "__main__":
    unittest.main()
