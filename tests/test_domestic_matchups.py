"""Domestic win-rate tests: never infer unavailable Swiss or bracket games."""
import csv
import tempfile
import unittest
from pathlib import Path

from domestic_matchups import (
    MATCH_COLUMNS, city_final_matches, player_perspectives,
    read_verified_cl_matches,
)

ROOT = Path(__file__).resolve().parents[1]


def sample_row(event, rank, deck, day="2026-10-27"):
    return {
        "event_url": f"https://limitlesstcg.com/tournaments/jp/{event}",
        "date": day,
        "rank": str(rank),
        "deck": deck,
        "shop": "日本のシティリーグ会場",
    }


class DomesticResultsTests(unittest.TestCase):
    def test_only_verified_final_is_derived_not_top16_rounds(self):
        rows = [
            sample_row(42, 1, "dragapult"),
            sample_row(42, 2, "gengar"),
            sample_row(42, 3, "mewtwo"),
            sample_row(42, 4, "slowking"),
        ]
        matches = city_final_matches(rows)
        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertEqual(match["winner"], "a")
        self.assertEqual(match["deck_a"], "dragapult")
        self.assertEqual(match["deck_b"], "gengar")
        self.assertEqual(match["stage"], "決勝")
        self.assertEqual(match["event_type"], "シティリーグ")
        self.assertEqual(match["source_url"], rows[0]["event_url"])
        self.assertEqual(
            [(r["deck"], r["opponent"], r["result"])
             for r in player_perspectives(matches)],
            [("dragapult", "gengar", 1.0), ("gengar", "dragapult", 0.0)],
        )

    def test_missing_or_ambiguous_final_not_guessed(self):
        self.assertEqual(city_final_matches([
            sample_row(50, 1, "dragapult"),
            sample_row(50, 3, "gengar"),
        ]), [])
        self.assertEqual(city_final_matches([
            sample_row(50, 1, "dragapult"),
            sample_row(50, 1, "dragapult"),
            sample_row(50, 2, "gengar"),
        ]), [])
        self.assertEqual(city_final_matches([
            sample_row(50, 1, ""),
            sample_row(50, 2, "gengar"),
        ]), [])

    def test_mirror_match_is_excluded_from_matchup_win_rates(self):
        matches = city_final_matches([
            sample_row(88, 1, "dragapult"),
            sample_row(88, 2, "dragapult"),
        ])
        self.assertEqual(len(matches), 1)
        self.assertEqual(player_perspectives(matches), [])
        self.assertEqual(len(player_perspectives(matches, exclude_mirrors=False)), 2)

    def test_existing_production_city_data_has_real_finals(self):
        with (ROOT / "city_league_results.csv").open(
                encoding="utf-8", newline="") as fp:
            rows = list(csv.DictReader(fp))
        finals = city_final_matches(rows)
        self.assertGreaterEqual(len(finals), 10)
        self.assertEqual(len({m["id"] for m in finals}), len(finals))
        self.assertTrue(all(m["source_url"].startswith(
            "https://limitlesstcg.com/tournaments/jp/") for m in finals))
        for match in finals:
            self.assertTrue(match["deck_a"] and match["deck_b"])
            self.assertEqual(match["winner"], "a")

    def test_cl2027_yokohama_has_three_source_linked_finals(self):
        entries = read_verified_cl_matches(ROOT / "cl_verified_matches.csv")
        self.assertEqual(len(entries), 3)
        self.assertEqual({x["event_type"] for x in entries}, {"CL"})
        self.assertEqual({x["date"] for x in entries}, {"2026-09-22"})
        self.assertEqual({x["stage"] for x in entries}, {"決勝"})
        self.assertEqual({x["winner"] for x in entries}, {"a"})
        self.assertEqual({x["event_name"].split()[-1] for x in entries},
                         {"マスターリーグ", "ジュニアリーグ", "シニアリーグ"})
        self.assertEqual(len(player_perspectives(entries)), 6)

    def test_cl_source_needs_verified_match_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "cl_verified_matches.csv"
            self.assertEqual(read_verified_cl_matches(file), [])
            row = {
                "id": "CL-test-1", "date": "2026-11-23",
                "event_type": "CL", "stage": "決勝",
                "event_name": "Verified example",
                "deck_a": "dragapult", "deck_b": "gengar",
                "winner": "a",
                "source_url": "https://www.pokemon-card.com/example",
            }
            with file.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=MATCH_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            self.assertEqual(len(read_verified_cl_matches(file)), 1)
            row["source_url"] = "http://random-blog.example.invalid/fake"
            with file.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=MATCH_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "trusted source"):
                read_verified_cl_matches(file)


if __name__ == "__main__":
    unittest.main()
