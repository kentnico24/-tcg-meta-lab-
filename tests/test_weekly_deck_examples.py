"""Tests for verifiable Japanese tournament decklist examples."""
import csv
from datetime import date
from pathlib import Path
import unittest

from weekly_deck_examples import select_domestic_decklists, trusted_list_url
from weekly_recommendations import city_family

AS_OF = date(2026, 10, 28)
ROOT = Path(__file__).resolve().parents[1]


def placement(event, day, deck, rank, list_id, key=None):
    return {
        "key": key if key is not None else f"{event}:{rank}",
        "date": day,
        "rank": str(rank),
        "deck": deck,
        "player": f"Player {event}",
        "shop": f"Japan City League {event}",
        "event_url": f"https://limitlesstcg.com/tournaments/jp/{event}",
        "decklist_url": f"https://limitlesstcg.com/decks/list/jp/{list_id}",
    }


class JapaneseDeckExamplesTests(unittest.TestCase):
    def test_only_trusted_published_japanese_list_urls(self):
        self.assertTrue(trusted_list_url(
            "https://limitlesstcg.com/decks/list/jp/76777"))
        for value in (
            "", None,
            "http://limitlesstcg.com/decks/list/jp/76777",
            "https://play.limitlesstcg.com/decks/list/jp/76777",
            "https://limitlesstcg.com.evil.example/decks/list/jp/76777",
            "https://limitlesstcg.com/decks/list/76777",
            "https://limitlesstcg.com/decks/list/jp/abc",
            "https://limitlesstcg.com/decks/list/jp/76777?redirect=other",
        ):
            with self.subTest(value=value):
                self.assertFalse(trusted_list_url(value))

    def test_real_japan_decks_match_recommended_type_and_date(self):
        rows = [
            placement(5001, "2026-10-27", "dragapult dudunsparce", 2, 901),
            placement(5002, "2026-10-26", "dragapult blaziken", 1, 902),
            placement(5003, "2026-10-23", "dragapult dusknoir", 4, 903),
            placement(5004, "2026-10-19", "dragapult", 1, 904),
            placement(5005, "2026-10-27", "lucario-mega hariyama", 1, 905),
            placement(5006, "2026-09-20", "dragapult", 1, 906),
            placement(5007, "2026-10-29", "dragapult", 1, 907),
        ]
        examples = select_domestic_decklists(rows, "Dragapult", AS_OF)
        self.assertEqual(len(examples), 3)
        self.assertEqual([x["date"] for x in examples],
                         ["2026-10-27", "2026-10-26", "2026-10-23"])
        self.assertEqual(examples[0]["deck"], "ドラパルト・ノココッチ")
        self.assertTrue(all(
            x["decklist_url"].startswith(
                "https://limitlesstcg.com/decks/list/jp/")
            for x in examples
        ))
        self.assertEqual(
            select_domestic_decklists(rows, "Mega Lucario", AS_OF)[0]["deck"],
            "メガルカリオ・ハリテヤマ",
        )

    def test_newer_distinct_events_preferred_with_fallback(self):
        rows = [
            placement(5001, "2026-10-27", "dragapult", 1, 9001),
            placement(5001, "2026-10-27", "dragapult", 2, 9002),
            placement(5002, "2026-10-26", "dragapult", 6, 9003),
            placement(5003, "2026-10-25", "dragapult", 9, 9004),
            placement(5001, "2026-10-27", "dragapult", 3, 9001),
        ]
        result = select_domestic_decklists(rows, "Dragapult", AS_OF)
        self.assertEqual([x["event_url"] for x in result], [
            f"https://limitlesstcg.com/tournaments/jp/{event}"
            for event in (5001, 5002, 5003)
        ])
        self.assertEqual([x["rank"] for x in result], [1, 6, 9])
        self.assertEqual(len(
            select_domestic_decklists(rows, "Dragapult", AS_OF, limit=4)), 4)

    def test_reject_invalid_or_unverified_records_and_do_not_invent(self):
        valid = placement(5001, "2026-10-27", "dragapult", 3, 9001)
        invalid = [
            dict(valid, decklist_url=""),
            dict(valid, event_url="https://limitlesstcg.com/tournaments/us/5001"),
            dict(valid, deck="gengar"),
            dict(valid, date="not-a-date"),
            dict(valid, date="2026-10-29"),
            dict(valid, rank="not-known"),
            dict(valid, rank="19"),
            dict(valid, decklist_url="https://untrusted.example/123"),
        ]
        self.assertEqual(select_domestic_decklists(invalid, "Dragapult", AS_OF), [])
        self.assertEqual(
            select_domestic_decklists([valid, *invalid], "Dragapult", AS_OF),
            [{
                "date": "2026-10-27", "rank": 3,
                "deck": "ドラパルト", "shop": valid["shop"],
                "player": valid["player"],
                "event_url": valid["event_url"],
                "decklist_url": valid["decklist_url"],
            }],
        )
        self.assertEqual(select_domestic_decklists([valid], "", AS_OF), [])

    def test_saved_production_japan_city_league_has_real_examples(self):
        with (ROOT / "city_league_results.csv").open(
                encoding="utf-8", newline="") as handle:
            city_rows = list(csv.DictReader(handle))
        saved_with_lists = sum(bool(x["decklist_url"]) for x in city_rows)
        self.assertGreater(saved_with_lists, 1000)
        examples = select_domestic_decklists(
            city_rows, "Dragapult", AS_OF, limit=3)
        self.assertTrue(examples)
        self.assertTrue(all(x["date"] >= "2026-09-25" for x in examples))
        self.assertTrue(all(x["date"] <= "2026-10-28" for x in examples))
        self.assertTrue(all(trusted_list_url(x["decklist_url"]) for x in examples))
        self.assertTrue(all(
            any(r["decklist_url"] == x["decklist_url"]
                and city_family(r["deck"]) == "Dragapult"
                for r in city_rows)
            for x in examples
        ))


if __name__ == "__main__":
    unittest.main()
