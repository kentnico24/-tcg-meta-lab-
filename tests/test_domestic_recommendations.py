"""Prove domestic top-16 meta weighting stays separate from global matchups."""
import unittest

from domestic_recommendations import (
    calculate_domestic_share, city_archetype, world_archetype,
    world_matchup_evidence, recommend,
)


def city_event(event_id, day, decks):
    return [{
        "key": f"{event_id}:{i}", "date": day,
        "event_url": f"https://limitlesstcg.com/tournaments/jp/{event_id}",
        "deck": deck,
    } for i, deck in enumerate(decks)]


def world_games(amount, candidate, opponent, candidate_wins=True,
                day="2026-10-25", offset=0):
    return [{
        "id": f"match-{offset+i}",
        "source": "limitless-play:abc",
        "played_at": day + "T10:00:00Z",
        "deck_a": candidate, "deck_b": opponent,
        "winner": "a" if candidate_wins else "b",
    } for i in range(amount)]


class DomesticRecommendationsTests(unittest.TestCase):
    def setUp(self):
        # 7-day Japan use consists solely of Japanese City League placements.
        self.city = (
            city_event("100", "2026-10-24",
                       ["dragapult"] * 4 + ["alakazam dudunsparce"] * 4)
            + city_event("101", "2026-10-27",
                         ["dragapult dusknoir"] * 4 + ["alakazam dusknoir"] * 4)
        )
        # Worldwide results are evidence of matchups, not weights for use.
        self.world = (
            world_games(30, "Gholdengo", "Dragapult", True, offset=0)
            + world_games(20, "Gholdengo", "Alakazam Dudunsparce",
                          True, offset=30)
            + world_games(30, "Dhelmise", "Dragapult", False, offset=50)
            + world_games(20, "Dhelmise", "Alakazam Dusknoir",
                          False, offset=80)
            + world_games(30, "Dragapult", "Alakazam Dusknoir",
                          False, offset=100)
        )

    def test_city_top16_share_is_not_world_usage(self):
        report = calculate_domestic_share(self.city, "2026-10-28")
        self.assertEqual(report["events"], 2)
        self.assertEqual(report["placements"], 16)
        self.assertEqual(report["start"], "2026-10-22")
        self.assertEqual(report["shares"], {
            "dragapult": 0.5, "alakazam": 0.5,
        })
        recommendation = recommend(self.city, self.world, "2026-10-28")
        self.assertEqual(recommendation["japan"]["shares"], report["shares"])
        self.assertEqual(recommendation["world"]["matches"], 130)
        self.assertEqual(recommendation["recommendations"][0]["deck"],
                         "Gholdengo")
        self.assertGreater(
            recommendation["recommendations"][0]["meta_score"], 50)
        self.assertLess(
            next(x for x in recommendation["recommendations"]
                 if x["deck"] == "Dhelmise")["meta_score"], 50)

    def test_missing_matchups_are_neutral_not_fabricated_100_percent(self):
        world = self.world[:8]
        data = recommend(self.city, world, "2026-10-28")
        self.assertEqual(data["recommendations"], [])
        self.assertEqual(data["japan"]["placements"], 16)

    def test_invalid_sources_do_not_change_city_distribution(self):
        polluted = self.city + [
            {"key": "notjp", "date": "2026-10-27",
             "event_url": "https://play.limitlesstcg.com/tournaments/example",
             "deck": "gengar"},
            {"key": "before", "date": "2026-10-21",
             "event_url": "https://limitlesstcg.com/tournaments/jp/88",
             "deck": "gengar"},
        ]
        self.assertEqual(
            calculate_domestic_share(polluted, "2026-10-28")["shares"],
            calculate_domestic_share(self.city, "2026-10-28")["shares"])

    def test_duplicate_world_matches_never_inflate_win_rates(self):
        doubled = self.world + [dict(self.world[0])]
        evidence = world_matchup_evidence(doubled, "2026-10-28")
        self.assertEqual(evidence["matches"], 130)
        self.assertEqual(evidence["outcomes"][("Gholdengo", "dragapult")][0], 30)

    def test_wrong_match_date_and_non_limitless_sources_rejected(self):
        old = world_games(10, "Gholdengo", "Dragapult",
                          day="2026-08-30", offset=1000)
        nonlimitless = world_games(10, "Gholdengo", "Dragapult",
                                  offset=2000)
        for x in nonlimitless:
            x["source"] = "manual"
        evidence = world_matchup_evidence(self.world + old + nonlimitless,
                                          "2026-10-28")
        self.assertEqual(evidence["matches"], 130)

    def test_conservative_family_linkage(self):
        self.assertEqual(world_archetype("Dragapult Dusknoir"), "dragapult")
        self.assertEqual(world_archetype("Mega Lucario"), "lucario-mega")
        self.assertEqual(world_archetype("N's Zoroark"), "n-zoroark")
        self.assertEqual(world_archetype("Other"), "")
        self.assertEqual(city_archetype("dusknoir dragapult"), "dragapult")
        self.assertEqual(city_archetype("dudunsparce lopunny-mega"), "lopunny-mega")
        self.assertNotEqual(world_archetype("N's Zoroark"),
                            city_archetype("zoroark"))
        self.assertNotEqual(world_archetype("Charizard"),
                            city_archetype("charizard-mega-y"))

    def test_one_city_tournament_is_not_sufficient_to_recommend(self):
        limited = self.city[:8] * 4
        data = recommend(limited, self.world, "2026-10-28")
        self.assertEqual(data["japan"]["events"], 1)
        self.assertEqual(data["recommendations"], [])


if __name__ == "__main__":
    unittest.main()
