"""Per-opponent win-rate sorting, safe without Streamlit/Pandas in CI."""
import ast
from pathlib import Path
import unittest

from matchup_sort import MATCHUP_SORT_OPTIONS, sort_matchup_rows

ROOT = Path(__file__).resolve().parents[1]


class MatchupSortTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"対面": "Dragapult", "試合数": 248, "勝率": 56.0},
            {"対面": "Mew", "試合数": 3, "勝率": 100.0},
            {"対面": "N's Zoroark", "試合数": 109, "勝率": 56.0},
            {"対面": "Crustle", "試合数": 125, "勝率": 36.8},
            {"対面": "Dudunsparce", "試合数": 1, "勝率": 0.0},
        ]

    def labels(self, order):
        return [r["対面"] for r in sort_matchup_rows(self.rows, order)]

    def test_all_four_modes_sort_numeric_columns(self):
        self.assertEqual(MATCHUP_SORT_OPTIONS, (
            "試合数が多い順", "勝率が高い順", "勝率が低い順", "試合数が少ない順"))
        self.assertEqual(self.labels("試合数が多い順"),
                         ["Dragapult", "Crustle", "N's Zoroark", "Mew", "Dudunsparce"])
        self.assertEqual(self.labels("勝率が高い順"),
                         ["Mew", "Dragapult", "N's Zoroark", "Crustle", "Dudunsparce"])
        self.assertEqual(self.labels("勝率が低い順"),
                         ["Dudunsparce", "Crustle", "Dragapult", "N's Zoroark", "Mew"])
        self.assertEqual(self.labels("試合数が少ない順"),
                         ["Dudunsparce", "Mew", "N's Zoroark", "Crustle", "Dragapult"])

    def test_ties_prioritize_more_evidence_and_input_is_unchanged(self):
        original = [dict(r) for r in self.rows]
        for option in MATCHUP_SORT_OPTIONS:
            sorted_rows = sort_matchup_rows(self.rows, option)
            self.assertEqual(len(sorted_rows), len(self.rows))
            self.assertEqual(sorted_rows, sort_matchup_rows(self.rows, option))
            self.assertEqual(self.rows, original)
        self.assertLess(
            self.labels("勝率が高い順").index("Dragapult"),
            self.labels("勝率が高い順").index("N's Zoroark"))

    def test_unrecognized_sort_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            sort_matchup_rows(self.rows, "random")

    def test_streamlit_display_csv_and_chart_share_sorted_summary(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("matchup_sort=st.selectbox('対面表の並び替え'", source)
        self.assertIn("summary=pd.DataFrame(sort_matchup_rows(matchup_rows,matchup_sort))", source)
        self.assertIn("display_summary=summary.assign(", source)
        self.assertIn("st.bar_chart(display_summary.set_index('対面')['勝率'])", source)
        self.assertIn("summary.to_csv(index=False)", source)


if __name__ == "__main__":
    unittest.main()
