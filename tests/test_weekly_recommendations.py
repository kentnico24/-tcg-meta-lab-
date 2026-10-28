"""Domestic-only share x worldwide-matchups recommendation regression tests."""
import csv
from datetime import date, timedelta
from pathlib import Path
import unittest

from weekly_recommendations import (
    city_family, worldwide_family, domestic_meta, worldwide_matchups,
    rank_recommendations,
)

AS_OF = date(2026, 10, 28)
ROOT = Path(__file__).resolve().parents[1]


def city(deck, day="2026-10-27", index=0, event=5000):
    return {
        "key": f"{event}:{index}", "date": day,
        "deck": deck,
        "event_url": f"https://limitlesstcg.com/tournaments/jp/{event}",
    }


def world(deck_a, deck_b, winner, index, day="2026-10-27", source=None):
    return {
        "id": f"world-{index}", "played_at": f"{day}T12:00:00.000Z",
        "deck_a": deck_a, "deck_b": deck_b, "winner": winner,
        "source": source if source is not None else "limitless-play:test-event",
    }


class WeeklyMetaTests(unittest.TestCase):
    def test_regional_shares_only_use_recent_japan_city_placements(self):
        rows = [
            city("dragapult", index=1),
            city("dragapult dudunsparce", index=2),
            city("alakazam dudunsparce", index=3),
            city("zoroark", index=4),
            city("dragapult", "2026-10-21", index=5),
            city("gengar", "2026-09-25", index=6),
            dict(city("slowking", index=7), event_url=
                 "https://limitlesstcg.com/tournaments/us/9000"),
            dict(city("slowking", index=8), event_url=
                 "https://play.limitlesstcg.com/tournaments/8000"),
            city("", index=9),
            city("dragapult", index=1),
        ]
        got = domestic_meta(rows, AS_OF)
        self.assertEqual(got["start"], date(2026, 10, 22))
        self.assertEqual(got["total"], 4)
        self.assertEqual(got["unknown"], 1)
        self.assertEqual(got["counts"]["Dragapult"], 2)
        self.assertAlmostEqual(got["shares"]["Dragapult"], 0.5)
        self.assertNotIn("Slowking", got["shares"])

    def test_conservative_archetype_mapping_does_not_assume_mega_or_n(self):
        self.assertEqual(city_family("lucario-mega hariyama"), "Mega Lucario")
        self.assertEqual(worldwide_family("Mega Lucario"), "Mega Lucario")
        self.assertEqual(worldwide_family("Lucario Hariyama"), "Lucario")
        self.assertNotEqual(city_family("zoroark"),
                            worldwide_family("N's Zoroark"))
        self.assertEqual(city_family("dragapult dusknoir"), "Dragapult")
        self.assertEqual(worldwide_family("Dragapult Dusknoir"), "Dragapult")
        self.assertEqual(city_family("dusknoir dragapult"), "Dragapult")
        self.assertEqual(city_family("raging-bolt ogerpon"), "Raging Bolt")
        self.assertEqual(worldwide_family("Raging Bolt Ogerpon"), "Raging Bolt")
        self.assertNotEqual(city_family("charizard-mega-y"),
                            worldwide_family("Mega Charizard X"))

    def test_online_matches_contribute_only_to_worldwide_winrate_not_share(self):
        matches = [
            world("Mega Lucario", "Dragapult", "a", 1),
            world("Dragapult", "Mega Lucario", "a", 2),
            world("Mega Lucario", "Dragapult", "draw", 3),
            world("Mega Lucario", "Dragapult", "a", 4,
                  source="uploaded-test-data"),
            world("Mega Lucario", "Dragapult", "a", 5,
                  day="2026-09-02"),
            world("Mega Lucario", "Mega Lucario", "a", 6),
            world("Mega Lucario", "Dragapult", "a", 1),
        ]
        got = worldwide_matchups(matches, AS_OF)
        self.assertEqual(got["matches"], 4)  # 3 real + 1 family mirror
        self.assertEqual(got["pairs"][("Mega Lucario", "Dragapult")],
                         [1.5, 3])
        self.assertEqual(got["pairs"][("Dragapult", "Mega Lucario")],
                         [1.5, 3])
        self.assertNotIn(("Mega Lucario", "Mega Lucario"), got["pairs"])
        self.assertEqual(domestic_meta(matches, AS_OF)["total"], 0)

    def test_weighted_domestic_meta_favors_worldwide_dragapult_counter(self):
        placements = [city("dragapult", index=i, event=5000+(i//16))
                      for i in range(48)]
        placements += [city("alakazam dudunsparce", index=200+i, event=5200)
                       for i in range(8)]
        placements += [city("lucario-mega hariyama", index=300+i, event=5300)
                       for i in range(4)]
        # 40 world matchups vs Japan's popular Dragapult, all won by Mega Lucario.
        matches = [world("Mega Lucario", "Dragapult", "a", i)
                   for i in range(40)]
        matches += [world("Mega Lucario", "Alakazam Dusknoir", "b", 100+i)
                    for i in range(12)]
        got = rank_recommendations(placements, matches, AS_OF)
        self.assertEqual(got["meta"]["total"], 60)
        self.assertEqual(got["world"]["matches"], 52)
        self.assertEqual(got["threats"][0]["family"], "Dragapult")
        self.assertEqual(got["recommendations"][0]["family"], "Mega Lucario")
        recommendation = got["recommendations"][0]
        self.assertGreater(recommendation["index"], 0.5)
        self.assertGreaterEqual(recommendation["world_n"], 40)
        self.assertEqual(recommendation["domestic_placements"], 4)
        self.assertGreaterEqual(len(got["recommendations"]), 1)
        self.assertLessEqual(len(got["recommendations"]), 5)
        self.assertEqual(got["recommendations"][0]["family"], "Mega Lucario")
        self.assertEqual(len({r["family"] for r in got["recommendations"]}),
                         len(got["recommendations"]))

    def test_insufficient_and_unmatched_world_data_never_generate_fake_rates(self):
        rows = [city("dragapult", index=i) for i in range(10)]
        rows += [city("zoroark", index=20+i) for i in range(3)]
        matches = [world("N's Zoroark", "Dragapult", "a", i) for i in range(3)]
        result = rank_recommendations(rows, matches, AS_OF)
        self.assertEqual(result["recommendations"], [])
        self.assertEqual(result["eligible"], 0)

    def test_one_or_two_domestic_events_cannot_drive_recommendations(self):
        single_event = [city("dragapult", index=i, event=6000)
                        for i in range(16)]
        world_data = [world("Mega Lucario", "Dragapult", "a", i)
                      for i in range(50)]
        a = rank_recommendations(single_event, world_data, AS_OF)
        self.assertEqual(a["meta"]["events"], 1)
        self.assertEqual(a["recommendations"], [])
        two_events = single_event + [
            city("lucario-mega", index=i, event=6001)
            for i in range(16)
        ]
        b = rank_recommendations(two_events, world_data, AS_OF)
        self.assertEqual(b["meta"]["events"], 2)
        self.assertEqual(b["recommendations"], [])

    def test_mirror_family_never_counts_as_real_matchup_coverage(self):
        city_rows = (
            [city("dragapult", index=i, event=6000) for i in range(12)]
            + [city("alakazam", index=i, event=6001) for i in range(12)]
            + [city("dragapult dusknoir", index=i, event=6002) for i in range(12)]
        )
        world_rows = [
            world("Dragapult", "Alakazam Dudunsparce", "a", i)
            for i in range(30)
        ]
        got = rank_recommendations(city_rows, world_rows, AS_OF)
        candidate = next(
            x for x in got["recommendations"] if x["family"] == "Dragapult"
        )
        self.assertAlmostEqual(candidate["coverage"], 12 / 36)
        self.assertLess(candidate["index"], 1.0)

    def test_current_production_snapshots_are_kept_separate(self):
        # Real-file smoke check protects data integration, not a fixed rank.
        with (ROOT/"city_league_results.csv").open(encoding="utf-8",newline="") as fp:
            city_rows = list(csv.DictReader(fp))
        with (ROOT/"matches_snapshot.csv").open(encoding="utf-8",newline="") as fp:
            world_rows = list(csv.DictReader(fp))
        result = rank_recommendations(city_rows, world_rows, AS_OF)
        self.assertGreater(result["meta"]["total"], 0)
        self.assertGreater(result["world"]["matches"], 0)
        self.assertTrue(all(
            r["world_n"] >= 12 and 0 <= r["index"] <= 1
            for r in result["recommendations"]))
        print(
            "PRODUCTION_WEEKLY_META_SMOKE:",
            "japan_placements", result["meta"]["total"],
            "japan_events", result["meta"]["events"],
            "world_matches", result["world"]["matches"],
            "qualified", result["eligible"],
            "top5", [(x["family"], round(x["index"]*100,1),
                      x["world_n"],round(x["coverage"]*100)) for x in result["recommendations"]],
            flush=True,
        )


if __name__ == "__main__":
    unittest.main()
